"""End-to-end Python boundary test for an agent-originated Unreal request."""

from controller.agent_entrypoint_contract import AgentControllerHandoff
from controller.agent_entrypoint_runtime import AtlasAgentEntrypointRuntime
from controller.agent_process_runtime import AtlasAgentProcessRuntime
from controller.capability_request import CapabilityRequest
from planning.agent_controller_production_request import AgentControllerProductionRequest
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration
from planning.unreal_production_operation import build_unreal_production_plan
from planning.unreal_production_planning_boundary import authorize_production_plan
from tests.test_unreal_heterogeneous_production import _intent, _spec


class FakeUnrealProduction(UnrealProductionControllerIntegration):
    def __init__(self):
        self.calls = []

    def execute(self, request):
        assert isinstance(request, CapabilityRequest)
        self.calls.append(request)
        return {"status": "executed", "capability": request.normalized_capability}


def test_agent_originated_unreal_request_reaches_controller_execution_once():
    integration = FakeUnrealProduction()
    process = AtlasAgentProcessRuntime(unreal_production=integration)
    entrypoint = AtlasAgentEntrypointRuntime(process)
    authorized = authorize_production_plan(
        build_unreal_production_plan(_intent(), _spec()),
        "agent-production-auth",
    )
    handoff = AgentControllerHandoff.from_fields(
        capability="production",
        provider="unreal",
        target_entity_ids=("FIELD_SURFACE",),
        intent_id="agent-production-001",
        description="agent-originated Unreal production request",
        context={
            "production": True,
            "authorized_production": authorized,
        },
    )

    execution = AgentControllerProductionRequest(entrypoint).submit(handoff)

    assert execution.controller_executed is True
    assert execution.result.value == {
        "status": "executed",
        "capability": "production",
    }
    assert len(integration.calls) == 1
    request = integration.calls[0]
    assert request.normalized_provider == "unreal"
    assert request.normalized_capability == "production"
    assert request.context["target_entity_ids"] == ("FIELD_SURFACE",)
    assert request.context["intent_id"] == "agent-production-001"


def test_agent_originated_legacy_route_never_reaches_controller_execution():
    integration = FakeUnrealProduction()
    process = AtlasAgentProcessRuntime(unreal_production=integration)
    entrypoint = AtlasAgentEntrypointRuntime(process)
    handoff = AgentControllerHandoff.from_fields(
        capability="blender",
        provider="blender",
        intent_id="legacy-blender-001",
    )

    execution = AgentControllerProductionRequest(entrypoint).submit(handoff)

    assert execution.controller_executed is False
    assert execution.result is None
    assert integration.calls == []
