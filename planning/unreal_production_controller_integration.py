"""Agent-facing integration boundary for Unreal production transactions.

The generic Atlas controller remains provider-neutral. This module adapts the
Unreal production runtime into a small lifecycle contract that an outer agent
or orchestrator can consume without gaining a way to bypass authorization.
"""

from dataclasses import dataclass
from typing import Optional

from controller.capability_request import CapabilityRequest
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_production_planning_boundary import UnrealAuthorizedProductionPlan
from planning.unreal_production_runtime_adapter import (
    UnrealProductionRuntimeAdapter,
    UnrealProductionRuntimeSnapshot,
)


@dataclass(frozen=True)
class UnrealProductionControllerEvent:
    """Controller-facing event emitted after each production lifecycle action."""

    operation: str
    snapshot: UnrealProductionRuntimeSnapshot


class UnrealProductionControllerIntegration:
    """Expose Unreal production as an explicit Atlas controller capability."""

    def __init__(self, runtime: UnrealProductionRuntimeAdapter) -> None:
        if not isinstance(runtime, UnrealProductionRuntimeAdapter):
            raise TypeError("runtime must be a UnrealProductionRuntimeAdapter")
        self._runtime = runtime
        self._last_event: Optional[UnrealProductionControllerEvent] = None

    @property
    def complete(self) -> bool:
        return self._runtime.complete

    @property
    def snapshot(self) -> UnrealProductionRuntimeSnapshot:
        return self._runtime.snapshot

    def execute(self, request: CapabilityRequest) -> UnrealProductionControllerEvent:
        """Execute one admitted production request using explicit authorization context.

        The generic capability layer supplies only a normalized request. Unreal
        authorization remains a concrete downstream concern: the request must
        carry an ``UnrealAuthorizedProductionPlan`` under the explicit
        ``authorized_production`` context key before production can start.
        """
        if not isinstance(request, CapabilityRequest):
            raise TypeError("request must be a CapabilityRequest")
        if request.normalized_provider != "unreal":
            raise ValueError("Unreal production execution requires provider='unreal'")
        if request.normalized_capability != "production":
            raise ValueError("Unreal production execution requires capability='production'")
        authorized = request.context.get("authorized_production")
        if not isinstance(authorized, UnrealAuthorizedProductionPlan):
            raise TypeError(
                "request context must contain an UnrealAuthorizedProductionPlan "
                "under 'authorized_production'"
            )
        return self.start(authorized)

    def start(self, authorized: UnrealAuthorizedProductionPlan) -> UnrealProductionControllerEvent:
        event = UnrealProductionControllerEvent(
            operation="start",
            snapshot=self._runtime.start(authorized),
        )
        self._last_event = event
        return event

    def reassess(
        self,
        authorization: UnrealPlanAuthorization,
    ) -> UnrealProductionControllerEvent:
        event = UnrealProductionControllerEvent(
            operation="reassess",
            snapshot=self._runtime.reassess(authorization),
        )
        self._last_event = event
        return event

    def resume(
        self,
        authorization: UnrealPlanAuthorization,
    ) -> UnrealProductionControllerEvent:
        event = UnrealProductionControllerEvent(
            operation="resume_recovery",
            snapshot=self._runtime.resume(authorization),
        )
        self._last_event = event
        return event

    def next_required_authorization(self) -> Optional[str]:
        """Return the next explicit authorization class, if one is required."""
        if self._runtime.complete:
            return None
        if self._last_event is None:
            return "production"
        state = self._last_event.snapshot.state
        if state == "awaiting_reassessment":
            return "reassessment"
        if state == "awaiting_replacement":
            return "replacement"
        return None
