"""Engine-independent contract for Atlas live Digital Twin state.

Atlas owns the semantic shape and lineage of live state. A simulator, tracking
system, game engine, or other runtime may own production of that state. This
module intentionally contains no networking, polling, execution, or engine SDK
code.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple

from planning.digital_twin_spatial import SpatialPose


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
class LiveEntityState:
    """One observed runtime state for an existing canonical Digital Twin entity."""

    entity_id: str
    pose: Optional[SpatialPose] = None
    attributes: Tuple[Tuple[str, str], ...] = ()
    status: str = "active"

    def __post_init__(self) -> None:
        if not self.entity_id.strip():
            raise ValueError("entity_id must not be empty")
        if not self.status.strip():
            raise ValueError("status must not be empty")
        normalized = tuple((key.strip().lower(), value.strip()) for key, value in self.attributes)
        if any(not key or not value for key, value in normalized):
            raise ValueError("live entity attributes must contain non-empty key/value pairs")
        if len({key for key, _ in normalized}) != len(normalized):
            raise ValueError("live entity attributes must have unique keys")
        object.__setattr__(self, "attributes", normalized)


@dataclass(frozen=True)
class LiveWorldStateSnapshot:
    """Immutable, provider-neutral snapshot of a canonical twin at one instant."""

    twin_id: str
    revision_id: str
    state_sequence: int
    observed_at: str
    source_id: str
    entities: Tuple[LiveEntityState, ...] = ()
    world_attributes: Tuple[Tuple[str, str], ...] = ()
    metadata: Optional[Mapping[str, Any]] = None

    def __post_init__(self) -> None:
        for field_name in ("twin_id", "revision_id", "observed_at", "source_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if not isinstance(self.state_sequence, int) or isinstance(self.state_sequence, bool) or self.state_sequence < 1:
            raise ValueError("state_sequence must be a positive integer")
        entity_ids = tuple(entity.entity_id for entity in self.entities)
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("live world-state entities must have unique ids")
        normalized_attributes = tuple((key.strip().lower(), value.strip()) for key, value in self.world_attributes)
        if any(not key or not value for key, value in normalized_attributes):
            raise ValueError("world attributes must contain non-empty key/value pairs")
        if len({key for key, _ in normalized_attributes}) != len(normalized_attributes):
            raise ValueError("world attributes must have unique keys")
        object.__setattr__(self, "world_attributes", normalized_attributes)
        if self.metadata is not None:
            if not isinstance(self.metadata, Mapping):
                raise TypeError("metadata must be a mapping when provided")
            object.__setattr__(self, "metadata", _freeze(self.metadata))

    def entity(self, entity_id: str) -> LiveEntityState:
        """Return an entity state by canonical entity id."""
        normalized = entity_id.strip()
        for entity in self.entities:
            if entity.entity_id == normalized:
                return entity
        raise KeyError(entity_id)

    def attribute(self, key: str) -> Optional[str]:
        """Return a normalized world-state attribute, if present."""
        normalized = key.strip().lower()
        for candidate, value in self.world_attributes:
            if candidate == normalized:
                return value
        return None

    def metadata_snapshot(self) -> Mapping[str, Any]:
        """Return detached metadata suitable for transport or persistence."""
        return _thaw(self.metadata or {})


@dataclass(frozen=True)
class LiveWorldStateEnvelope:
    """Transport-neutral envelope for handing live state across a subsystem boundary."""

    snapshot: LiveWorldStateSnapshot
    provider_type: str
    provider_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, LiveWorldStateSnapshot):
            raise TypeError("snapshot must be a LiveWorldStateSnapshot")
        if not self.provider_type.strip():
            raise ValueError("provider_type must not be empty")
        if not self.provider_version.strip():
            raise ValueError("provider_version must not be empty")


def validate_live_world_state(
    snapshot: LiveWorldStateSnapshot,
    *,
    expected_twin_id: Optional[str] = None,
    expected_revision_id: Optional[str] = None,
    previous_sequence: Optional[int] = None,
) -> None:
    """Apply Atlas's pure admission rules to an already-produced live snapshot.

    This function validates identity and monotonic sequencing only. It does not
    decide whether the external provider is trustworthy, fetch newer state, or
    mutate a canonical Digital Twin revision.
    """
    if not isinstance(snapshot, LiveWorldStateSnapshot):
        raise TypeError("snapshot must be a LiveWorldStateSnapshot")
    if expected_twin_id is not None and snapshot.twin_id != expected_twin_id:
        raise ValueError("live world-state twin_id does not match expected Digital Twin")
    if expected_revision_id is not None and snapshot.revision_id != expected_revision_id:
        raise ValueError("live world-state revision_id does not match expected revision")
    if previous_sequence is not None:
        if not isinstance(previous_sequence, int) or isinstance(previous_sequence, bool) or previous_sequence < 0:
            raise ValueError("previous_sequence must be a non-negative integer")
        if snapshot.state_sequence <= previous_sequence:
            raise ValueError("live world-state sequence must increase monotonically")


__all__ = [
    "LiveEntityState",
    "LiveWorldStateEnvelope",
    "LiveWorldStateSnapshot",
    "validate_live_world_state",
]
