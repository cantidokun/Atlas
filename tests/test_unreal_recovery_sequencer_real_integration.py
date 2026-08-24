"""Real Unreal integration coverage for Sequencer recovery reassessment."""

import pytest

from planning.unreal_adapter_production import create_production_adapter
from planning.unreal_agent import (
    UnrealCapability,
    UnrealOperation,
    UnrealOperationKind,
    UnrealTaskIntent,
)
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_executor import UnrealPlanExecutionFailure, UnrealPlanExecutor
from planning.unreal_recovery_sequence import assess_reassessment_sequence, build_reassessment_plan
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner
from planning.unreal_transport_named_pipe import NamedPipeTransportError


pytestmark = pytest.mark.integration

ENTITY_ID = "FIELD_SURFACE"


def _intent(intent_id: str) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="real Unreal Sequencer recovery integration",
        target_entity_ids=(ENTITY_ID,),
    )


def _inspection_plan(intent):
    """Build the explicit Sequencer read used for live state capture."""
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


def _post_write_failure(target_state):
    return UnrealPlanExecutionFailure(
        intent_id="real-sequencer-recovery",
        operation_index=2,
        operation_name="verify_sequencer_playback_range",
        completed_evidence=(
            UnrealEvidence(
                operation_name="inspect_sequencer_state",
                entity_ids=(ENTITY_ID,),
                observed_state={ENTITY_ID: {"entity_id": ENTITY_ID, "sequencer": dict(target_state)}},
                source="real-sequencer-recovery-test",
                verified=False,
            ),
            UnrealEvidence(
                operation_name="set_sequencer_playback_range",
                entity_ids=(ENTITY_ID,),
                observed_state={ENTITY_ID: {"entity_id": ENTITY_ID, "sequencer": dict(target_state)}},
                source="real-sequencer-recovery-test",
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


def test_real_unreal_sequencer_recovery_reassesses_live_state_without_retrying_write():
    """Exercise live Sequencer reassessment after a simulated post-write failure."""
    try:
        adapter = create_production_adapter("sequencer-recovery-integration")
        executor = UnrealPlanExecutor(adapter)
        planner = UnrealTaskPlanner()

        original_result = executor.execute(
            _inspection_plan(_intent("real-sequencer-recovery-original")),
            "real-sequencer-recovery-original-auth",
        )
        original_state = _sequencer_state(original_result.evidence_ledger[0])

        target_start = original_state["start_frame"] + 10
        target_end = original_state["end_frame"] + 10
        target_state = {"start_frame": target_start, "end_frame": target_end}

        try:
            write_plan = planner.plan_sequencer_playback_range(
                _intent("real-sequencer-recovery-write"),
                target_start,
                target_end,
            )
            write_result = executor.execute(
                write_plan,
                "real-sequencer-recovery-write-auth",
            )
            assert write_result.success is True
            assert _sequencer_state(write_result.evidence_ledger[2]) == target_state

            failure = _post_write_failure(target_state)
            reassessment = build_reassessment_plan(write_plan, failure)
            assert [operation.name for operation in reassessment.operations] == [
                "inspect_sequencer_state"
            ]

            reassessment_result = executor.execute(
                reassessment,
                "real-sequencer-recovery-reassessment-auth",
            )
            assessment = assess_reassessment_sequence(
                write_plan,
                failure,
                reassessment_result,
            )

            assert assessment.disposition == "already_applied"
            assert assessment.steps[0].operation_name == "set_sequencer_playback_range"
            assert assessment.steps[0].disposition == "already_applied"
            assert _sequencer_state(reassessment_result.evidence_ledger[0]) == target_state
        finally:
            restore_plan = planner.plan_sequencer_playback_range(
                _intent("real-sequencer-recovery-restore"),
                original_state["start_frame"],
                original_state["end_frame"],
            )
            restore_result = executor.execute(
                restore_plan,
                "real-sequencer-recovery-restore-auth",
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
