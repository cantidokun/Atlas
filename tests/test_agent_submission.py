from controller.agent_entrypoint_runtime import AtlasAgentEntrypointRuntime
from controller.agent_process_runtime import (
    AtlasAgentProcessRuntime,
    AgentProcessRouteContext,
)
from controller.agent_task_request import AgentTaskRequest
from controller.agent_submission import submit_agent_task


class StubProcess(AtlasAgentProcessRuntime):
    def __init__(self):
        pass

    def classify(self, request):
        return AgentProcessRouteContext(
            route=type(
                "Route",
                (),
                {
                    "controller_owned": False,
                    "selection": type("Selection", (), {"name": "stub"})(),
                },
            )(),
            runtime=self,
            request=request,
        )


def test_submit_agent_task_builds_and_dispatches_request():
    runtime = AtlasAgentEntrypointRuntime(StubProcess())

    execution = submit_agent_task(
        runtime,
        "production",
        provider="unreal",
        context={
            "production": True,
            "target_entity_ids": ("FIELD_SURFACE",),
        },
        intent="agent-production-001",
    )

    assert execution.controller_executed is False
    request = execution.classified.request

    assert isinstance(request, AgentTaskRequest)
    assert request.capability == "production"
    assert request.provider == "unreal"
    assert request.context["production"] is True
    assert request.context["target_entity_ids"] == ("FIELD_SURFACE",)
    assert request.intent == "agent-production-001"


def test_submit_agent_task_preserves_non_controller_intent():
    runtime = AtlasAgentEntrypointRuntime(StubProcess())

    execution = submit_agent_task(
        runtime,
        "blender",
        provider="blender",
        intent="legacy-blender-001",
    )

    assert execution.controller_executed is False
    request = execution.classified.request

    assert request.capability == "blender"
    assert request.provider == "blender"
    assert request.intent == "legacy-blender-001"


def test_submit_agent_task_rejects_invalid_runtime():
    try:
        submit_agent_task(object(), "production")
    except TypeError as exc:
        assert "AtlasAgentEntrypointRuntime" in str(exc)
    else:
        raise AssertionError("invalid runtime should fail closed")
