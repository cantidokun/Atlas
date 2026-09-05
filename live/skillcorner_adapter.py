"""Adapter transforming official SkillCorner tracking data into Atlas Live RawPerceptionFrame batches.

Adheres strictly to Atlas perception boundary semantics:
- Provider ID: "skillcorner-broadcast-cam" (or configured source_id)
- Session ID: e.g. "skillcorner-match-2017461-p1"
- Track ID: e.g. "trk_ball" for ball, f"trk_p{player_id}" for players
- Coordinates: (x, y, z) in meters, pitch-centered (x long side, y short side)
- Track status: "detected" vs "extrapolated"
- Confidence mapping:
  * Ball: 1.0 if is_detected else 0.4 (extrapolated)
  * Player: 0.95 if is_detected else 0.4 (extrapolated)
- Timing: 10 Hz frame * 100_000_000 ns (monotonic_source domain)
- Preserves raw frame, timestamp, and period in metadata.
"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple, Union

from live.perception_adapter import RawEntityMeasurement, RawPerceptionFrame


@dataclass(frozen=True)
class SkillCornerAdapterConfig:
    source_id: str = "skillcorner-broadcast-cam"
    session_id: str = "skillcorner-session-default"
    default_frame_id: str = "atlas-field"
    ball_track_id: str = "trk_ball"
    frame_interval_ns: int = 100_000_000  # 10 fps (100 ms)
    # Extrapolated observations are degraded in confidence
    detected_ball_confidence: float = 1.0
    extrapolated_ball_confidence: float = 0.4
    detected_player_confidence: float = 0.95
    extrapolated_player_confidence: float = 0.4
    filter_extrapolated_ball: bool = False  # When True, drops extrapolated ball entirely


class SkillCornerTrackingAdapter:
    """Transforms raw SkillCorner JSON tracking frames into canonical RawPerceptionFrame batches."""

    def __init__(self, config: Optional[SkillCornerAdapterConfig] = None) -> None:
        self.config = config or SkillCornerAdapterConfig()

    def transform_frame(self, raw_data: Mapping[str, Any]) -> Optional[RawPerceptionFrame]:
        """Convert a single SkillCorner tracking dictionary into a RawPerceptionFrame."""
        source_frame = raw_data.get("frame")
        if source_frame is None:
            return None

        # Period and elapsed match timestamp
        period = raw_data.get("period")
        source_ts_str = str(raw_data.get("timestamp") or "")

        # Monotonic source timestamp in nanoseconds derived from source frame index
        sensor_timestamp_ns = int(source_frame) * self.config.frame_interval_ns

        measurements: List[RawEntityMeasurement] = []

        # 1. Process Ball
        ball = raw_data.get("ball_data")
        if ball and isinstance(ball, dict) and ball.get("x") is not None and ball.get("y") is not None:
            is_detected = bool(ball.get("is_detected"))
            if not is_detected and self.config.filter_extrapolated_ball:
                pass  # Discard extrapolated ball if configured
            else:
                bx = float(ball["x"])
                by = float(ball["y"])
                bz = float(ball.get("z", 0.11)) if ball.get("z") is not None else 0.11

                ball_conf = (
                    self.config.detected_ball_confidence
                    if is_detected
                    else self.config.extrapolated_ball_confidence
                )
                ball_status = "detected" if is_detected else "extrapolated"

                measurements.append(
                    RawEntityMeasurement(
                        entity_id=self.config.ball_track_id,
                        x=bx,
                        y=by,
                        z=bz,
                        frame_id=self.config.default_frame_id,
                        confidence=ball_conf,
                        attributes=(
                            ("track_status", ball_status),
                            ("is_detected", str(is_detected).lower()),
                        ),
                    )
                )

        # 2. Process Players
        players = raw_data.get("player_data", [])
        for p in players:
            pid = p.get("player_id")
            if pid is None or p.get("x") is None or p.get("y") is None:
                continue

            is_det = bool(p.get("is_detected"))
            px = float(p["x"])
            py = float(p["y"])
            pz = 0.0

            player_conf = (
                self.config.detected_player_confidence
                if is_det
                else self.config.extrapolated_player_confidence
            )
            player_status = "detected" if is_det else "extrapolated"

            measurements.append(
                RawEntityMeasurement(
                    entity_id=f"trk_p{pid}",
                    x=px,
                    y=py,
                    z=pz,
                    frame_id=self.config.default_frame_id,
                    confidence=player_conf,
                    attributes=(
                        ("track_status", player_status),
                        ("is_detected", str(is_det).lower()),
                        ("skillcorner_player_id", str(pid)),
                    ),
                )
            )

        metadata = {
            "session_id": self.config.session_id,
            "timestamp_domain": "monotonic_source",
            "source_frame": str(source_frame),
            "source_match_timestamp": source_ts_str,
            "period": str(period) if period is not None else "",
        }

        return RawPerceptionFrame(
            source_id=self.config.source_id,
            sequence_number=int(source_frame),
            sensor_timestamp_ns=sensor_timestamp_ns,
            measurements=tuple(measurements),
            metadata=metadata,
        )

    def replay_raw_file(
        self,
        file_path: Union[str, Path],
        realtime: bool = False,
        speed_factor: float = 1.0,
    ) -> Iterator[RawPerceptionFrame]:
        """Replay raw SkillCorner jsonl lines, transforming each into a RawPerceptionFrame."""
        import time

        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"SkillCorner raw file not found: {file_path}")

        last_ts_ns: Optional[int] = None

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                obj = json.loads(line_str)
                frame = self.transform_frame(obj)
                if frame is not None:
                    if realtime and last_ts_ns is not None and speed_factor > 0:
                        delta_ns = frame.sensor_timestamp_ns - last_ts_ns
                        if delta_ns > 0:
                            sleep_s = (delta_ns / 1e9) / speed_factor
                            time.sleep(sleep_s)
                    last_ts_ns = frame.sensor_timestamp_ns
                    yield frame
