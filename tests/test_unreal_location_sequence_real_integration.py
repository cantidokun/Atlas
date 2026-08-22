"""Real Unreal integration coverage for compound actor-location execution."""

import pytest

from planning.unreal_adapter_production import create_production_adapter
from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_named_pipe import NamedPipeTransportError


pytestmark = pytest.mark.integration

ENTITY_ID = "FIELD_SURFACE"


def _intent(intent_id: str) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="integration test compound actor location sequence",
        target_entity_ids=(ENTITY_ID,),
    )


def _location(evidence):
    return dict(evidence.observed_state[ENTITY_ID]["location"])


def test_real_unreal_location_sequence_executes_in_order_and_restores():
    """Exercise the compound sequence against the running Unreal Editor.

    The test uses two temporary locations, verifies each mutation independently,
    checks the exact wire operation sequence, and restores the original actor
    location in a finally block.
    """
    try:
        adapter = create_production_adapter("location-sequence-integration")
        executor = UnrealPlanExecutor(adapter)
        planner = UnrealTaskPlanner()

        original_result = executor.execute(
            planner.plan_inspection(_intent("real-sequence-original")),
            "real-sequence-original-auth",
        )
        original_location = _location(original_result.evidence_ledger[0])

        first_location = {
            "x": float(original_location["x"]) + 15.0,
            "y": float(original_location["y"]) + 10.0,
            "z": float(original_location["z"]) + 5.0,
        }
        second_location = {
            "x": float(original_location["x"]) - 20.0,
            "y": float(original_location["y"]) + 30.0,
            "z": float(original_location["z"]) + 10.0,
        }

        try:
            plan = planner.plan_actor_location_sequence(
                _intent("real-sequence-write"),
                (first_location, second_location),
            )
            result = executor.execute(plan, "real-sequence-write-auth")

            assert result.success is True
            assert len(result.evidence_ledger) == 5
            assert [evidence.operation_name for evidence in result.evidence_ledger] == [
                "inspect_target_actors",
                "set_actor_location",
                "verify_target_actor_mapping",
                "set_actor_location",
                "verify_target_actor_mapping",
            ]
            assert _location(result.evidence_ledger[2]) == pytest.approx(first_location)
            assert _location(result.evidence_ledger[4]) == pytest.approx(second_location)
            assert _location(result.evidence_ledger[4]) != pytest.approx(first_location)
        finally:
            restore_plan = planner.plan_actor_location_write(
                _intent("real-sequence-restore"),
                original_location,
            )
            restore_result = executor.execute(
                restore_plan,
                "real-sequence-restore-auth",
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
