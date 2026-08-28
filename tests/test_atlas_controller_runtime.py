"""Tests for the outer Atlas controller runtime capability boundary."""

from controller.atlas_controller_runtime import AtlasControllerRuntime
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
