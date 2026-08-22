"""Real Unreal integration coverage for the complete plan executor boundary."""

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
        description="integration test actor location write",
        target_entity_ids=(ENTITY_ID,),
    )


def _location(evidence):
    return dict(evidence.observed_state[ENTITY_ID]["location"])


@pytest.mark.skipif(
    not hasattr(create_production_adapter, "__call__"),
    reason="production Unreal adapter unavailable",
)
def test_real_unreal_plan_executor_location_write_and_restore():
    """Execute a complete inspect/write/verify plan against the live Editor.

    The actor is restored to its original location in a finally block so this
    test leaves the Unreal fixture in the same state in which it found it.
    """
    try:
        adapter = create_production_adapter("plan-executor-integration")
        executor = UnrealPlanExecutor(adapter)
        planner = UnrealTaskPlanner()

        inspect_plan = planner.plan_inspection(_intent("real-plan-inspect"))
        original_result = executor.execute(
            inspect_plan,
            "real-plan-inspect-auth",
        )
        original_location = _location(original_result.evidence_ledger[0])

        target_location = {
            "x": float(original_location["x"]) + 25.0,
            "y": float(original_location["y"]) + 25.0,
            "z": float(original_location["z"]) + 25.0,
        }

        try:
            write_plan = planner.plan_actor_location_write(
                _intent("real-plan-write"),
                target_location,
            )
            result = executor.execute(write_plan, "real-plan-write-auth")

            assert result.success is True
            assert len(result.evidence_ledger) == 3
            assert result.evidence_ledger[0].operation_name == "inspect_target_actors"
            assert result.evidence_ledger[1].operation_name == "set_actor_location"
            assert result.evidence_ledger[2].operation_name == "verify_target_actor_mapping"
            assert _location(result.evidence_ledger[2]) == pytest.approx(target_location)
        finally:
            restore_plan = planner.plan_actor_location_write(
                _intent("real-plan-restore"),
                original_location,
            )
            restore_result = executor.execute(restore_plan, "real-plan-restore-auth")
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
