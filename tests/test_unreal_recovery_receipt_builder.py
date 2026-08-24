import pytest

from planning.recovery_receipt import RecoveryReceipt
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_evidence_digest import digest_evidence_ledger
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionResult
from planning.unreal_recovery_workflow import build_recovery_receipt
from planning.unreal_task_planner import UnrealTaskPlan


ENTITY_IDS = ("FIELD_SURFACE",)


def _plan():
    return UnrealTaskPlan(
        "receipt-builder-replacement",
        (
            UnrealOperation(
                UnrealCapability.SEQUENCER,
                UnrealOperationKind.WRITE,
                "set_sequencer_playback_range",
                {"entity_ids": ENTITY_IDS, "start_frame": 10, "end_frame": 110},
                ENTITY_IDS,
            ),
        ),
    )


def test_builder_derives_evidence_plan_and_authorization_identity():
    reassessment = UnrealPlanExecutionResult("reassessment", (), True)
    replacement = _plan()
    replacement_auth = UnrealPlanAuthorization.issue(replacement, "replacement-auth")

    receipt = build_recovery_receipt(reassessment, replacement, replacement_auth)

    assert receipt.evidence_digest == digest_evidence_ledger(())
    assert receipt.plan_digest == replacement_auth.plan_digest
    assert receipt.authorization_digest == replacement_auth.authorization_digest


def test_builder_rejects_authorization_for_modified_plan():
    reassessment = UnrealPlanExecutionResult("reassessment", (), True)
    replacement = _plan()
    authorized = UnrealPlanAuthorization.issue(replacement, "replacement-auth")
    modified = UnrealTaskPlan(
        "receipt-builder-replacement-modified",
        replacement.operations,
    )

    with pytest.raises(ValueError, match="exact replacement plan"):
        build_recovery_receipt(reassessment, modified, authorized)


def test_builder_rejects_unsuccessful_reassessment():
    with pytest.raises(ValueError, match="unsuccessful reassessment"):
        build_recovery_receipt(
            UnrealPlanExecutionResult("reassessment", (), False),
            _plan(),
            UnrealPlanAuthorization.issue(_plan(), "replacement-auth"),
        )


def test_builder_rejects_missing_authorization_identity():
    with pytest.raises(TypeError, match="UnrealPlanAuthorization"):
        build_recovery_receipt(
            UnrealPlanExecutionResult("reassessment", (), True),
            _plan(),
            "authorization-1",
        )


def test_authorization_digest_changes_with_exact_authorization():
    plan = _plan()
    first = UnrealPlanAuthorization.issue(plan, "replacement-auth-a")
    second = UnrealPlanAuthorization.issue(plan, "replacement-auth-b")

    assert first.authorization_digest != second.authorization_digest
    assert first.authorization_digest == UnrealPlanAuthorization.issue(
        plan, "replacement-auth-a"
    ).authorization_digest


def test_builder_returns_immutable_receipt():
    replacement = _plan()
    receipt = build_recovery_receipt(
        UnrealPlanExecutionResult("reassessment", (), True),
        replacement,
        UnrealPlanAuthorization.issue(replacement, "replacement-auth"),
    )
    assert isinstance(receipt, RecoveryReceipt)
    with pytest.raises(AttributeError):
        receipt.evidence_digest = "changed"
