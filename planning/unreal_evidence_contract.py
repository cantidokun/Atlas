"""Engine-neutral evidence contract for the Unreal Agent boundary.

Evidence is produced by the Unreal side after an operation is executed. It is
not an authorization receipt and cannot authorize itself. Atlas verification
consumes this evidence independently of the agent's proposal.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Tuple


@dataclass(frozen=True)
class UnrealEvidence:
    operation_name: str
    entity_ids: Tuple[str, ...]
    observed_state: Mapping[str, Any]
    source: str
    verified: bool = False

    def __post_init__(self) -> None:
        if not self.operation_name.strip():
            raise ValueError("operation_name must not be empty")
        if not self.entity_ids:
            raise ValueError("evidence requires explicit entity IDs")
        if any(not entity_id.strip() for entity_id in self.entity_ids):
            raise ValueError("evidence entity_ids must not contain empty values")
        if not self.source.strip():
            raise ValueError("evidence source must not be empty")
        if not isinstance(self.observed_state, Mapping):
            raise TypeError("observed_state must be a mapping")


def validate_evidence_for_operation(evidence: UnrealEvidence, operation_name: str, entity_ids: Tuple[str, ...]) -> UnrealEvidence:
    """Ensure evidence refers exactly to the operation and Atlas targets."""
    if evidence.operation_name != operation_name:
        raise ValueError("evidence operation_name does not match operation")
    if tuple(evidence.entity_ids) != tuple(entity_ids):
        raise ValueError("evidence entity_ids do not match operation targets")
    return evidence
