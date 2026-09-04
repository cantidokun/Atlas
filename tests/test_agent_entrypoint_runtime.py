"""Tests for the explicit Atlas agent-entrypoint execution seam."""

from types import SimpleNamespace

import pytest

from controller.agent_entrypoint_runtime import AtlasAgentEntrypointRuntime
from controller.agent_process_runtime import AtlasAgentProcessRuntime
from controller.agent_task_request import AgentTaskRequest
from controller.capability_execution import CapabilityExecutionResult
from controller.capability_request import CapabilityRequest
from controller.agent_capability_runtime import AgentCapabilityResolution
from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration
from planning.unreal_production_operation import build_unreal_production_plan
from planning.unreal_production_planning_boundary import authorize_production_plan
from planning.unreal_production_runtime_adapter import UnrealProductionRuntimeAdapter
from planning.unreal_plan_executor import UnrealPlanExecutor
from tests.test_unreal_heterogeneous_production import ProductionTransport, _intent, _spec


class Handler:
    def __init__(self):
        self.calls = []

    def execute(self, request):
        self.calls.append(request)
        return "executed"


def _integration():
    return UnrealProductionControllerIntegration(
        UnrealProductionRuntimeAdapter(
            UnrealPlanExecutor(
                UnrealAdapterProduction(ProductionTransport(), "entrypoint-runtime-test")
            )
        )
    )


def test_entrypoint_executes_explicit_controller_route():
    process = AtlasAgentProcessRuntime()
    handler = Handler()
    process.runtime.registry.dispatcher.register(
        "unreal_production",
        lambda request: (
            isinstance(request, CapabilityRequest)
            and request.normalized_provider == "unreal"
            and request.normalized_capability == "production"
            and request.context.get("production") is True
        ),
        handler,
    )

    dispatched = AtlasAgentEntrypointRuntime(process).dispatch(
        AgentTaskRequest(
            capability="production",
            provider="unreal",
            context={"production": True},
        )
    )

    assert dispatched.controller_executed is True
    assert isinstance(dispatched.result, CapabilityExecutionResult)
    assert dispatched.result.capability_name == "unreal_production"
    assert dispatched.result.value == "executed"
    assert dispatched.result_contract is None
    assert len(handler.calls) == 1
    assert isinstance(handler.calls[0], CapabilityRequest)


def test_entrypoint_exposes_engine_neutral_result_contract():
    process = AtlasAgentProcessRuntime()
    contract = object()

    class ContractHandler:
        def execute(self, request):
            return SimpleNamespace(result_contract=contract)

    process.runtime.registry.dispatcher.register(
        "unreal_production",
        lambda request: (
            isinstance(request, CapabilityRequest)
            and request.normalized_provider == "unreal"
            and request.normalized_capability == "production"
            and request.context.get("production") is True
        ),
        ContractHandler(),
    )

    dispatched = AtlasAgentEntrypointRuntime(process).dispatch(
        AgentTaskRequest(
            capability="production",
            provider="unreal",
            context={"production": True},
        )
    )

    assert dispatched.controller_executed is True
    assert dispatched.result_contract is contract


def test_entrypoint_leaves_legacy_route_unexecuted():
    process = AtlasAgentProcessRuntime()

    dispatched = AtlasAgentEntrypointRuntime(process).dispatch(
        AgentTaskRequest("ordinary task", provider="blender")
    )

    assert dispatched.controller_executed is False
    assert dispatched.result is None
    assert dispatched.result_contract is None
    assert dispatched.classified.controller_owned is False


def test_entrypoint_rejects_non_request_input():
    process = AtlasAgentProcessRuntime()

    with pytest.raises(TypeError, match="AgentTaskRequest"):
        AtlasAgentEntrypointRuntime(process).dispatch("production")


def test_entrypoint_executes_real_authorized_unreal_production():
    production = build_unreal_production_plan(_intent(), _spec())
    authorized = authorize_production_plan(production, "entrypoint-production-auth")
    integration = _integration()
    process = AtlasAgentProcessRuntime(unreal_production=integration)

    dispatched = AtlasAgentEntrypointRuntime(process).dispatch(
        AgentTaskRequest(
            capability="production",
            provider="unreal",
            context={
                "production": True,
                "authorized_production": authorized,
            },
        )
    )

    assert dispatched.controller_executed is True
    assert dispatched.result is not None
    assert dispatched.result.capability_name == "unreal_production"
    assert dispatched.result.value.operation == "start"
    assert dispatched.result.value.snapshot.state == "complete"
    assert dispatched.result_contract is not None
    assert dispatched.result_contract.success is True
    assert dispatched.result_contract.verified_render is False
    assert integration.complete is True
