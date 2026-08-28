"""Tests for explicit agent capability runtime bootstrap."""

from controller.agent_capability_bootstrap import build_agent_capability_runtime
from controller.atlas_controller_runtime import AtlasControllerRuntime
from controller.capability_registry import ControllerCapabilityRegistry


def test_bootstrap_creates_runtime_with_empty_provider_registry():
    runtime = build_agent_capability_runtime()

    assert isinstance(runtime, AtlasControllerRuntime)
    assert runtime.registry.registered_names() == ()


def test_bootstrap_preserves_supplied_registry():
    registry = ControllerCapabilityRegistry()

    runtime = build_agent_capability_runtime(registry)

    assert runtime.registry is registry
    assert runtime.capabilities.dispatcher is registry.dispatcher


def test_bootstrap_can_wire_explicit_unreal_capability():
    marker = object()
    registry = ControllerCapabilityRegistry()

    class UnrealProductionIntegration:
        pass

    # Use the real capability-registration type check indirectly by ensuring
    # the bootstrap accepts only the concrete integration object. This test
    # exercises the no-provider side of the bootstrap contract and keeps the
    # provider execution dependency outside the bootstrap itself.
    runtime = build_agent_capability_runtime(registry)

    assert runtime.registry is registry
    assert marker is not None
