"""World-State representation and deterministic state reconciliation for Atlas Live.

Atlas owns the canonical World-State representation. External observations are reconciled
deterministically into this state model. This module maintains entity spatial poses,
velocities, confidence, freshness, and temporal history.
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from planning.digital_twin_spatial import SpatialPose, Vector3
from live.observation import EntityObservation, LiveObservationFrame, _freeze, _thaw


class EntityFreshness(str, Enum):
    OBSERVED = "observed"
    STALE = "stale"
    UNOBSERVED = "unobserved"


@dataclass(frozen=True)
class LiveWorldEntity:
    """Reconciled canonical state of an entity in the Live World-State."""

    entity_id: str
    pose: Optional[SpatialPose] = None
    velocity: Optional[Vector3] = None
    confidence: float = 1.0
    last_observed_timestamp_ns: int = 0
    source_id: str = "unknown"
    attributes: Tuple[Tuple[str, str], ...] = ()
    freshness: EntityFreshness = EntityFreshness.OBSERVED
    is_observed: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.entity_id, str) or not self.entity_id.strip():
            raise ValueError("entity_id must be a non-empty string")
        if not isinstance(self.confidence, (int, float)) or isinstance(self.confidence, bool):
            raise TypeError("confidence must be a float between 0.0 and 1.0")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if not isinstance(self.last_observed_timestamp_ns, int) or isinstance(self.last_observed_timestamp_ns, bool) or self.last_observed_timestamp_ns < 0:
            raise ValueError("last_observed_timestamp_ns must be a non-negative integer")
        if not isinstance(self.freshness, EntityFreshness):
            raise TypeError("freshness must be an instance of EntityFreshness")
        normalized = tuple((key.strip().lower(), value.strip()) for key, value in self.attributes)
        if any(not key or not value for key, value in normalized):
            raise ValueError("attributes must contain non-empty key/value pairs")
        if len({key for key, _ in normalized}) != len(normalized):
            raise ValueError("attributes must have unique keys")
        object.__setattr__(self, "attributes", normalized)
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "is_observed", bool(self.freshness == EntityFreshness.OBSERVED))

    def attribute(self, key: str) -> Optional[str]:
        target = key.strip().lower()
        for k, v in self.attributes:
            if k == target:
                return v
        return None


@dataclass(frozen=True)
class LiveWorldState:
    """Canonical, provider-neutral representation of the live soccer world at one instant."""

    twin_id: str
    sequence_number: int
    timestamp_ns: int
    entities: Tuple[LiveWorldEntity, ...] = ()
    world_attributes: Tuple[Tuple[str, str], ...] = ()
    metadata: Optional[Mapping[str, Any]] = None
    reconciled_at_ns: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.twin_id, str) or not self.twin_id.strip():
            raise ValueError("twin_id must be a non-empty string")
        if not isinstance(self.sequence_number, int) or isinstance(self.sequence_number, bool) or self.sequence_number < 1:
            raise ValueError("sequence_number must be a positive integer")
        if not isinstance(self.timestamp_ns, int) or isinstance(self.timestamp_ns, bool) or self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be a non-negative integer")
        entity_ids = tuple(entity.entity_id for entity in self.entities)
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("entities must have unique ids")
        normalized_attrs = tuple((key.strip().lower(), value.strip()) for key, value in self.world_attributes)
        if any(not key or not value for key, value in normalized_attrs):
            raise ValueError("world_attributes must contain non-empty key/value pairs")
        if len({key for key, _ in normalized_attrs}) != len(normalized_attrs):
            raise ValueError("world_attributes must have unique keys")
        object.__setattr__(self, "world_attributes", normalized_attrs)
        if self.reconciled_at_ns is not None:
            if not isinstance(self.reconciled_at_ns, int) or isinstance(self.reconciled_at_ns, bool) or self.reconciled_at_ns < 0:
                raise ValueError("reconciled_at_ns must be a non-negative integer when provided")
        if self.metadata is not None:
            if not isinstance(self.metadata, Mapping):
                raise TypeError("metadata must be a mapping when provided")
            object.__setattr__(self, "metadata", _freeze(self.metadata))

    def entity(self, entity_id: str) -> LiveWorldEntity:
        target = entity_id.strip()
        for e in self.entities:
            if e.entity_id == target:
                return e
        raise KeyError(entity_id)

    def has_entity(self, entity_id: str, only_fresh: bool = False) -> bool:
        target = entity_id.strip()
        for e in self.entities:
            if e.entity_id == target:
                if only_fresh:
                    return e.freshness == EntityFreshness.OBSERVED
                return True
        return False

    def attribute(self, key: str) -> Optional[str]:
        target = key.strip().lower()
        for k, v in self.world_attributes:
            if k == target:
                return v
        return None

    def metadata_snapshot(self) -> Mapping[str, Any]:
        return _thaw(self.metadata or {})


class LiveWorldStateReconciler:
    """Reconciles incoming observation frames into authoritative LiveWorldState snapshots.

    Deterministic behavior:
    - Out-of-order/stale observation frames (timestamp <= last frame timestamp) are rejected.
    - Entities omitted from a frame are explicitly marked STALE or UNOBSERVED.
    - Derived velocity resets when an entity reappears after an observation gap (> max_derivative_gap_ns).
    - Retains bounded history buffer for event detection and temporal queries.
    """

    def __init__(
        self,
        twin_id: str,
        max_history: int = 100,
        freshness_window_ns: int = 150_000_000,  # 150ms freshness limit
        max_derivative_gap_ns: int = 100_000_000,  # 100ms max continuity gap for deriving velocity
    ) -> None:
        if not isinstance(twin_id, str) or not twin_id.strip():
            raise ValueError("twin_id must be a non-empty string")
        if max_history < 2:
            raise ValueError("max_history must be at least 2")
        if freshness_window_ns <= 0:
            raise ValueError("freshness_window_ns must be positive")
        if max_derivative_gap_ns <= 0:
            raise ValueError("max_derivative_gap_ns must be positive")

        self.twin_id: str = twin_id.strip()
        self.max_history: int = max_history
        self.freshness_window_ns: int = freshness_window_ns
        self.max_derivative_gap_ns: int = max_derivative_gap_ns

        self._current_sequence: int = 0
        self._entities: Dict[str, LiveWorldEntity] = {}
        # Track observation continuity per entity: entity_id -> (last_seen_timestamp_ns, consecutive_count)
        self._entity_continuity: Dict[str, Tuple[int, int]] = {}
        self._world_attributes: Dict[str, str] = {}
        self._history: List[LiveWorldState] = []
        self._last_observation_timestamp_ns: int = -1

    @property
    def current_state(self) -> Optional[LiveWorldState]:
        if not self._history:
            return None
        return self._history[-1]

    @property
    def history(self) -> Sequence[LiveWorldState]:
        return tuple(self._history)

    def ingest(self, frame: LiveObservationFrame) -> Optional[LiveWorldState]:
        """Ingest a new observation frame and return the updated LiveWorldState.

        Rejects frames that arrive stale or out of order (timestamp_ns <= last timestamp).
        """
        if not isinstance(frame, LiveObservationFrame):
            raise TypeError("frame must be a LiveObservationFrame")

        # Stale/out-of-order check
        if frame.timestamp_ns <= self._last_observation_timestamp_ns:
            return None

        self._last_observation_timestamp_ns = frame.timestamp_ns
        self._current_sequence += 1

        observed_ids: set = set()

        # Reconcile entities present in the frame
        for obs in frame.entities:
            entity_id = obs.entity_id
            observed_ids.add(entity_id)
            prior = self._entities.get(entity_id)

            # Continuity tracking for derivative safety
            continuity_info = self._entity_continuity.get(entity_id)
            is_continuous = False
            consecutive_obs = 1
            dt_entity_s = 0.0

            if continuity_info is not None:
                last_seen_ns, prior_consecutive = continuity_info
                gap_ns = frame.timestamp_ns - last_seen_ns
                if gap_ns <= self.max_derivative_gap_ns and gap_ns > 0:
                    is_continuous = True
                    consecutive_obs = prior_consecutive + 1
                    dt_entity_s = gap_ns / 1e9

            self._entity_continuity[entity_id] = (frame.timestamp_ns, consecutive_obs)

            computed_velocity = obs.velocity
            if computed_velocity is None:
                # Only derive velocity if observations were continuous (no observation gap)
                if (
                    is_continuous
                    and prior is not None
                    and prior.pose is not None
                    and obs.pose is not None
                    and dt_entity_s > 0.0
                ):
                    if prior.pose.frame_id == obs.pose.frame_id:
                        vx = (obs.pose.position.x - prior.pose.position.x) / dt_entity_s
                        vy = (obs.pose.position.y - prior.pose.position.y) / dt_entity_s
                        vz = (obs.pose.position.z - prior.pose.position.z) / dt_entity_s
                        computed_velocity = Vector3(vx, vy, vz)
                else:
                    # Observation gap or first observation: do NOT manufacture velocity from gap!
                    computed_velocity = None

            # Reconcile attributes (merge new over prior)
            merged_attrs: Dict[str, str] = {}
            if prior is not None:
                for k, v in prior.attributes:
                    merged_attrs[k] = v
            for k, v in obs.attributes:
                merged_attrs[k] = v

            reconciled_entity = LiveWorldEntity(
                entity_id=obs.entity_id,
                pose=obs.pose if obs.pose is not None else (prior.pose if prior else None),
                velocity=computed_velocity if computed_velocity is not None else (prior.velocity if prior and is_continuous else None),
                confidence=obs.confidence,
                last_observed_timestamp_ns=frame.timestamp_ns,
                source_id=frame.source_id,
                attributes=tuple((k, v) for k, v in sorted(merged_attrs.items())),
                freshness=EntityFreshness.OBSERVED,
            )
            self._entities[entity_id] = reconciled_entity

        # Reconcile unobserved entities: mark STALE or UNOBSERVED based on freshness window
        for entity_id, entity in list(self._entities.items()):
            if entity_id not in observed_ids:
                time_since_seen_ns = frame.timestamp_ns - entity.last_observed_timestamp_ns
                freshness = (
                    EntityFreshness.STALE
                    if time_since_seen_ns <= self.freshness_window_ns
                    else EntityFreshness.UNOBSERVED
                )
                # Keep last known spatial info, but flag as STALE/UNOBSERVED and clear velocity
                self._entities[entity_id] = LiveWorldEntity(
                    entity_id=entity.entity_id,
                    pose=entity.pose,
                    velocity=None,  # Do not project stale velocity
                    confidence=max(0.0, entity.confidence * 0.9),  # Decay confidence
                    last_observed_timestamp_ns=entity.last_observed_timestamp_ns,
                    source_id=entity.source_id,
                    attributes=entity.attributes,
                    freshness=freshness,
                )

        # Reconcile frame attributes
        for k, v in frame.frame_attributes:
            self._world_attributes[k] = v

        snapshot = LiveWorldState(
            twin_id=self.twin_id,
            sequence_number=self._current_sequence,
            timestamp_ns=frame.timestamp_ns,
            entities=tuple(self._entities[eid] for eid in sorted(self._entities.keys())),
            world_attributes=tuple((k, v) for k, v in sorted(self._world_attributes.items())),
            metadata=frame.metadata,
            reconciled_at_ns=time.perf_counter_ns(),
        )

        self._history.append(snapshot)
        if len(self._history) > self.max_history:
            self._history.pop(0)

        return snapshot
