"""Tests for registering Unreal production with the generic dispatcher."""

import pytest

from controller.capability_dispatch import ControllerCapabilityDispatcher
from controller.capability_request import CapabilityRequest
from controller.unreal_production_capability import register_unreal_production_capability
from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_production_runtime_adapter import UnrealProductionRuntimeAdapter
from tests.test_unreal_heterogeneous_production import ProductionTransport


def test_unreal_production_registers_as_named_capability():
    dispatcher = ControllerCapabilityDispatcher()
    integration = UnrealProductionControllerIntegration(
        UnrealProductionRuntimeAdapter(
            UnrealPlanExecutor(UnrealAdapterProduction(ProductionTransport(), "capability-test"))
        )
    )

    register_unreal_production_capability(dispatcher, integration)

    capability = dispatcher.resolve(
        CapabilityRequest(
            capability="production",
            provider="unreal",
            context={"production": True},
        )
    )
    assert capability is not None
    assert capability.name == "unreal_production"
    assert capability.handler is integration


def test_unreal_production_capability_does_not_match_without_explicit_context():
    dispatcher = ControllerCapabilityDispatcher()
    integration = UnrealProductionControllerIntegration(
        UnrealProductionRuntimeAdapter(
            UnrealPlanExecutor(UnrealAdapterProduction(ProductionTransport(), "capability-negative-test"))
        )
    )
    register_unreal_production_capability(dispatcher, integration)

    assert dispatcher.resolve(
        CapabilityRequest(
            capability="production",
            provider="unreal",
            context={},
        )
    ) is None
    assert dispatcher.resolve(
        CapabilityRequest(
            capability="production",
            provider="blender",
            context={"production": True},
        )
    ) is None


def test_registration_rejects_wrong_dependencies():
    dispatcher = ControllerCapabilityDispatcher()
    with pytest.raises(TypeError, match="ControllerCapabilityDispatcher"):
        register_unreal_production_capability(object(), object())
