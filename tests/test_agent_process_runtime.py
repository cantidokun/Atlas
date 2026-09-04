"""Tests for the optional Atlas agent-process capability routing boundary."""

import pytest

from controller.agent_process_runtime import AtlasAgentProcessRuntime, AgentProcessRouteContext
from controller.agent_task_request import AgentTaskRequest
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration
from planning.unreal_production_operation import build_unreal_production_plan
from planning.unreal_production_planning_boundary import authorize_production_plan
from planning.unreal_production_runtime_adapter import UnrealProductionRuntimeAdapter
from planning.unreal_adapter_production import UnrealAdapterProduction
from tests.test_unreal_heterogeneous_production import ProductionTransport, _intent, _spec


def _integration():
    return UnrealProductionControllerIntegration(
        UnrealProductionRuntimeAdapter(
            UnrealPlanExecutor(
                UnrealAdapterProduction(ProductionTransport(), "agent-process-runtime-test")
            )
        )
    )


def _authorized_production():
    production = build_unreal_production_plan(_intent(), _spec())
    return authorize_production_plan(production, "agent-process-runtime-auth")


def test_agent_process_routes_explicit_unreal_production_to_controller():
    process = AtlasAgentProcessRuntime(unreal_production=_integration())

    routed = process.route(
        "production",
        provider="unreal",
        context={
            "production": True,
            "authorized_production": _authorized_production(),
        },
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
        context={
            "production": True,
            "authorized_production": _authorized_production(),
        },
    )

    assert integration.complete is False


def test_agent_process_executes_classified_explicit_unreal_production():
    production = build_unreal_production_plan(_intent(), _spec())
    authorized = authorize_production_plan(production, "production-auth")
    process = AtlasAgentProcessRuntime(unreal_production=_integration())

    classified = process.classify(
        AgentTaskRequest(
            capability="production",
            provider="unreal",
            context={
                "production": True,
                "authorized_production": authorized,
            },
        )
    )

    assert isinstance(classified, AgentProcessRouteContext)
    result = process.execute_classified(classified)

    assert result.capability_name == "unreal_production"
    assert result.value.operation == "start"
    assert result.value.snapshot.state == "complete"


def test_agent_process_refuses_execution_of_legacy_route():
    process = AtlasAgentProcessRuntime(unreal_production=_integration())
    classified = process.route("ordinary task", provider="blender", context={})

    with pytest.raises(ValueError, match="controller-owned"):
        process.execute_classified(classified)


def test_agent_process_refuses_raw_request_for_classified_execution():
    process = AtlasAgentProcessRuntime(unreal_production=_integration())

    with pytest.raises(TypeError, match="AgentProcessRouteContext"):
        process.execute_classified(AgentTaskRequest("production"))
