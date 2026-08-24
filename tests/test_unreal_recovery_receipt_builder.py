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


def test_builder_derives_evidence_and_exact_plan_identity():
    reassessment = UnrealPlanExecutionResult("reassessment", (), True)
    replacement = _plan()

    receipt = build_recovery_receipt(reassessment, replacement, "authorization-1")

    assert receipt.evidence_digest == digest_evidence_ledger(())
    assert receipt.plan_digest == UnrealPlanAuthorization.issue(
        replacement, "unused"
    ).plan_digest
    assert receipt.authorization_digest == "authorization-1"


def test_builder_rejects_unsuccessful_reassessment():
    with pytest.raises(ValueError, match="unsuccessful reassessment"):
        build_recovery_receipt(
            UnrealPlanExecutionResult("reassessment", (), False),
            _plan(),
            "authorization-1",
        )


def test_builder_rejects_missing_authorization_identity():
    with pytest.raises(ValueError, match="authorization_digest"):
        build_recovery_receipt(
            UnrealPlanExecutionResult("reassessment", (), True),
            _plan(),
            " ",
        )


def test_builder_returns_immutable_receipt():
    receipt = build_recovery_receipt(
        UnrealPlanExecutionResult("reassessment", (), True),
        _plan(),
        "authorization-1",
    )
    assert isinstance(receipt, RecoveryReceipt)
    with pytest.raises(AttributeError):
        receipt.evidence_digest = "changed"
