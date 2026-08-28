"""Tests for explicit agent-entrypoint task-request construction."""

import pytest

from controller.agent_entrypoint_adapter import build_agent_task_request
from controller.agent_task_request import AgentTaskRequest


def test_adapter_builds_canonical_agent_task_request():
    request = build_agent_task_request(
        "production",
        provider="unreal",
        context={"production": True},
        intent="run production",
    )

    assert isinstance(request, AgentTaskRequest)
    assert request.capability == "production"
    assert request.provider == "unreal"
    assert request.context == {"production": True}
    assert request.intent == "run production"


def test_adapter_copies_context_without_aliasing_input():
    context = {"production": True}
    request = build_agent_task_request("production", context=context)

    context["changed"] = True

    assert request.context == {"production": True}


def test_adapter_defaults_context_to_empty_dictionary():
    request = build_agent_task_request("production")

    assert request.context == {}
    assert request.provider is None
    assert request.intent is None


def test_adapter_rejects_non_dictionary_context():
    with pytest.raises(TypeError, match="context must be a dictionary"):
        build_agent_task_request("production", context=[("production", True)])
