"""Tests for the provider-neutral controller capability registry."""

from controller.capability_dispatch import ControllerCapabilityDispatcher
from controller.capability_registry import ControllerCapabilityRegistry
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration


def test_registry_exposes_one_shared_agent_runtime_over_dispatcher():
    dispatcher = ControllerCapabilityDispatcher()
    registry = ControllerCapabilityRegistry(dispatcher)
    runtime = registry.runtime()

    assert runtime.dispatcher is dispatcher
    assert registry.registered_names() == ()


def test_registry_preserves_existing_dispatcher_registrations():
    dispatcher = ControllerCapabilityDispatcher()
    dispatcher.register("test", lambda request: True, object())
    registry = ControllerCapabilityRegistry(dispatcher)

    assert registry.registered_names() == ("test",)
    assert registry.runtime().resolve("test").matched is True


def test_registry_creates_dispatcher_when_not_supplied():
    registry = ControllerCapabilityRegistry()

    assert isinstance(registry.dispatcher, ControllerCapabilityDispatcher)
    assert registry.registered_names() == ()


def test_registry_can_bootstrap_explicit_unreal_production_capability():
    registry = ControllerCapabilityRegistry()
    integration = object.__new__(UnrealProductionControllerIntegration)

    registry.register_unreal_production(integration)

    assert registry.registered_names() == ("unreal_production",)
    resolution = registry.runtime().resolve(
        "production",
        provider="unreal",
        context={"production": True},
    )
    assert resolution.matched is True
    assert resolution.capability.handler is integration


def test_registry_does_not_match_unreal_without_explicit_production_context():
    registry = ControllerCapabilityRegistry()
    integration = object.__new__(UnrealProductionControllerIntegration)
    registry.register_unreal_production(integration)

    assert registry.runtime().resolve("production", provider="unreal").matched is False
