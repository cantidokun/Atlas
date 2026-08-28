"""Live Unreal validation for an agent-originated production request."""

import os

import pytest

from controller.agent_entrypoint_contract import AgentControllerHandoff
from controller.agent_entrypoint_runtime import AtlasAgentEntrypointRuntime
from controller.agent_process_runtime import AtlasAgentProcessRuntime
from planning.agent_controller_production_request import AgentControllerProductionRequest
from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration
from planning.unreal_production_operation import build_unreal_production_plan
from planning.unreal_production_planning_boundary import authorize_production_plan
from planning.unreal_production_runtime_adapter import UnrealProductionRuntimeAdapter
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlan
from planning.unreal_transport_named_pipe import NamedPipeTransportError


pytestmark = pytest.mark.integration

ENTITY_ID = "ATLAS_BLUEPRINT_TEST"
ASSET_PATH = os.environ.get(
    "ATLAS_TEST_BLUEPRINT_ASSET",
    "/Game/AtlasTest/BP_AtlasTest.BP_AtlasTest",
)


def _assert_transport_available(exc: Exception) -> None:
    current = exc
    messages = []
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        messages.append(str(current).lower())
        current = current.__cause__ or current.__context__
    message = " | ".join(messages)
    if "not available" in message or "pipe not found" in message or "disconnected" in message:
        pytest.skip("Unreal Editor transport is unavailable")


def _intent(intent_id: str):
    from planning.unreal_agent import UnrealTaskIntent

    return UnrealTaskIntent(
        intent_id=intent_id,
        description="agent-originated Unreal production request",
        target_entity_ids=(ENTITY_ID,),
    )


def _spec():
    from planning.unreal_production_operation import UnrealProductionSpec

    return UnrealProductionSpec(
        entity_ids=(ENTITY_ID,),
        location=(1.0, 2.0, 3.0),
        rotation=(0.0, 0.0, 0.0),
        scale=(1.0, 1.0, 1.0),
        material_variant="Default",
        niagara_variant="Default",
    )


def _integration() -> UnrealProductionControllerIntegration:
    from planning.unreal_transport_named_pipe import WindowsNamedPipeTransport

    transport = WindowsNamedPipeTransport()
    return UnrealProductionControllerIntegration(
        UnrealProductionRuntimeAdapter(
            UnrealPlanExecutor(
                UnrealAdapterProduction(transport, "agent-controller-real-integration")
            )
        )
    )


def test_real_agent_originated_unreal_request_reaches_live_production_boundary():
    """Send an explicit agent handoff through the controller and into live Unreal."""
    try:
        production = build_unreal_production_plan(_intent("real-agent-production"), _spec())
        authorized = authorize_production_plan(
            production,
            "real-agent-production-auth",
        )
        integration = _integration()
        process = AtlasAgentProcessRuntime(unreal_production=integration)
        entrypoint = AtlasAgentEntrypointRuntime(process)
        handoff = AgentControllerHandoff.from_fields(
            capability="production",
            provider="unreal",
            target_entity_ids=(ENTITY_ID,),
            intent_id="real-agent-production",
            description="agent-originated live Unreal production request",
            context={
                "production": True,
                "authorized_production": authorized,
            },
        )

        execution = AgentControllerProductionRequest(entrypoint).submit(handoff)

        assert execution.controller_executed is True
        assert execution.result is not None
        assert execution.result.capability_name == "unreal_production"
        assert execution.result.value.operation == "start"
        assert execution.result.value.snapshot.state == "complete"
        assert integration.complete is True
    except NamedPipeTransportError as exc:
        _assert_transport_available(exc)
        raise
