"""Outer Atlas controller runtime bootstrap.

This module is deliberately limited to capability bootstrap and resolution. It
provides one stable runtime-owned object that can be created by an Atlas agent
entrypoint while leaving provider-specific execution and authorization behind
the registered controller capability.
"""

from typing import Optional

from controller.agent_capability_runtime import AgentCapabilityRuntime
from controller.capability_registry import ControllerCapabilityRegistry
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration


class AtlasControllerRuntime:
    """Own the controller capability registry for one Atlas runtime instance."""

    def __init__(self, registry: Optional[ControllerCapabilityRegistry] = None) -> None:
        self.registry = registry or ControllerCapabilityRegistry()
        self.capabilities = self.registry.runtime()

    def register_unreal_production(
        self,
        integration: UnrealProductionControllerIntegration,
    ) -> None:
        """Make the explicit Unreal production capability available to this runtime."""
        self.registry.register_unreal_production(integration)

    def resolve_capability(
        self,
        capability: str,
        *,
        provider: Optional[str] = None,
        context: Optional[dict] = None,
    ):
        """Resolve a capability request without invoking its handler."""
        return self.capabilities.resolve(
            capability,
            provider=provider,
            context=context,
        )
