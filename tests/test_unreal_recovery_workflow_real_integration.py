"""Real Unreal integration coverage for the receipt-bound recovery workflow."""

import pytest

from planning.recovery_receipt import RecoveryReceipt
from planning.unreal_adapter_production import create_production_adapter
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_evidence_digest import digest_evidence_ledger
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionFailure, UnrealPlanExecutor
from planning.unreal_recovery_sequence import (
    assess_reassessment_sequence,
    build_reassessment_plan,
    build_replacement_plan,
    issue_replacement_authorization,
)
from planning.unreal_recovery_workflow import (
    build_recovery_receipt,
    execute_receipt_bound_recovery_sequence,
)
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner
from planning.unreal_transport_named_pipe import NamedPipeTransportError


pytestmark = pytest.mark.integration

ENTITY_ID = "FIELD_SURFACE"


def _intent(intent_id: str) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="real receipt-bound Unreal recovery workflow integration",
        target_entity_ids=(ENTITY_ID,),
    )


def _inspection_plan(intent):
    operation = UnrealOperation(
        capability=UnrealCapability.SEQUENCER,
        kind=UnrealOperationKind.READ,
        name="inspect_sequencer_state",
        arguments={"entity_ids": (ENTITY_ID,)},
        entity_ids=(ENTITY_ID,),
    )
    return UnrealTaskPlan(intent.intent_id, (operation,))


def _sequencer_state(evidence):
    state = evidence.observed_state[ENTITY_ID]["sequencer"]
    return {"start_frame": int(state["start_frame"]), "end_frame": int(state["end_frame"])}


def _post_write_failure(target_state, intent_id):
    return UnrealPlanExecutionFailure(
        intent_id=intent_id,
        operation_index=2,
        operation_name="verify_sequencer_playback_range",
        completed_evidence=(
            UnrealEvidence(
                operation_name="inspect_sequencer_state",
                entity_ids=(ENTITY_ID,),
                observed_state={ENTITY_ID: {"entity_id": ENTITY_ID, "sequencer": dict(target_state)}},
                source="real-receipt-bound-recovery-test",
                verified=False,
            ),
            UnrealEvidence(
                operation_name="set_sequencer_playback_range",
                entity_ids=(ENTITY_ID,),
                observed_state={ENTITY_ID: {"entity_id": ENTITY_ID, "sequencer": dict(target_state)}},
                source="real-receipt-bound-recovery-test",
                verified=False,
            ),
        ),
        error="simulated post-write verification failure",
        operation_entity_ids=(ENTITY_ID,),
        operation_arguments={
            "entity_ids": (ENTITY_ID,),
            "expected_start_frame": target_state["start_frame"],
            "expected_end_frame": target_state["end_frame"],
        },
        completed_operation_arguments=(
            {"entity_ids": (ENTITY_ID,)},
            {
                "entity_ids": (ENTITY_ID,),
                "start_frame": target_state["start_frame"],
                "end_frame": target_state["end_frame"],
            },
        ),
    )


def test_real_receipt_bound_recovery_workflow_executes_authorized_replacement():
    """Exercise the complete live reassess -> receipt check -> replacement path."""
    try:
        adapter = create_production_adapter("receipt-bound-recovery-workflow-integration")
        executor = UnrealPlanExecutor(adapter)
        planner = UnrealTaskPlanner()

        original_result = executor.execute(
            _inspection_plan(_intent("real-receipt-bound-original")),
            "real-receipt-bound-original-auth",
        )
        original_state = _sequencer_state(original_result.evidence_ledger[0])
        target_state = {
            "start_frame": original_state["start_frame"] + 10,
            "end_frame": original_state["end_frame"] + 10,
        }
        mismatched_state = {
            "start_frame": original_state["start_frame"] + 20,
            "end_frame": original_state["end_frame"] + 20,
        }

        try:
            write_plan = planner.plan_sequencer_playback_range(
                _intent("real-receipt-bound-write"),
                target_state["start_frame"],
                target_state["end_frame"],
            )
            write_result = executor.execute(
                write_plan,
                "real-receipt-bound-write-auth",
            )
            assert _sequencer_state(write_result.evidence_ledger[2]) == target_state

            mismatch_plan = planner.plan_sequencer_playback_range(
                _intent("real-receipt-bound-mismatch"),
                mismatched_state["start_frame"],
                mismatched_state["end_frame"],
            )
            mismatch_result = executor.execute(
                mismatch_plan,
                "real-receipt-bound-mismatch-auth",
            )
            assert _sequencer_state(mismatch_result.evidence_ledger[2]) == mismatched_state

            failure = _post_write_failure(target_state, write_plan.intent_id)
            reassessment_plan = build_reassessment_plan(write_plan, failure)
            reassessment_authorization = UnrealPlanAuthorization.issue(
                reassessment_plan,
                "real-receipt-bound-reassessment-auth",
            )
            reassessment_result = executor.execute_authorized(
                reassessment_plan,
                reassessment_authorization,
            )
            assessment = assess_reassessment_sequence(
                write_plan,
                failure,
                reassessment_result,
            )
            assert assessment.disposition == "replacement_required"

            replacement_plan = build_replacement_plan(write_plan, assessment)
            replacement_authorization = issue_replacement_authorization(
                replacement_plan,
                "real-receipt-bound-replacement-auth",
            )
            receipt = build_recovery_receipt(
                reassessment_result,
                replacement_plan,
                replacement_authorization,
            )
            evidence_digest = digest_evidence_ledger(reassessment_result.evidence_ledger)
            authorization_digest = replacement_authorization.authorization_digest

            recovery = execute_receipt_bound_recovery_sequence(
                executor,
                write_plan,
                failure,
                reassessment_authorization,
                replacement_authorization,
                receipt,
                evidence_digest=evidence_digest,
                authorization_digest=authorization_digest,
            )

            assert recovery.assessment.disposition == "replacement_required"
            assert recovery.replacement_plan is not None
            assert recovery.replacement_result is not None
            assert recovery.replacement_result.success is True
            assert _sequencer_state(recovery.replacement_result.evidence_ledger[1]) == target_state
        finally:
            restore_plan = planner.plan_sequencer_playback_range(
                _intent("real-receipt-bound-restore"),
                original_state["start_frame"],
                original_state["end_frame"],
            )
            restore_result = executor.execute(
                restore_plan,
                "real-receipt-bound-restore-auth",
            )
            assert restore_result.success is True
            assert _sequencer_state(restore_result.evidence_ledger[2]) == original_state

    except NamedPipeTransportError as exc:
        message = str(exc).lower()
        if "not available" in message or "pipe not found" in message:
            pytest.skip("Unreal Editor transport is unavailable")
        if "not found" in message:
            pytest.skip("A valid Level Sequence actor is not present in the Unreal fixture")
        raise
