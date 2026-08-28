"""Outer Atlas controller runtime bootstrap.

This module is deliberately limited to capability bootstrap and resolution. It
provides one stable runtime-owned object that can be created by an Atlas agent
entrypoint while leaving provider-specific execution and authorization behind
the registered controller capability.
"""

from typing import Optional

from controller.agent_capability_runtime import AgentCapabilityRuntime
from controller.capability_admission import CapabilityAdmission, ControllerCapabilityAdmission
from controller.capability_execution import CapabilityExecutionResult, ControllerCapabilityExecutor
from controller.capability_registry import ControllerCapabilityRegistry
from controller.capability_selection import CapabilitySelection
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration


class AtlasControllerRuntime:
    """Own the controller capability registry for one Atlas runtime instance."""

    def __init__(self, registry: Optional[ControllerCapabilityRegistry] = None) -> None:
        self.registry = registry or ControllerCapabilityRegistry()
        self.capabilities = self.registry.runtime()
        self.admission = ControllerCapabilityAdmission(self.registry.dispatcher)
        self.executor = ControllerCapabilityExecutor()

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

    def select_capability(
        self,
        capability: str,
        *,
        provider: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> CapabilitySelection:
        """Return an immutable selection result without executing the capability."""
        return CapabilitySelection(
            self.resolve_capability(
                capability,
                provider=provider,
                context=context,
            )
        )

    def admit_capability(self, request) -> CapabilityAdmission:
        """Admit one normalized agent task without executing it."""
        return self.admission.admit(request)

    def execute_admitted(self, admission: CapabilityAdmission) -> CapabilityExecutionResult:
        """Execute only a capability that has already passed admission."""
        return self.executor.execute(admission)
