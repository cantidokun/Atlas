"""Real Unreal integration coverage for the Movie Render Pipeline boundary."""

import pytest

from planning.unreal_adapter_production import create_production_adapter
from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_transport_named_pipe import NamedPipeTransportError
from planning.unreal_task_planner import UnrealTaskPlanner

pytestmark = pytest.mark.integration

ENTITY_ID = "ATLAS_RENDER_TEST"
CONFIG = {
    "width": 1280,
    "height": 720,
    "start_frame": 1,
    "end_frame": 24,
    "output_directory": "Saved/AtlasRenderOutput",
    "output_format": "png",
}


def _intent(intent_id: str) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="real Unreal Movie Render Pipeline production integration",
        target_entity_ids=(ENTITY_ID,),
    )


def _render_state(evidence):
    return evidence.observed_state[ENTITY_ID]["render"]


def _skip_unavailable(exc: Exception):
    message = str(exc).lower()
    if any(token in message for token in ("pipe not found", "not available", "disconnected")):
        pytest.skip("Unreal Editor transport is unavailable")


def test_real_unreal_render_configuration_persists_and_verifies():
    try:
        adapter = create_production_adapter("render-production-integration")
        executor = UnrealPlanExecutor(adapter)
        planner = UnrealTaskPlanner()
        plan = planner.plan_render_configuration(_intent("real-render-configuration"), CONFIG)
        assert [operation.name for operation in plan.operations] == [
            "inspect_render_state",
            "configure_render",
            "verify_render_state",
        ]
        result = executor.execute(plan, "real-render-configuration-auth")
        assert result.success is True
        assert _render_state(result.evidence_ledger[1])["width"] == CONFIG["width"]
        assert _render_state(result.evidence_ledger[1])["height"] == CONFIG["height"]
        assert _render_state(result.evidence_ledger[1])["start_frame"] == CONFIG["start_frame"]
        assert _render_state(result.evidence_ledger[1])["end_frame"] == CONFIG["end_frame"]
        assert _render_state(result.evidence_ledger[1])["output_format"] == "png"
        assert _render_state(result.evidence_ledger[2]) == _render_state(result.evidence_ledger[1])
        fresh = executor.execute(
            planner.plan_render_configuration(_intent("real-render-fresh-inspection"), CONFIG)[:1] and
            __import__("planning.unreal_task_planner", fromlist=["UnrealTaskPlan"]).UnrealTaskPlan(
                "real-render-fresh-inspection",
                (plan.operations[0],),
            ),
            "real-render-fresh-auth",
        )
        assert _render_state(fresh.evidence_ledger[0])["width"] == CONFIG["width"]
        assert _render_state(fresh.evidence_ledger[0])["height"] == CONFIG["height"]
    except (NamedPipeTransportError, UnrealPlanExecutionError) as exc:
        _skip_unavailable(exc)
        if "Render config asset not found" in str(exc):
            pytest.skip("Run AtlasRenderFixture commandlet before real render integration")
        raise
