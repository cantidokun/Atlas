"""Engine-neutral evidence contract for the Unreal Agent boundary.

Evidence is produced by the Unreal side after an operation is executed. It is
not an authorization receipt and cannot authorize itself. Atlas verification
consumes this evidence independently of the agent's proposal.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Tuple


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
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return sorted((_thaw(item) for item in value), key=repr)
    return value


@dataclass(frozen=True)
class UnrealEvidence:
    operation_name: str
    entity_ids: Tuple[str, ...]
    observed_state: Mapping[str, Any]
    source: str
    verified: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.operation_name, str) or not self.operation_name.strip():
            raise ValueError("operation_name must not be empty")
        if not isinstance(self.entity_ids, (list, tuple)):
            raise TypeError("evidence entity_ids must be a sequence")
        entity_ids = tuple(self.entity_ids)
        if not entity_ids:
            raise ValueError("evidence requires explicit entity IDs")
        if any(not isinstance(entity_id, str) or not entity_id.strip() for entity_id in entity_ids):
            raise ValueError("evidence entity_ids must not contain empty values")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("evidence source must not be empty")
        if not isinstance(self.observed_state, Mapping):
            raise TypeError("observed_state must be a mapping")
        if not isinstance(self.verified, bool):
            raise TypeError("verified must be a boolean")
        object.__setattr__(self, "entity_ids", entity_ids)
        object.__setattr__(self, "observed_state", _freeze(self.observed_state))

    def snapshot(self) -> dict[str, Any]:
        """Return a detached JSON-compatible snapshot of the immutable evidence."""
        return {
            "operation_name": self.operation_name,
            "entity_ids": list(self.entity_ids),
            "observed_state": _thaw(self.observed_state),
            "source": self.source,
            "verified": self.verified,
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any]) -> "UnrealEvidence":
        """Reconstruct evidence from an exact persisted snapshot, fail-closed."""
        if not isinstance(snapshot, Mapping):
            raise TypeError("Unreal evidence snapshot must be a mapping")
        required = {"operation_name", "entity_ids", "observed_state", "source", "verified"}
        if set(snapshot) != required:
            raise ValueError("Unreal evidence snapshot fields are invalid")
        return cls(
            operation_name=snapshot["operation_name"],
            entity_ids=snapshot["entity_ids"],
            observed_state=snapshot["observed_state"],
            source=snapshot["source"],
            verified=snapshot["verified"],
        )


def validate_evidence_for_operation(evidence: UnrealEvidence, operation_name: str, entity_ids: Tuple[str, ...]) -> UnrealEvidence:
    """Ensure evidence refers exactly to the operation and Atlas targets."""
    if not isinstance(evidence, UnrealEvidence):
        raise TypeError("evidence must be a UnrealEvidence instance")
    if evidence.operation_name != operation_name:
        raise ValueError("evidence operation_name does not match operation")
    if tuple(evidence.entity_ids) != tuple(entity_ids):
        raise ValueError("evidence entity_ids do not match operation targets")
    return evidence
