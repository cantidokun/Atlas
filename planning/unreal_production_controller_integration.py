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
            raise TypeError("runtime must be a UnrealProductionRuntimeAdapter instance")
        self._runtime = runtime

    @property
    def complete(self) -> bool:
        return self._runtime.complete

    def start(self, authorized: UnrealAuthorizedProductionPlan) -> UnrealProductionControllerEvent:
        return UnrealProductionControllerEvent(
            operation="start",
            snapshot=self._runtime.start(authorized),
        )

    def reassess(
        self,
        authorization: UnrealPlanAuthorization,
    ) -> UnrealProductionControllerEvent:
        return UnrealProductionControllerEvent(
            operation="reassess",
            snapshot=self._runtime.reassess(authorization),
        )

    def resume(
        self,
        authorization: UnrealPlanAuthorization,
    ) -> UnrealProductionControllerEvent:
        return UnrealProductionControllerEvent(
            operation="resume_recovery",
            snapshot=self._runtime.resume(authorization),
        )

    def next_required_authorization(self) -> Optional[str]:
        """Return the next explicit authorization class, if one is required."""
        loop = self._runtime.loop
        if self._runtime.complete:
            return None
        if loop.waiting_for_replacement:
            return "replacement"
        if loop.waiting_for_reassessment:
            return "reassessment"
        return "production"
