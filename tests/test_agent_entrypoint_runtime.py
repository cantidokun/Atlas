"""Tests for the explicit Atlas agent-entrypoint execution seam."""

import pytest

from controller.agent_entrypoint_runtime import AtlasAgentEntrypointRuntime
from controller.agent_process_runtime import AtlasAgentProcessRuntime
from controller.agent_task_request import AgentTaskRequest
from controller.capability_execution import CapabilityExecutionResult
from controller.capability_request import CapabilityRequest


class Handler:
    def __init__(self):
        self.calls = []

    def execute(self, request):
        self.calls.append(request)
        return "executed"


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
    assert len(handler.calls) == 1
    assert isinstance(handler.calls[0], CapabilityRequest)


def test_entrypoint_leaves_legacy_route_unexecuted():
    process = AtlasAgentProcessRuntime()

    dispatched = AtlasAgentEntrypointRuntime(process).dispatch(
        AgentTaskRequest("ordinary task", provider="blender")
    )

    assert dispatched.controller_executed is False
    assert dispatched.result is None
    assert dispatched.classified.controller_owned is False


def test_entrypoint_rejects_non_request_input():
    process = AtlasAgentProcessRuntime()

    with pytest.raises(TypeError, match="AgentTaskRequest"):
        AtlasAgentEntrypointRuntime(process).dispatch("production")
