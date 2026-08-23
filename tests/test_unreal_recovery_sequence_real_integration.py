"""Real Unreal integration coverage for the explicit recovery sequence boundary."""

import pytest

from planning.unreal_adapter_production import create_production_adapter
from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_executor import UnrealPlanExecutionFailure, UnrealPlanExecutor
from planning.unreal_recovery_sequence import (
    assess_reassessment_sequence,
    build_reassessment_plan,
)
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_named_pipe import NamedPipeTransportError


pytestmark = pytest.mark.integration

ENTITY_ID = "FIELD_SURFACE"


def _intent(intent_id: str) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="real Unreal recovery sequence integration",
        target_entity_ids=(ENTITY_ID,),
    )


def _location(evidence):
    return dict(evidence.observed_state[ENTITY_ID]["location"])


def _post_write_failure(target_location):
    return UnrealPlanExecutionFailure(
        intent_id="real-recovery-sequence",
        operation_index=2,
        operation_name="verify_actor_location",
        completed_evidence=(
            UnrealEvidence(
                operation_name="inspect_target_actors",
                entity_ids=(ENTITY_ID,),
                observed_state={ENTITY_ID: {"location": target_location}},
                source="real-recovery-sequence-test",
                verified=False,
            ),
            UnrealEvidence(
                operation_name="set_actor_location",
                entity_ids=(ENTITY_ID,),
                observed_state={ENTITY_ID: {"location": target_location}},
                source="real-recovery-sequence-test",
                verified=False,
            ),
        ),
        error="simulated post-write verification failure",
        operation_entity_ids=(ENTITY_ID,),
        operation_arguments={"entity_ids": (ENTITY_ID,), "expected_location": target_location},
        completed_operation_arguments=(
            {"entity_ids": (ENTITY_ID,)},
            {"entity_ids": (ENTITY_ID,), "location": target_location},
        ),
    )


def test_real_unreal_recovery_sequence_reassesses_live_state_without_retrying_write():
    """Exercise the new recovery-sequence layer against live Unreal state."""
    try:
        adapter = create_production_adapter("recovery-sequence-integration")
        executor = UnrealPlanExecutor(adapter)
        planner = UnrealTaskPlanner()

        original_result = executor.execute(
            planner.plan_inspection(_intent("real-recovery-sequence-original")),
            "real-recovery-sequence-original-auth",
        )
        original_location = _location(original_result.evidence_ledger[0])
        target_location = {
            "x": float(original_location["x"]) + 35.0,
            "y": float(original_location["y"]) + 35.0,
            "z": float(original_location["z"]) + 35.0,
        }

        try:
            write_plan = planner.plan_actor_location_write(
                _intent("real-recovery-sequence-write"),
                target_location,
            )
            write_result = executor.execute(write_plan, "real-recovery-sequence-write-auth")
            assert write_result.success is True

            failure = _post_write_failure(target_location)
            reassessment = build_reassessment_plan(write_plan, failure)
            reassessment_result = executor.execute(
                reassessment,
                "real-recovery-sequence-reassessment-auth",
            )
            assessment = assess_reassessment_sequence(
                write_plan,
                failure,
                reassessment_result,
            )

            assert [operation.name for operation in reassessment.operations] == [
                "inspect_target_actors"
            ]
            assert assessment.disposition == "already_applied"
            assert assessment.steps[0].operation_name == "set_actor_location"
            assert assessment.steps[0].disposition == "already_applied"
            assert _location(reassessment_result.evidence_ledger[0]) == pytest.approx(
                target_location
            )
        finally:
            restore_plan = planner.plan_actor_location_write(
                _intent("real-recovery-sequence-restore"),
                original_location,
            )
            restore_result = executor.execute(
                restore_plan,
                "real-recovery-sequence-restore-auth",
            )
            assert restore_result.success is True
            assert _location(restore_result.evidence_ledger[2]) == pytest.approx(
                original_location
            )

    except NamedPipeTransportError as exc:
        message = str(exc).lower()
        if "not available" in message or "pipe not found" in message:
            pytest.skip("Unreal Editor transport is unavailable")
        if "not found" in message:
            pytest.skip("FIELD_SURFACE actor is not present in the Unreal fixture")
        raise
