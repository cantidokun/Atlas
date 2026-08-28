"""Tests for explicit agent capability runtime bootstrap."""

from controller.agent_capability_bootstrap import build_agent_capability_runtime
from controller.atlas_controller_runtime import AtlasControllerRuntime
from controller.capability_registry import ControllerCapabilityRegistry
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration
from planning.unreal_production_runtime_adapter import UnrealProductionRuntimeAdapter
from tests.test_unreal_heterogeneous_production import ProductionTransport


def test_bootstrap_creates_runtime_with_empty_provider_registry():
    runtime = build_agent_capability_runtime()

    assert isinstance(runtime, AtlasControllerRuntime)
    assert runtime.registry.registered_names() == ()


def test_bootstrap_preserves_supplied_registry():
    registry = ControllerCapabilityRegistry()

    runtime = build_agent_capability_runtime(registry)

    assert runtime.registry is registry
    assert runtime.capabilities.dispatcher is registry.dispatcher


def test_bootstrap_wires_explicit_unreal_capability():
    integration = UnrealProductionControllerIntegration(
        UnrealProductionRuntimeAdapter(
            UnrealPlanExecutor(
                UnrealAdapterProduction(ProductionTransport(), "bootstrap-test")
            )
        )
    )

    runtime = build_agent_capability_runtime(unreal_production=integration)
    selected = runtime.resolve_capability(
        "production",
        provider="unreal",
        context={"production": True},
    )

    assert selected.matched is True
    assert selected.capability.name == "unreal_production"
    assert selected.capability.handler is integration
