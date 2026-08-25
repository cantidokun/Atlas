"""Live Unreal proof for actor rotation mutation and restoration."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction, UnrealAdapterError
from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_named_pipe import NamedPipeTransportError, create_named_pipe_transport


pytestmark = pytest.mark.integration

ENTITY_ID = "FIELD_SURFACE"


def _intent(intent_id: str) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="integration test actor rotation mutation",
        target_entity_ids=(ENTITY_ID,),
    )


def _rotation(evidence):
    return dict(evidence.observed_state[ENTITY_ID]["rotation"])


def test_real_unreal_actor_rotation_applies_verifies_and_restores():
    """Prove rotation mutation and independent verification against real Unreal."""
    transport = create_named_pipe_transport()
    adapter = UnrealAdapterProduction(transport, "actor-rotation-integration")
    executor = UnrealPlanExecutor(adapter)
    planner = UnrealTaskPlanner()
    original_rotation = None

    try:
        original_result = executor.execute(
            planner.plan_inspection(_intent("rotation-original-read")),
            "rotation-original-read-auth",
        )
        original_rotation = _rotation(original_result.evidence_ledger[0])
        target_rotation = {
            "pitch": float(original_rotation["pitch"]) + 11.0,
            "yaw": float(original_rotation["yaw"]) + 37.0,
            "roll": float(original_rotation["roll"]) - 9.0,
        }

        result = executor.execute(
            planner.plan_actor_rotation_write(_intent("rotation-live"), target_rotation),
            "rotation-live-auth",
        )

        assert result.success is True
        assert [evidence.operation_name for evidence in result.evidence_ledger] == [
            "inspect_target_actors",
            "set_actor_rotation",
            "verify_actor_rotation",
        ]
        assert _rotation(result.evidence_ledger[1]) == pytest.approx(target_rotation)
        assert _rotation(result.evidence_ledger[2]) == pytest.approx(target_rotation)

    except (UnrealAdapterError, NamedPipeTransportError) as exc:
        message = str(exc).lower()
        if "not available" in message:
            pytest.skip("Unreal Editor transport is unavailable")
        if "actor not found" in message or "not found" in message:
            pytest.skip("FIELD_SURFACE actor is not present in the Unreal fixture")
        raise
    finally:
        if original_rotation is not None:
            restore_result = executor.execute(
                planner.plan_actor_rotation_write(_intent("rotation-restore"), original_rotation),
                "rotation-restore-auth",
            )
            assert restore_result.success is True
            assert _rotation(restore_result.evidence_ledger[2]) == pytest.approx(original_rotation)
