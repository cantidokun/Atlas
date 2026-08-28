"""Runtime-facing integration for Atlas Unreal production transactions.

This module is deliberately thin. Planning and authorization remain upstream;
the production autonomous loop owns deterministic execution and recovery.
The runtime integration exposes that lifecycle as a small stateful boundary
that an agent/controller can drive without taking ownership of authorization.
"""

from dataclasses import dataclass
from typing import Optional

from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_production_autonomous_loop import (
    UnrealProductionAutonomousLoop,
    UnrealProductionLoopOutcome,
)
from planning.unreal_production_controller_bridge import UnrealProductionControllerBridge
from planning.unreal_production_operation import UnrealProductionPlan
from planning.unreal_production_planning_boundary import UnrealAuthorizedProductionPlan


@dataclass(frozen=True)
class UnrealProductionRuntimeSnapshot:
    """Small immutable snapshot suitable for an outer Atlas runtime."""

    state: str
    phase: str
    waiting_for_reassessment: bool
    waiting_for_replacement: bool
    failure: object = None
    recovery: object = None


class UnrealProductionRuntimeIntegration:
    """Drive one authorized production transaction from the Atlas runtime."""

    def __init__(self, bridge: UnrealProductionControllerBridge) -> None:
        self._loop = UnrealProductionAutonomousLoop(bridge)
        self._outcome: Optional[UnrealProductionLoopOutcome] = None

    @property
    def active(self) -> bool:
        return self._outcome is not None and self._outcome.state not in {
            "complete",
            "recovery_complete",
            "manual_review_required",
        }

    @property
    def complete(self) -> bool:
        return self._outcome is not None and self._outcome.state in {
            "complete",
            "recovery_complete",
        }

    @property
    def snapshot(self) -> UnrealProductionRuntimeSnapshot:
        if self._outcome is None:
            return UnrealProductionRuntimeSnapshot(
                state="not_started",
                phase="not_started",
                waiting_for_reassessment=False,
                waiting_for_replacement=False,
            )
        return UnrealProductionRuntimeSnapshot(
            state=self._outcome.state,
            phase=self._outcome.phase,
            waiting_for_reassessment=self._loop.waiting_for_reassessment,
            waiting_for_replacement=self._loop.waiting_for_replacement,
            failure=self._outcome.failure,
            recovery=self._outcome.recovery,
        )

    def start(self, authorized: UnrealAuthorizedProductionPlan) -> UnrealProductionLoopOutcome:
        """Start the exact authorized production plan; never authorize implicitly."""
        outcome = self._loop.start(authorized)
        self._outcome = outcome
        return outcome

    def reassess(
        self,
        reassessment_authorization: UnrealPlanAuthorization,
    ) -> UnrealProductionLoopOutcome:
        """Perform the separately authorized fresh reassessment."""
        outcome = self._loop.reassess(reassessment_authorization)
        self._outcome = outcome
        return outcome

    def resume_recovery(
        self,
        replacement_authorization: UnrealPlanAuthorization,
    ) -> UnrealProductionLoopOutcome:
        """Resume only with authorization for the exact prepared replacement."""
        outcome = self._loop.resume_recovery(replacement_authorization)
        self._outcome = outcome
        return outcome

    def require_active_failure(self) -> UnrealProductionLoopOutcome:
        """Return the current recovery boundary or fail loudly if none exists."""
        if self._outcome is None or self._outcome.failure is None:
            raise RuntimeError("no failed production transaction is available")
        return self._outcome
