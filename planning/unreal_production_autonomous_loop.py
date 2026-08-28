"""Production-aware autonomous execution loop for Unreal transactions.

The loop owns orchestration only. It never invents authorization. A failed
transaction pauses at an explicit recovery boundary, fresh reassessment must
be authorized separately, and a replacement must receive its own exact
authorization before execution can resume.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionFailure
from planning.unreal_production_controller_bridge import (
    UnrealProductionControllerBridge,
    UnrealProductionControllerOutcome,
)
from planning.unreal_production_operation import UnrealProductionPlan
from planning.unreal_production_planning_boundary import UnrealAuthorizedProductionPlan
from planning.unreal_production_recovery_adapter import UnrealProductionReceiptRecovery


@dataclass(frozen=True)
class UnrealProductionLoopOutcome:
    """Public orchestration state exposed between autonomous loop steps."""

    state: str
    phase: str
    failure: Optional[UnrealPlanExecutionFailure]
    recovery: Optional[object]
    required_authorizations: Tuple[str, ...]


class UnrealProductionAutonomousLoop:
    """Pause/resume production execution at explicit authorization boundaries."""

    def __init__(self, bridge: UnrealProductionControllerBridge) -> None:
        if not isinstance(bridge, UnrealProductionControllerBridge):
            raise TypeError("bridge must be a UnrealProductionControllerBridge instance")
        self._bridge = bridge
        self._production: Optional[UnrealProductionPlan] = None
        self._failure: Optional[UnrealPlanExecutionFailure] = None
        self._reassessment_authorization: Optional[UnrealPlanAuthorization] = None
        self._prepared_recovery: Optional[UnrealProductionReceiptRecovery] = None

    @property
    def waiting_for_reassessment(self) -> bool:
        return self._failure is not None and self._prepared_recovery is None

    @property
    def waiting_for_replacement(self) -> bool:
        return bool(
            self._prepared_recovery is not None
            and self._prepared_recovery.assessment.disposition == "replacement_required"
        )

    def start(self, authorized: UnrealAuthorizedProductionPlan) -> UnrealProductionLoopOutcome:
        """Start exactly one authorized production transaction."""
        if not isinstance(authorized, UnrealAuthorizedProductionPlan):
            raise TypeError("authorized must be an UnrealAuthorizedProductionPlan instance")
        if self._production is not None and not self._bridge.complete:
            raise RuntimeError("a production transaction is already in progress")

        self._production = authorized.production
        self._failure = None
        self._reassessment_authorization = None
        self._prepared_recovery = None
        outcome = self._bridge.start(authorized.production, authorized.authorization)
        if outcome.state == "failed_pending_recovery":
            self._failure = outcome.failure
            return UnrealProductionLoopOutcome(
                state="awaiting_reassessment",
                phase=self._bridge.state.phase,
                failure=outcome.failure,
                recovery=None,
                required_authorizations=("reassessment",),
            )
        return self._from_controller_outcome(outcome, required=())

    def reassess(
        self,
        reassessment_authorization: UnrealPlanAuthorization,
    ) -> UnrealProductionLoopOutcome:
        """Perform one fresh, separately authorized reassessment."""
        if not self.waiting_for_reassessment:
            raise RuntimeError("production loop is not waiting for reassessment")
        if self._production is None or self._failure is None:
            raise RuntimeError("no failed production transaction is available for reassessment")

        prepared = self._bridge.prepare_recovery(
            self._production,
            self._failure,
            reassessment_authorization,
        )
        self._reassessment_authorization = reassessment_authorization
        self._prepared_recovery = prepared
        disposition = prepared.assessment.disposition

        if disposition == "replacement_required":
            return UnrealProductionLoopOutcome(
                state="awaiting_replacement",
                phase="recovery_reassessed",
                failure=self._failure,
                recovery=prepared,
                required_authorizations=("replacement",),
            )
        if disposition == "already_applied":
            completed = self._bridge.complete_prepared_recovery(
                prepared,
                reassessment_authorization=reassessment_authorization,
            )
            return self._from_controller_outcome(completed, required=())

        return UnrealProductionLoopOutcome(
            state="manual_review_required",
            phase="recovery_reassessed",
            failure=self._failure,
            recovery=prepared,
            required_authorizations=(),
        )

    def resume_recovery(
        self,
        replacement_authorization: UnrealPlanAuthorization,
    ) -> UnrealProductionLoopOutcome:
        """Resume only after the exact replacement plan has been authorized."""
        if not self.waiting_for_replacement:
            raise RuntimeError("production loop is not waiting for replacement authorization")
        if self._prepared_recovery is None or self._reassessment_authorization is None:
            raise RuntimeError("no prepared production recovery is available")

        completed = self._bridge.complete_prepared_recovery(
            self._prepared_recovery,
            reassessment_authorization=self._reassessment_authorization,
            replacement_authorization=replacement_authorization,
        )
        return self._from_controller_outcome(completed, required=())

    def _from_controller_outcome(
        self,
        outcome: UnrealProductionControllerOutcome,
        *,
        required: Tuple[str, ...],
    ) -> UnrealProductionLoopOutcome:
        return UnrealProductionLoopOutcome(
            state=outcome.state,
            phase=self._bridge.state.phase,
            failure=outcome.failure,
            recovery=outcome.recovery,
            required_authorizations=required,
        )
