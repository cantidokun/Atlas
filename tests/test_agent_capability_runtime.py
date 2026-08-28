"""Tests for the provider-neutral agent capability runtime boundary."""

import pytest

from controller.agent_capability_runtime import AgentCapabilityRuntime
from controller.capability_dispatch import ControllerCapabilityDispatcher
from controller.capability_request import CapabilityRequest


def test_agent_runtime_resolves_explicit_capability_without_invoking_handler():
    dispatcher = ControllerCapabilityDispatcher()
    calls = []
    handler = object()

    def predicate(request: CapabilityRequest) -> bool:
        calls.append(request)
        return (
            request.normalized_capability == "production"
            and request.normalized_provider == "unreal"
            and request.context.get("production") is True
        )

    dispatcher.register("unreal_production", predicate, handler)
    runtime = AgentCapabilityRuntime(dispatcher)

    resolution = runtime.resolve(
        "Production",
        provider="Unreal",
        context={"production": True, "job_id": "demo"},
    )

    assert resolution.matched is True
    assert resolution.capability is not None
    assert resolution.capability.handler is handler
    assert resolution.request.normalized_capability == "production"
    assert resolution.request.normalized_provider == "unreal"
    assert resolution.request.context["job_id"] == "demo"
    assert len(calls) == 1


def test_agent_runtime_returns_no_match_without_explicit_provider_or_context():
    dispatcher = ControllerCapabilityDispatcher()
    dispatcher.register(
        "unreal_production",
        lambda request: (
            request.normalized_capability == "production"
            and request.normalized_provider == "unreal"
            and request.context.get("production") is True
        ),
        object(),
    )
    runtime = AgentCapabilityRuntime(dispatcher)

    assert runtime.resolve("production").matched is False
    assert runtime.resolve("production", provider="unreal").matched is False
    assert runtime.resolve("production", provider="blender", context={"production": True}).matched is False


def test_agent_runtime_does_not_execute_resolved_handler():
    dispatcher = ControllerCapabilityDispatcher()
    calls = []

    class Handler:
        def start(self):
            calls.append("start")

    handler = Handler()
    dispatcher.register("test", lambda request: True, handler)
    runtime = AgentCapabilityRuntime(dispatcher)

    resolution = runtime.resolve("test")

    assert resolution.capability is not None
    assert resolution.capability.handler is handler
    assert calls == []


def test_agent_runtime_rejects_invalid_dispatcher():
    with pytest.raises(TypeError, match="ControllerCapabilityDispatcher"):
        AgentCapabilityRuntime(object())
