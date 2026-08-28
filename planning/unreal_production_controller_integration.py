"""Agent-facing integration boundary for Unreal production transactions.

The generic Atlas controller remains provider-neutral. This module adapts the
Unreal production runtime into a small lifecycle contract that an outer agent
or orchestrator can consume without gaining a way to bypass authorization.
"""

from dataclasses import dataclass
from typing import Optional

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
