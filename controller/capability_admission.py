"""Admission boundary between normalized agent intent and capability execution.

Admission is intentionally non-executing. It converts the outer agent request
into the controller's canonical request model, resolves exactly one registered
capability, and returns an immutable admission receipt. Provider-specific
execution and authorization remain downstream of this boundary.
"""

from dataclasses import dataclass
from typing import Any

from controller.agent_task_request import AgentTaskRequest
from controller.capability_dispatch import ControllerCapability, ControllerCapabilityDispatcher
from controller.capability_request import CapabilityRequest


@dataclass(frozen=True)
class CapabilityAdmission:
    """Immutable proof that a normalized request resolved to one capability."""

    request: CapabilityRequest
    capability: ControllerCapability

    @property
    def name(self) -> str:
        return self.capability.name

    @property
    def handler(self) -> Any:
        return self.capability.handler


class ControllerCapabilityAdmission:
    """Admit controller-owned requests without invoking their handlers."""

    def __init__(self, dispatcher: ControllerCapabilityDispatcher) -> None:
        if not isinstance(dispatcher, ControllerCapabilityDispatcher):
            raise TypeError("dispatcher must be a ControllerCapabilityDispatcher")
        self._dispatcher = dispatcher

    def admit(self, request: AgentTaskRequest) -> CapabilityAdmission:
        """Convert, resolve, and admit one agent request without execution."""
        if not isinstance(request, AgentTaskRequest):
            raise TypeError("request must be an AgentTaskRequest instance")

        canonical = CapabilityRequest(
            capability=request.capability,
            provider=request.provider,
            context=dict(request.context),
        )
        capability = self._dispatcher.resolve(canonical)
        if capability is None:
            raise LookupError(
                f"no controller capability matched: {canonical.normalized_capability}"
            )
        return CapabilityAdmission(request=canonical, capability=capability)
