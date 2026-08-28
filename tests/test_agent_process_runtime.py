"""Tests for the optional Atlas agent-process capability routing boundary."""

from controller.agent_process_runtime import AtlasAgentProcessRuntime
from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration
from planning.unreal_production_runtime_adapter import UnrealProductionRuntimeAdapter
from tests.test_unreal_heterogeneous_production import ProductionTransport


def _integration():
    return UnrealProductionControllerIntegration(
        UnrealProductionRuntimeAdapter(
            UnrealPlanExecutor(
                UnrealAdapterProduction(ProductionTransport(), "agent-process-runtime-test")
            )
        )
    )


def test_agent_process_routes_explicit_unreal_production_to_controller():
    process = AtlasAgentProcessRuntime(unreal_production=_integration())

    routed = process.route(
        "production",
        provider="unreal",
        context={"production": True},
    )

    assert routed.route.route == "controller"
    assert routed.route.controller_owned is True
    assert routed.route.selection.name == "unreal_production"


def test_agent_process_routes_unmatched_requests_to_legacy_agent_path():
    process = AtlasAgentProcessRuntime(unreal_production=_integration())

    routed = process.route("ordinary task", provider="blender", context={})

    assert routed.route.route == "agent"
    assert routed.route.controller_owned is False
    assert routed.route.selection.matched is False


def test_agent_process_routing_does_not_execute_capability():
    integration = _integration()
    process = AtlasAgentProcessRuntime(unreal_production=integration)

    process.route(
        "production",
        provider="unreal",
        context={"production": True},
    )

    assert integration.complete is False
