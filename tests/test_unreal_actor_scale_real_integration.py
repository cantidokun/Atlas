import pytest

from planning.unreal_adapter_production import UnrealAdapterError, UnrealAdapterProduction
from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_named_pipe import NamedPipeTransportError, create_named_pipe_transport


pytestmark = pytest.mark.integration

ENTITY_ID = "FIELD_SURFACE"


def _intent(intent_id):
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="live Unreal actor scale semantic verification",
        target_entity_ids=(ENTITY_ID,),
    )


def _scale(evidence):
    return dict(evidence.observed_state[ENTITY_ID]["scale"])


def test_real_unreal_actor_scale_write_verifies_and_restores():
    transport = None
    original_scale = None
    try:
        transport = create_named_pipe_transport()
        executor = UnrealPlanExecutor(UnrealAdapterProduction(transport, "scale-integration"))
        planner = UnrealTaskPlanner()

        original = executor.execute(planner.plan_inspection(_intent("scale-original")), "scale-original-auth")
        original_scale = _scale(original.evidence_ledger[0])
        target = {
            "x": float(original_scale["x"]) * 1.25,
            "y": float(original_scale["y"]) * 0.75,
            "z": float(original_scale["z"]) * 1.5,
        }

        result = executor.execute(
            planner.plan_actor_scale_write(_intent("scale-live"), target),
            "scale-live-auth",
        )

        assert result.success is True
        assert _scale(result.evidence_ledger[2]) == pytest.approx(target)

    except (UnrealAdapterError, NamedPipeTransportError) as exc:
        message = str(exc).lower()
        if "not available" in message:
            pytest.skip("Unreal Editor transport is unavailable")
        if "actor not found" in message or "not found" in message:
            pytest.skip("FIELD_SURFACE actor is not present in the Unreal fixture")
        raise
    finally:
        if transport is not None and original_scale is not None:
            try:
                UnrealPlanExecutor(UnrealAdapterProduction(transport, "scale-restore")).execute(
                    UnrealTaskPlanner().plan_actor_scale_write(_intent("scale-restore"), original_scale),
                    "scale-restore-auth",
                )
            except (UnrealAdapterError, NamedPipeTransportError):
                pass
