import pytest

from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionResult
from planning.unreal_recovery_authority import (
    UnrealRecoveryAuthority,
    evidence_digest,
    replacement_authorization_digest,
    replacement_plan_digest,
)
from planning.unreal_task_planner import UnrealTaskPlan


ENTITY_IDS = ("FIELD_SURFACE",)


def _plan(start=10, end=110):
    return UnrealTaskPlan(
        "unreal-recovery-authority",
        (
            UnrealOperation(
                UnrealCapability.SEQUENCER,
                UnrealOperationKind.WRITE,
                "set_sequencer_playback_range",
                {"entity_ids": ENTITY_IDS, "start_frame": start, "end_frame": end},
                ENTITY_IDS,
            ),
            UnrealOperation(
                UnrealCapability.SEQUENCER,
                UnrealOperationKind.VERIFY,
                "verify_sequencer_playback_range",
                {"entity_ids": ENTITY_IDS, "expected_start_frame": start, "expected_end_frame": end},
                ENTITY_IDS,
            ),
        ),
    )


def _result(start=10, end=110):
    evidence = UnrealEvidence(
        "inspect_sequencer_state",
        ENTITY_IDS,
        {
            "FIELD_SURFACE": {
                "entity_id": "FIELD_SURFACE",
                "sequencer": {"start_frame": start, "end_frame": end},
            }
        },
        "unreal-editor-atlas-transport",
        verified=False,
    )
    return UnrealPlanExecutionResult("unreal-recovery-authority:reassess-sequence", (evidence,), True)


def _authority():
    plan = _plan()
    authorization = UnrealPlanAuthorization.issue(plan, "replacement-auth")
    return UnrealRecoveryAuthority.issue(_result(), plan, authorization), plan, authorization


def test_authority_binds_exact_reassessment_plan_and_authorization():
    authority, plan, authorization = _authority()
    authority.require_match(_result(), plan, authorization)
    assert authority.snapshot()["receipt_digest"] == authority.receipt.receipt_digest


def test_authority_rejects_modified_reassessment_evidence():
    authority, plan, authorization = _authority()
    with pytest.raises(ValueError, match="identity mismatch"):
        authority.require_match(_result(20, 120), plan, authorization)


def test_authority_rejects_modified_replacement_plan():
    authority, _, authorization = _authority()
    modified_plan = _plan(20, 120)
    modified_authorization = UnrealPlanAuthorization.issue(modified_plan, authorization.authorization_id)
    with pytest.raises(ValueError, match="identity mismatch"):
        authority.require_match(_result(), modified_plan, modified_authorization)


def test_authority_rejects_authorization_for_different_plan():
    authority, plan, _ = _authority()
    other_plan = _plan(20, 120)
    other_authorization = UnrealPlanAuthorization.issue(other_plan, "replacement-auth")
    with pytest.raises(ValueError, match="identity mismatch"):
        authority.require_match(_result(), plan, other_authorization)


def test_digest_functions_are_stable_for_identical_inputs():
    plan = _plan()
    authorization = UnrealPlanAuthorization.issue(plan, "replacement-auth")
    result = _result()
    assert evidence_digest(result) == evidence_digest(result)
    assert replacement_plan_digest(plan) == replacement_plan_digest(plan)
    assert replacement_authorization_digest(authorization) == replacement_authorization_digest(authorization)
