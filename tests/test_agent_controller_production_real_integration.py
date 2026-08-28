"""Live Unreal validation for an agent-originated production request."""

import os

import pytest

from controller.agent_entrypoint_contract import AgentControllerHandoff
from controller.agent_entrypoint_runtime import AtlasAgentEntrypointRuntime
from controller.agent_process_runtime import AtlasAgentProcessRuntime
from planning.agent_controller_production_request import AgentControllerProductionRequest
from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_composite_operation import build_composite_actor_operation
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration
from planning.unreal_production_operation import UnrealProductionSpec, build_unreal_production_plan
from planning.unreal_production_planning_boundary import authorize_production_plan
from planning.unreal_production_runtime_adapter import UnrealProductionRuntimeAdapter
from planning.unreal_render_contract import UnrealRenderConfig
from planning.unreal_transport_named_pipe import NamedPipeTransportError, WindowsNamedPipeTransport
from planning.unreal_task_planner import UnrealTaskIntent


pytestmark = pytest.mark.integration

ENTITY_ID = "FIELD_SURFACE"


def _intent(intent_id: str) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="agent-originated Unreal production request",
        target_entity_ids=(ENTITY_ID,),
    )


def _spec() -> UnrealProductionSpec:
    return UnrealProductionSpec(
        composite=build_composite_actor_operation(
            [ENTITY_ID],
            [
                {"name": "set_actor_location", "location": {"x": 10.0, "y": 20.0, "z": 30.0}},
                {"name": "set_actor_rotation", "rotation": {"pitch": 0.0, "yaw": 15.0, "roll": 0.0}},
                {"name": "set_actor_scale", "scale": {"x": 1.1, "y": 1.1, "z": 1.1}},
                {"name": "apply_material_variant", "variant": "liquid_surface"},
                {"name": "apply_niagara_variant", "variant": "goal_burst"},
            ],
        ),
        start_frame=1,
        end_frame=24,
        render_config=UnrealRenderConfig(
            width=1280,
            height=720,
            start_frame=1,
            end_frame=24,
            output_directory="Saved/AtlasProductionOutput",
            output_format="png",
        ),
    )


def _integration() -> UnrealProductionControllerIntegration:
    return UnrealProductionControllerIntegration(
        UnrealProductionRuntimeAdapter(
            UnrealPlanExecutor(
                UnrealAdapterProduction(
                    WindowsNamedPipeTransport(),
                    "agent-controller-real-integration",
                )
            )
        )
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


def test_real_agent_originated_unreal_request_reaches_live_production_boundary():
    """Send an explicit agent handoff through the controller and into live Unreal."""
    try:
        production = build_unreal_production_plan(_intent("real-agent-production"), _spec())
        authorized = authorize_production_plan(production, "real-agent-production-auth")
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
