import pytest

from planning.unreal_adapter_v01 import AdapterResultKind, UnrealAdapterV01
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind


def operation(kind):
    return UnrealOperation(
        UnrealCapability.MODIFY_ACTOR,
        kind,
        "modify_goal",
        {"location": (1, 2, 3)},
        ("GOAL_LEFT",),
    )


def test_inspect_accepts_only_reads():
    result = UnrealAdapterV01().inspect(operation(UnrealOperationKind.READ))
    assert result.kind is AdapterResultKind.EVIDENCE
    assert result.evidence_ids


def test_inspect_rejects_writes():
    result = UnrealAdapterV01().inspect(operation(UnrealOperationKind.WRITE))
    assert result.kind is AdapterResultKind.REJECTED


def test_apply_requires_authorization():
    result = UnrealAdapterV01().apply_authorized(operation(UnrealOperationKind.WRITE), "")
    assert result.kind is AdapterResultKind.REJECTED
    assert "authorization" in result.reason


def test_authorized_apply_returns_evidence():
    result = UnrealAdapterV01().apply_authorized(operation(UnrealOperationKind.WRITE), "auth-123")
    assert result.kind is AdapterResultKind.EVIDENCE
    assert result.evidence_ids


def test_verify_requires_observed_state():
    verify_operation = UnrealOperation(
        UnrealCapability.MODIFY_ACTOR,
        UnrealOperationKind.VERIFY,
        "verify_goal",
        {},
        ("GOAL_LEFT",),
    )
    result = UnrealAdapterV01().verify(verify_operation, {})
    assert result.kind is AdapterResultKind.REJECTED


def test_verify_returns_evidence_for_observed_state():
    verify_operation = UnrealOperation(
        UnrealCapability.MODIFY_ACTOR,
        UnrealOperationKind.VERIFY,
        "verify_goal",
        {},
        ("GOAL_LEFT",),
    )
    result = UnrealAdapterV01().verify(verify_operation, {"location": (1, 2, 3)})
    assert result.kind is AdapterResultKind.EVIDENCE
    assert result.evidence_ids
