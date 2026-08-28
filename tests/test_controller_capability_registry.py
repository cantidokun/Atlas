"""Tests for the provider-neutral controller capability registry."""

from controller.capability_dispatch import ControllerCapabilityDispatcher
from controller.capability_registry import ControllerCapabilityRegistry


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
