"""Bootstrap registry for controller-owned Atlas capabilities.

The registry centralizes capability registration without coupling the generic
agent runtime to provider-specific implementation details.
"""

from typing import Optional

from controller.agent_capability_runtime import AgentCapabilityRuntime
from controller.capability_dispatch import ControllerCapabilityDispatcher
from controller.unreal_production_capability import register_unreal_production_capability
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration


class ControllerCapabilityRegistry:
    """Own the provider-neutral dispatcher used by the outer runtime."""

    def __init__(self, dispatcher: Optional[ControllerCapabilityDispatcher] = None) -> None:
        self.dispatcher = dispatcher or ControllerCapabilityDispatcher()

    def runtime(self) -> AgentCapabilityRuntime:
        """Return the agent-facing resolver over the current registry."""
        return AgentCapabilityRuntime(self.dispatcher)

    def register_unreal_production(
        self,
        integration: UnrealProductionControllerIntegration,
    ) -> None:
        """Register the explicit Unreal production capability on this registry."""
        register_unreal_production_capability(self.dispatcher, integration)

    def registered_names(self) -> tuple[str, ...]:
        return self.dispatcher.names()
