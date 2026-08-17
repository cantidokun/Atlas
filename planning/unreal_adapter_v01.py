"""Engine-neutral Unreal adapter v0.1 contract and reference behavior.

This module stops at the Atlas boundary. It does not import Unreal Engine APIs.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Tuple

from planning.unreal_agent import UnrealOperation, UnrealOperationKind


class AdapterResultKind(str, Enum):
    EVIDENCE = "evidence"
    REJECTED = "rejected"


@dataclass(frozen=True)
class UnrealAdapterResult:
    operation_name: str
    kind: AdapterResultKind
    evidence_ids: Tuple[str, ...] = ()
    reason: str = ""


class UnrealAdapterV01:
    """Reference adapter boundary; real Unreal transport plugs in later."""

    def inspect(self, operation: UnrealOperation) -> UnrealAdapterResult:
        if operation.kind is not UnrealOperationKind.READ:
            return UnrealAdapterResult(operation.name, AdapterResultKind.REJECTED, reason="inspect accepts READ only")
        return UnrealAdapterResult(operation.name, AdapterResultKind.EVIDENCE, evidence_ids=(f"unreal:{operation.name}:inspection",))

    def apply_authorized(self, operation: UnrealOperation, authorization_id: str) -> UnrealAdapterResult:
        if operation.kind is not UnrealOperationKind.WRITE:
            return UnrealAdapterResult(operation.name, AdapterResultKind.REJECTED, reason="write accepts WRITE only")
        if not authorization_id.strip():
            return UnrealAdapterResult(operation.name, AdapterResultKind.REJECTED, reason="authorization is required")
        return UnrealAdapterResult(operation.name, AdapterResultKind.EVIDENCE, evidence_ids=(f"unreal:{operation.name}:applied",))

    def verify(self, operation: UnrealOperation, observed_state: Mapping[str, object]) -> UnrealAdapterResult:
        if operation.kind is not UnrealOperationKind.VERIFY:
            return UnrealAdapterResult(operation.name, AdapterResultKind.REJECTED, reason="verify accepts VERIFY only")
        if not observed_state:
            return UnrealAdapterResult(operation.name, AdapterResultKind.REJECTED, reason="verification requires observed state")
        return UnrealAdapterResult(operation.name, AdapterResultKind.EVIDENCE, evidence_ids=(f"unreal:{operation.name}:verification",))
