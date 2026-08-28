"""Tests for the explicit agent-to-controller handoff contract."""

import pytest

from controller.agent_entrypoint_contract import (
    AgentControllerHandoff,
    dispatch_controller_handoff,
)
from controller.agent_entrypoint_runtime import AtlasAgentEntrypointRuntime
from controller.agent_process_runtime import AtlasAgentProcessRuntime
from controller.capability_request import CapabilityRequest


class Handler:
    def execute(self, request):
        return request.normalized_capability


def test_handoff_builds_immutable_explicit_request():
    handoff = AgentControllerHandoff.build(
        "production",
        provider="unreal",
        context={"production": True},
        intent="run the production transaction",
    )

    assert handoff.request.capability == "production"
    assert handoff.request.provider == "unreal"
    assert handoff.request.context == {"production": True}
    assert handoff.request.intent == "run the production transaction"


def test_handoff_dispatches_through_existing_entrypoint_runtime():
    process = AtlasAgentProcessRuntime()
    process.runtime.registry.dispatcher.register(
        "unreal_production",
        lambda request: (
            isinstance(request, CapabilityRequest)
            and request.normalized_provider == "unreal"
            and request.normalized_capability == "production"
            and request.context.get("production") is True
        ),
        Handler(),
    )

    runtime = AtlasAgentEntrypointRuntime(process)
    handoff = AgentControllerHandoff.build(
        "production",
        provider="unreal",
        context={"production": True},
    )

    result = dispatch_controller_handoff(runtime, handoff)

    assert result.controller_executed is True
    assert result.result.value == "production"


def test_handoff_does_not_execute_legacy_route():
    process = AtlasAgentProcessRuntime()
    runtime = AtlasAgentEntrypointRuntime(process)

    handoff = AgentControllerHandoff.build("ordinary task", provider="blender")
    result = dispatch_controller_handoff(runtime, handoff)

    assert result.controller_executed is False
    assert result.result is None


def test_handoff_rejects_wrong_runtime_or_input():
    handoff = AgentControllerHandoff.build("production", provider="unreal")

    with pytest.raises(TypeError, match="AtlasAgentEntrypointRuntime"):
        dispatch_controller_handoff(object(), handoff)

    with pytest.raises(TypeError, match="AgentControllerHandoff"):
        dispatch_controller_handoff(AtlasAgentEntrypointRuntime(AtlasAgentProcessRuntime()), object())
