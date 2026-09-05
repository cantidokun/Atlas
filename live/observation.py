"""Canonical observation primitives for Atlas Live.

External perception systems, tracking hardware, and simulators emit raw observations.
Atlas accepts them through this schema. Downstream consumers consume reconciled WorldState,
not vendor-specific payloads.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple

from planning.digital_twin_spatial import SpatialPose, Vector3


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class EntityObservation:
    """Observed state for a single entity from an external provider/sensor."""

    entity_id: str
    pose: Optional[SpatialPose] = None
    velocity: Optional[Vector3] = None
    confidence: float = 1.0
    attributes: Tuple[Tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.entity_id, str) or not self.entity_id.strip():
            raise ValueError("entity_id must be a non-empty string")
        if not isinstance(self.confidence, (int, float)) or isinstance(self.confidence, bool):
            raise TypeError("confidence must be a float between 0.0 and 1.0")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        normalized = tuple((key.strip().lower(), value.strip()) for key, value in self.attributes)
        if any(not key or not value for key, value in normalized):
            raise ValueError("entity attributes must contain non-empty key/value pairs")
        if len({key for key, _ in normalized}) != len(normalized):
            raise ValueError("entity attributes must have unique keys")
        object.__setattr__(self, "attributes", normalized)
        object.__setattr__(self, "confidence", float(self.confidence))


@dataclass(frozen=True)
class LiveObservationFrame:
    """A single coherent time-indexed observation batch from an external provider or simulator."""

    source_id: str
    sequence_number: int
    timestamp_ns: int
    entities: Tuple[EntityObservation, ...] = ()
    frame_attributes: Tuple[Tuple[str, str], ...] = ()
    metadata: Optional[Mapping[str, Any]] = None
    ingested_at_ns: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id must be a non-empty string")
        if not isinstance(self.sequence_number, int) or isinstance(self.sequence_number, bool) or self.sequence_number < 1:
            raise ValueError("sequence_number must be a positive integer")
        if not isinstance(self.timestamp_ns, int) or isinstance(self.timestamp_ns, bool) or self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be a non-negative integer")
        entity_ids = tuple(entity.entity_id for entity in self.entities)
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("frame entities must have unique ids")
        normalized_attrs = tuple((key.strip().lower(), value.strip()) for key, value in self.frame_attributes)
        if any(not key or not value for key, value in normalized_attrs):
            raise ValueError("frame attributes must contain non-empty key/value pairs")
        if len({key for key, _ in normalized_attrs}) != len(normalized_attrs):
            raise ValueError("frame attributes must have unique keys")
        object.__setattr__(self, "frame_attributes", normalized_attrs)
        if self.ingested_at_ns is not None:
            if not isinstance(self.ingested_at_ns, int) or isinstance(self.ingested_at_ns, bool) or self.ingested_at_ns < 0:
                raise ValueError("ingested_at_ns must be a non-negative integer when provided")
        if self.metadata is not None:
            if not isinstance(self.metadata, Mapping):
                raise TypeError("metadata must be a mapping when provided")
            object.__setattr__(self, "metadata", _freeze(self.metadata))

    def entity(self, entity_id: str) -> EntityObservation:
        """Return an entity observation by entity id."""
        target = entity_id.strip()
        for e in self.entities:
            if e.entity_id == target:
                return e
        raise KeyError(entity_id)

    def metadata_snapshot(self) -> Mapping[str, Any]:
        """Return detached copy of metadata."""
        return _thaw(self.metadata or {})
