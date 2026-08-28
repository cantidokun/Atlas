"""Execution gateway for controller-owned capabilities.

Execution is intentionally downstream of admission. The gateway accepts only
an immutable ``CapabilityAdmission`` produced by the admission boundary and
then invokes the already-registered handler. It does not create authorization
or perform provider-specific execution itself.
"""

from dataclasses import dataclass
from typing import Any

from controller.capability_admission import CapabilityAdmission
from controller.capability_dispatch import ControllerCapability


@dataclass(frozen=True)
class CapabilityExecutionResult:
    """Stable result returned after one admitted capability invocation."""

    capability_name: str
    value: Any


class ControllerCapabilityExecutor:
    """Execute only capabilities that have already passed admission."""

    def execute(self, admission: CapabilityAdmission) -> CapabilityExecutionResult:
        if not isinstance(admission, CapabilityAdmission):
            raise TypeError("admission must be a CapabilityAdmission instance")
        capability = admission.capability
        if not isinstance(capability, ControllerCapability):
            raise TypeError("admission must contain a registered ControllerCapability")
        handler = capability.handler
        execute = getattr(handler, "execute", None)
        if not callable(execute):
            raise TypeError(
                f"capability '{capability.name}' handler does not expose execute()"
            )
        value = execute(admission.request)
        return CapabilityExecutionResult(
            capability_name=capability.name,
            value=value,
        )
