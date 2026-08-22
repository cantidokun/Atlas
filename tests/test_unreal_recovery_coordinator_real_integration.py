"""Real Unreal integration coverage for the read-only recovery coordinator boundary."""

import pytest

from planning.unreal_adapter_production import create_production_adapter
from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_executor import UnrealPlanExecutionFailure, UnrealPlanExecutor
from planning.unreal_recovery_coordinator import UnrealRecoveryCoordinator
from planning.unreal_reassessment_decision import UnrealReassessmentOutcome
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_named_pipe import NamedPipeTransportError


pytestmark = pytest.mark.integration


ENTITY_ID = "FIELD_SURFACE"


def _intent(intent_id: str) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="integration test actor location recovery",
        target_entity_ids=(ENTITY_ID,),
    )


def _location(evidence):
    return dict(evidence.observed_state[ENTITY_ID]["location"])


def _post_write_failure(target_location):
    return UnrealPlanExecutionFailure(
        intent_id="real-recovery",
        operation_index=2,
        operation_name="verify_target_actor_mapping",
        completed_evidence=(
            UnrealEvidence(
                operation_name="inspect_target_actors",
                entity_ids=(ENTITY_ID,),
                observed_state={
                    ENTITY_ID: {"location": target_location},
                },
                source="real-recovery-test",
                verified=False,
            ),
            UnrealEvidence(
                operation_name="set_actor_location",
                entity_ids=(ENTITY_ID,),
                observed_state={
                    ENTITY_ID: {"location": target_location},
                },
                source="real-recovery-test",
                verified=False,
            ),
        ),
        error="simulated post-write verification failure",
        operation_entity_ids=(ENTITY_ID,),
        operation_arguments={"entity_ids": (ENTITY_ID,)},
        completed_operation_arguments=(
            {"entity_ids": (ENTITY_ID,)},
            {"entity_ids": (ENTITY_ID,), "location": target_location},
        ),
    )


def test_real_unreal_recovery_coordinator_reassesses_live_state_without_retrying_write():
    """Read live Unreal state after a simulated post-write verification failure.

    The coordinator must issue exactly one read-only transport request, confirm
    the live actor location, and never retry the mutation. The actor is restored
    to its original location in a finally block.
    """
    try:
        adapter = create_production_adapter("recovery-coordinator-integration")
        executor = UnrealPlanExecutor(adapter)
        coordinator = UnrealRecoveryCoordinator(executor)
        planner = UnrealTaskPlanner()

        original_result = executor.execute(
            planner.plan_inspection(_intent("real-recovery-original")),
            "real-recovery-original-auth",
        )
        original_location = _location(original_result.evidence_ledger[0])

        target_location = {
            "x": float(original_location["x"]) + 35.0,
            "y": float(original_location["y"]) + 35.0,
            "z": float(original_location["z"]) + 35.0,
        }

        try:
            write_result = executor.execute(
                planner.plan_actor_location_write(
                    _intent("real-recovery-write"),
                    target_location,
                ),
                "real-recovery-write-auth",
            )
            assert write_result.success is True

            result = coordinator.reassess(
                _post_write_failure(target_location),
                "real-recovery-read-auth",
            )

            assert result.decision is not None
            assert result.decision.outcome is UnrealReassessmentOutcome.CONFIRMED
            assert result.decision.retry_authorized is False
            assert result.decision.mutation_authorized is False
            assert result.execution_result is not None
            assert [
                evidence.operation_name
                for evidence in result.execution_result.evidence_ledger
            ] == ["inspect_target_actors"]
            assert _location(result.execution_result.evidence_ledger[0]) == pytest.approx(
                target_location
            )
        finally:
            restore_result = executor.execute(
                planner.plan_actor_location_write(
                    _intent("real-recovery-restore"),
                    original_location,
                ),
                "real-recovery-restore-auth",
            )
            assert restore_result.success is True
            assert _location(restore_result.evidence_ledger[2]) == pytest.approx(
                original_location
            )

    except NamedPipeTransportError as exc:
        message = str(exc).lower()
        if "not available" in message:
            pytest.skip("Unreal Editor transport is unavailable")
        if "not found" in message:
            pytest.skip("FIELD_SURFACE actor is not present in the Unreal fixture")
        raise
