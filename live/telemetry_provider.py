"""Telemetry stream provider for Atlas Live.

Ingests or replays recorded single-camera tracking telemetry (JSON lines / stream)
and transforms raw telemetry batches into canonical RawPerceptionFrame packets.

Adheres to Atlas architecture boundaries:
- Pure perception ingestion: ZERO WorldState, identity, event, or Unreal logic.
- Preserves source_id, provider_session, provider_track_id, timestamp_domain.
- Supports file replay and generator/iterator stream interfaces.
"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple, Union

from live.perception_adapter import RawEntityMeasurement, RawPerceptionFrame


@dataclass(frozen=True)
class TelemetryStreamConfig:
    source_id: str = "cam-field-01"
    default_frame_id: str = "atlas-field"
    default_timestamp_domain: str = "monotonic_source"


class TelemetryStreamProvider:
    """Reads recorded or incoming single-camera tracking telemetry and yields RawPerceptionFrame batches."""

    def __init__(
        self,
        config: Optional[TelemetryStreamConfig] = None,
    ) -> None:
        self.config = config or TelemetryStreamConfig()
        self._current_session: Optional[str] = None
        self._last_sequence: int = 0

    @property
    def current_session(self) -> Optional[str]:
        return self._current_session

    def parse_telemetry_line(self, line: str) -> Optional[RawPerceptionFrame]:
        """Parse one line of JSON tracking telemetry into a RawPerceptionFrame."""
        clean = line.strip()
        if not clean:
            return None
        data = json.loads(clean)
        return self.parse_telemetry_dict(data)

    def parse_telemetry_dict(self, data: Mapping[str, Any]) -> RawPerceptionFrame:
        """Parse dictionary payload into a RawPerceptionFrame."""
        source_id = str(data.get("source_id", self.config.source_id)).strip()
        session_id = str(data.get("session_id", "session-default")).strip()
        self._current_session = session_id

        sequence_number = int(data.get("sequence_number", self._last_sequence + 1))
        self._last_sequence = sequence_number

        timestamp_ns = int(data.get("timestamp_ns", 0))
        timestamp_domain = str(data.get("timestamp_domain", self.config.default_timestamp_domain)).strip()

        measurements: List[RawEntityMeasurement] = []
        for item in data.get("entities", []):
            track_id = str(item.get("track_id") or item.get("entity_id", "")).strip()
            if not track_id:
                continue
            x = float(item.get("x", 0.0))
            y = float(item.get("y", 0.0))
            z = float(item.get("z", 0.0))
            frame_id = str(item.get("frame_id", self.config.default_frame_id)).strip()
            confidence = float(item.get("confidence", 1.0))

            vx = float(item["vx"]) if "vx" in item and item["vx"] is not None else None
            vy = float(item["vy"]) if "vy" in item and item["vy"] is not None else None
            vz = float(item["vz"]) if "vz" in item and item["vz"] is not None else None

            attrs: List[Tuple[str, str]] = []
            if "track_status" in item:
                attrs.append(("track_status", str(item["track_status"]).strip()))
            for k, v in item.get("attributes", {}).items() if isinstance(item.get("attributes"), dict) else item.get("attributes", ()):
                attrs.append((str(k).strip(), str(v).strip()))

            measurements.append(
                RawEntityMeasurement(
                    entity_id=track_id,
                    x=x,
                    y=y,
                    z=z,
                    frame_id=frame_id,
                    vx=vx,
                    vy=vy,
                    vz=vz,
                    confidence=confidence,
                    attributes=tuple(attrs),
                )
            )

        metadata = {
            "session_id": session_id,
            "timestamp_domain": timestamp_domain,
        }
        if "metadata" in data and isinstance(data["metadata"], dict):
            for k, v in data["metadata"].items():
                metadata[str(k)] = str(v)

        return RawPerceptionFrame(
            source_id=source_id,
            sequence_number=sequence_number,
            sensor_timestamp_ns=timestamp_ns,
            measurements=tuple(measurements),
            attributes=tuple((str(k), str(v)) for k, v in data.get("attributes", ())),
            metadata=metadata,
        )

    def replay_file(
        self,
        file_path: Union[str, Path],
        realtime: bool = False,
        speed_factor: float = 1.0,
    ) -> Iterator[RawPerceptionFrame]:
        """Replay recorded tracking telemetry lines from a file path.

        Parameters:
        - file_path: Path to jsonl fixture file.
        - realtime: If True, paces yields according to frame timestamp deltas.
        - speed_factor: Multiplier for pacing speed (e.g. 2.0 = 2x speed, 0.5 = half speed).
        """
        import time

        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Telemetry fixture not found: {file_path}")

        last_ts_ns: Optional[int] = None

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                frame = self.parse_telemetry_line(line)
                if frame is not None:
                    if realtime and last_ts_ns is not None and speed_factor > 0:
                        delta_ns = frame.sensor_timestamp_ns - last_ts_ns
                        if delta_ns > 0:
                            sleep_s = (delta_ns / 1e9) / speed_factor
                            time.sleep(sleep_s)
                    last_ts_ns = frame.sensor_timestamp_ns
                    yield frame
