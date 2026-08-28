"""Tests for the outer Atlas controller runtime capability boundary."""

import pytest

from controller.agent_task_request import AgentTaskRequest
from controller.atlas_controller_runtime import AtlasControllerRuntime
from controller.capability_admission import CapabilityAdmission
from controller.capability_execution import CapabilityExecutionResult
from controller.capability_registry import ControllerCapabilityRegistry
from controller.capability_request import CapabilityRequest


def test_runtime_bootstraps_one_shared_capability_registry():
    runtime = AtlasControllerRuntime()

    assert isinstance(runtime.registry, ControllerCapabilityRegistry)
    assert runtime.capabilities.dispatcher is runtime.registry.dispatcher
    assert runtime.registry.registered_names() == ()


def test_runtime_resolves_only_explicit_unreal_production_requests():
    runtime = AtlasControllerRuntime()

    class Handler:
        pass

    handler = Handler()
    runtime.registry.dispatcher.register(
        "unreal_production",
        lambda request: (
            isinstance(request, CapabilityRequest)
            and request.normalized_provider == "unreal"
            and request.normalized_capability == "production"
            and request.context.get("production") is True
        ),
        handler,
    )

    resolved = runtime.resolve_capability(
        "production",
        provider="unreal",
        context={"production": True},
    )
    assert resolved.matched is True
    assert resolved.capability.handler is handler

    not_resolved = runtime.resolve_capability("production", provider="unreal")
    assert not_resolved.matched is False


def test_resolution_does_not_invoke_registered_handler():
    runtime = AtlasControllerRuntime()
    calls = []

    runtime.registry.dispatcher.register(
        "test",
        lambda request: True,
        lambda: calls.append("executed"),
    )

    resolved = runtime.resolve_capability("test")

    assert resolved.matched is True
    assert calls == []


def test_runtime_selects_immutable_capability_result():
    runtime = AtlasControllerRuntime()
    handler = object()
    runtime.registry.dispatcher.register("test", lambda request: True, handler)

    selection = runtime.select_capability("test")

    assert selection.matched is True
    assert selection.name == "test"
    assert selection.handler is handler
    assert selection.resolution.request.normalized_capability == "test"
    assert selection.resolution.request.provider is None


def test_runtime_admits_and_executes_through_one_capability_boundary():
    runtime = AtlasControllerRuntime()
    calls = []

    class Handler:
        def execute(self, request):
            calls.append(request)
            return {
                "status": "executed",
                "capability": request.normalized_capability,
            }

    handler = Handler()
    runtime.registry.dispatcher.register(
        "test",
        lambda request: request.normalized_capability == "test",
        handler,
    )

    request = AgentTaskRequest("test")
    admission = runtime.admit_capability(request)

    assert isinstance(admission, CapabilityAdmission)
    assert admission.name == "test"
    assert admission.handler is handler
    assert calls == []

    result = runtime.execute_admitted(admission)

    assert isinstance(result, CapabilityExecutionResult)
    assert result.capability_name == "test"
    assert result.value == {
        "status": "executed",
        "capability": "test",
    }
    assert calls == [admission.request]


def test_runtime_execute_request_chains_admission_and_execution():
    runtime = AtlasControllerRuntime()
    calls = []

    class Handler:
        def execute(self, request):
            calls.append(request)
            return request.normalized_capability

    handler = Handler()
    runtime.registry.dispatcher.register(
        "test",
        lambda request: request.normalized_capability == "test",
        handler,
    )

    request = AgentTaskRequest("test")
    result = runtime.execute_request(request)

    assert isinstance(result, CapabilityExecutionResult)
    assert result.capability_name == "test"
    assert result.value == "test"
    assert len(calls) == 1
    assert isinstance(calls[0], CapabilityRequest)
    assert calls[0].normalized_capability == request.capability
    assert calls[0] is not request


def test_runtime_execution_rejects_raw_agent_request():
    runtime = AtlasControllerRuntime()

    with pytest.raises(TypeError, match="CapabilityAdmission"):
        runtime.execute_admitted(AgentTaskRequest("test"))
