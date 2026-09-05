"""Provider-neutral perception adapter and temporal ingestion boundary for Atlas Live.

Sits between external tracking providers (optical cameras, computer vision, RFID/UWB, simulators)
and the Atlas LiveWorldStateReconciler.

Responsibilities:
1. Translate external entity measurements into canonical EntityObservation & LiveObservationFrame batches.
2. Filter jitter, staleness, out-of-order packets, timestamp discontinuities, and velocity jumps.
3. Preserve strict temporal semantics:
   - Source/Capture timestamp (physical world occurrence)
   - Adapter arrival/ingestion timestamp (monotonic host arrival)
4. Telemetry collection on accepted/rejected/downgraded observations.
"""

from dataclasses import dataclass
from enum import Enum
import math
import time
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from planning.digital_twin_spatial import SpatialPose, Vector3
from live.observation import EntityObservation, LiveObservationFrame


class TimestampDomain(str, Enum):
    MONOTONIC_HOST = "monotonic_host"
    MONOTONIC_SOURCE = "monotonic_source"
    UTC_UNIX = "utc_unix"


class IngestionRejectionReason(str, Enum):
    OUT_OF_ORDER = "out_of_order"
    STALE = "stale"
    TIMESTAMP_DISCONTINUITY = "timestamp_discontinuity"
    MISSING_TIMESTAMP = "missing_timestamp"
    CONFIDENCE_TOO_LOW = "confidence_too_low"
    VELOCITY_IMPLAUSIBLE = "velocity_implausible"
    EMPTY_FRAME = "empty_frame"
    TIMESTAMP_DOMAIN_MISMATCH = "timestamp_domain_mismatch"


@dataclass(frozen=True)
class RawEntityMeasurement:
    """Raw, vendor-agnostic sensor/perception observation of a single entity."""

    entity_id: str
    x: float
    y: float
    z: float
    frame_id: str = "atlas-field"
    vx: Optional[float] = None
    vy: Optional[float] = None
    vz: Optional[float] = None
    confidence: float = 1.0
    attributes: Tuple[Tuple[str, str], ...] = ()


@dataclass(frozen=True)
class RawPerceptionFrame:
    """Raw observation packet from an external perception provider before normalization."""

    source_id: str
    sequence_number: int
    sensor_timestamp_ns: int
    measurements: Tuple[RawEntityMeasurement, ...] = ()
    attributes: Tuple[Tuple[str, str], ...] = ()
    metadata: Optional[Mapping[str, str]] = None


@dataclass(frozen=True)
class IngestionTelemetry:
    """Observable metrics from the perception ingestion filter."""

    total_frames_received: int
    total_frames_accepted: int
    total_frames_rejected: int
    total_entities_ingested: int
    total_entities_filtered: int
    rejection_counts: Mapping[str, int]
    last_jitter_ns: int
    last_ingestion_latency_ns: int


class PerceptionIngestionPolicy:
    """Configurable boundaries for filtering sensor jitter, latency, and implausible motion.

    All parameters are explicit policy settings rather than fixed architectural assumptions.
    """

    def __init__(
        self,
        min_confidence: float = 0.3,
        max_staleness_ns: Optional[int] = None,  # Optional max staleness against arrival time (same epoch)
        max_timestamp_jump_ns: Optional[int] = 5_000_000_000,  # 5.0s discontinuity threshold, or None to disable
        max_implausible_speed_m_s: Optional[float] = 60.0,  # Configurable sanity ceiling, or None to disable
        allow_out_of_order: bool = False,  # Strict monotonic rejection by default; True allows bounded reordering in future
        expected_timestamp_domain: TimestampDomain = TimestampDomain.MONOTONIC_HOST,
    ) -> None:
        if not 0.0 <= float(min_confidence) <= 1.0:
            raise ValueError("min_confidence must be between 0.0 and 1.0")
        if max_staleness_ns is not None and max_staleness_ns <= 0:
            raise ValueError("max_staleness_ns must be positive when provided")
        if max_timestamp_jump_ns is not None and max_timestamp_jump_ns <= 0:
            raise ValueError("max_timestamp_jump_ns must be positive when provided")
        if max_implausible_speed_m_s is not None and max_implausible_speed_m_s <= 0.0:
            raise ValueError("max_implausible_speed_m_s must be positive when provided")

        self.min_confidence = float(min_confidence)
        self.max_staleness_ns = max_staleness_ns
        self.max_timestamp_jump_ns = max_timestamp_jump_ns
        self.max_implausible_speed_m_s = (
            float(max_implausible_speed_m_s) if max_implausible_speed_m_s is not None else None
        )
        self.allow_out_of_order = allow_out_of_order
        self.expected_timestamp_domain = expected_timestamp_domain


class PerceptionAdapter:
    """Provider-neutral perception adapter enforcing temporal normalization and jitter policies."""

    def __init__(
        self,
        source_id: str,
        policy: Optional[PerceptionIngestionPolicy] = None,
    ) -> None:
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("source_id must be a non-empty string")
        self.source_id = source_id.strip()
        self.policy = policy or PerceptionIngestionPolicy()

        self._active_session_id: Optional[str] = None
        self._last_sensor_timestamp_ns: int = -1
        self._last_known_positions: Dict[str, Tuple[float, float, float, int]] = {}  # entity -> (x, y, z, t_ns)

        # Telemetry
        self._total_received = 0
        self._total_accepted = 0
        self._total_rejected = 0
        self._total_entities_ingested = 0
        self._total_entities_filtered = 0
        self._rejection_counts: Dict[str, int] = {r.value: 0 for r in IngestionRejectionReason}
        self._last_jitter_ns = 0
        self._last_ingestion_latency_ns = 0

    @property
    def telemetry(self) -> IngestionTelemetry:
        return IngestionTelemetry(
            total_frames_received=self._total_received,
            total_frames_accepted=self._total_accepted,
            total_frames_rejected=self._total_rejected,
            total_entities_ingested=self._total_entities_ingested,
            total_entities_filtered=self._total_entities_filtered,
            rejection_counts=dict(self._rejection_counts),
            last_jitter_ns=self._last_jitter_ns,
            last_ingestion_latency_ns=self._last_ingestion_latency_ns,
        )

    def process_raw_frame(
        self,
        raw: RawPerceptionFrame,
        ingested_at_ns: Optional[int] = None,
    ) -> Optional[LiveObservationFrame]:
        """Ingest, filter, and adapt a raw perception frame into a canonical LiveObservationFrame.

        Returns None if the frame fails temporal validity, jitter, or staleness checks.
        """
        now_ns = ingested_at_ns if ingested_at_ns is not None else time.perf_counter_ns()
        self._total_received += 1

        # Check for provider session reset / change
        frame_session = (
            raw.metadata.get("session_id") if raw.metadata else None
        )
        if frame_session is not None and frame_session != self._active_session_id:
            # Clean session reset: reset local sensor sequence/timestamp tracking without corrupting pipeline
            self._active_session_id = frame_session
            self._last_sensor_timestamp_ns = -1
            self._last_known_positions.clear()

        # 0. Timestamp domain validation
        frame_domain = (
            raw.metadata.get("timestamp_domain") if raw.metadata else None
        )
        if frame_domain is not None:
            if frame_domain != self.policy.expected_timestamp_domain.value:
                self._reject(IngestionRejectionReason.TIMESTAMP_DOMAIN_MISMATCH)
                return None

        # 1. Missing or invalid timestamp check
        if raw.sensor_timestamp_ns < 0:
            self._reject(IngestionRejectionReason.MISSING_TIMESTAMP)
            return None

        # 2. Staleness check against arrival time
        # ONLY evaluate against now_ns if domain is MONOTONIC_HOST (same epoch/clock)
        if (
            self.policy.max_staleness_ns is not None
            and self.policy.expected_timestamp_domain == TimestampDomain.MONOTONIC_HOST
            and now_ns > raw.sensor_timestamp_ns
        ):
            staleness = now_ns - raw.sensor_timestamp_ns
            if staleness > self.policy.max_staleness_ns:
                self._reject(IngestionRejectionReason.STALE)
                return None

        # 3. Monotonic ordering and jitter check
        if self._last_sensor_timestamp_ns >= 0:
            if raw.sensor_timestamp_ns < self._last_sensor_timestamp_ns:
                # Out-of-order frame
                jitter = self._last_sensor_timestamp_ns - raw.sensor_timestamp_ns
                self._last_jitter_ns = jitter
                if not self.policy.allow_out_of_order:
                    self._reject(IngestionRejectionReason.OUT_OF_ORDER)
                    return None
            elif raw.sensor_timestamp_ns == self._last_sensor_timestamp_ns:
                # Duplicate timestamp
                if not self.policy.allow_out_of_order:
                    self._reject(IngestionRejectionReason.OUT_OF_ORDER)
                    return None

            # 4. Discontinuity check (large gap)
            if self.policy.max_timestamp_jump_ns is not None:
                time_gap = raw.sensor_timestamp_ns - self._last_sensor_timestamp_ns
                if time_gap > self.policy.max_timestamp_jump_ns:
                    self._reject(IngestionRejectionReason.TIMESTAMP_DISCONTINUITY)
                    return None

        # Record valid sensor timestamp
        self._last_sensor_timestamp_ns = max(self._last_sensor_timestamp_ns, raw.sensor_timestamp_ns)
        # Only compute ingestion latency against host clock if monotonic host domain
        if self.policy.expected_timestamp_domain == TimestampDomain.MONOTONIC_HOST:
            self._last_ingestion_latency_ns = max(0, now_ns - raw.sensor_timestamp_ns)
        else:
            self._last_ingestion_latency_ns = 0

        # 5. Entity observation filtering (confidence, implausible speed)
        valid_entities: List[EntityObservation] = []
        for m in raw.measurements:
            # Confidence check
            if m.confidence < self.policy.min_confidence:
                self._total_entities_filtered += 1
                self._rejection_counts[IngestionRejectionReason.CONFIDENCE_TOO_LOW.value] += 1
                continue

            # Check implausible speed jump if policy is enabled
            if self.policy.max_implausible_speed_m_s is not None:
                dt_s = 0.0
                if m.entity_id in self._last_known_positions:
                    px, py, pz, pt_ns = self._last_known_positions[m.entity_id]
                    dt_s = (raw.sensor_timestamp_ns - pt_ns) / 1e9
                    if dt_s > 0.0:
                        dx = m.x - px
                        dy = m.y - py
                        dz = m.z - pz
                        speed = math.sqrt(dx * dx + dy * dy + dz * dz) / dt_s
                        if speed > self.policy.max_implausible_speed_m_s:
                            self._total_entities_filtered += 1
                            self._rejection_counts[IngestionRejectionReason.VELOCITY_IMPLAUSIBLE.value] += 1
                            continue

            self._last_known_positions[m.entity_id] = (m.x, m.y, m.z, raw.sensor_timestamp_ns)

            vel = (
                Vector3(m.vx, m.vy, m.vz)
                if (m.vx is not None and m.vy is not None and m.vz is not None)
                else None
            )

            entity_obs = EntityObservation(
                entity_id=m.entity_id,
                pose=SpatialPose(m.frame_id, Vector3(m.x, m.y, m.z)),
                velocity=vel,
                confidence=m.confidence,
                attributes=m.attributes,
            )
            valid_entities.append(entity_obs)

        if not valid_entities and raw.measurements:
            # All measurements were filtered out
            self._reject(IngestionRejectionReason.EMPTY_FRAME)
            return None

        self._total_accepted += 1
        self._total_entities_ingested += len(valid_entities)

        return LiveObservationFrame(
            source_id=self.source_id,
            sequence_number=raw.sequence_number,
            timestamp_ns=raw.sensor_timestamp_ns,
            entities=tuple(valid_entities),
            frame_attributes=raw.attributes,
            metadata=raw.metadata,
            ingested_at_ns=now_ns,
        )

    def _reject(self, reason: IngestionRejectionReason) -> None:
        self._total_rejected += 1
        self._rejection_counts[reason.value] += 1
