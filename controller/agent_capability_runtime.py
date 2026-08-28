"""Agent-facing capability resolution without implicit execution authority.

The existing midpoint controller integration remains unchanged. This module
provides a provider-neutral entry point that can resolve explicit capability
requests to registered controller-owned capabilities.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from controller.capability_dispatch import ControllerCapability, ControllerCapabilityDispatcher
from controller.capability_request import CapabilityRequest


@dataclass(frozen=True)
class AgentCapabilityResolution:
    """Stable result of capability resolution at the agent boundary."""

    request: CapabilityRequest
    capability: Optional[ControllerCapability]

    @property
    def matched(self) -> bool:
        return self.capability is not None


class AgentCapabilityRuntime:
    """Resolve controller capabilities while leaving execution to the owner."""

    def __init__(self, dispatcher: ControllerCapabilityDispatcher) -> None:
        if not isinstance(dispatcher, ControllerCapabilityDispatcher):
            raise TypeError("dispatcher must be a ControllerCapabilityDispatcher instance")
        self._dispatcher = dispatcher

    @property
    def dispatcher(self) -> ControllerCapabilityDispatcher:
        return self._dispatcher

    def resolve(
        self,
        capability: str,
        *,
        provider: Optional[str] = None,
        context: Optional[Mapping[str, Any]] = None,
    ) -> AgentCapabilityResolution:
        """Resolve one explicit capability request without invoking its handler."""
        request = CapabilityRequest(
            capability=capability,
            provider=provider,
            context=context or {},
        )
        return AgentCapabilityResolution(
            request=request,
            capability=self._dispatcher.resolve(request),
        )
