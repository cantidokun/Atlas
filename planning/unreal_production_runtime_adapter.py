"""Adapter from Atlas's generic runtime loop to Unreal production transactions.

The generic runtime/controller remains provider-neutral. This adapter exposes a
small Unreal-specific surface that consumes an already-authorized production
plan and returns explicit orchestration states without granting execution
authority to the model layer.
"""

from dataclasses import dataclass
from typing import Optional

from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_production_autonomous_loop import (
    UnrealProductionAutonomousLoop,
    UnrealProductionLoopOutcome,
)
from planning.unreal_production_planning_boundary import UnrealAuthorizedProductionPlan
from planning.unreal_production_controller_bridge import UnrealProductionControllerBridge


@dataclass(frozen=True)
class UnrealProductionRuntimeSnapshot:
    """Stable runtime-facing snapshot for one Unreal production transaction."""

    state: str
    phase: str
    waiting_for_reassessment: bool
    waiting_for_replacement: bool
    failure: object
    recovery: object
    required_authorizations: tuple


class UnrealProductionRuntimeAdapter:
    """Drive the production loop from an Atlas runtime without bypassing gates."""

    def __init__(self, executor: UnrealPlanExecutor) -> None:
        if not isinstance(executor, UnrealPlanExecutor):
            raise TypeError("executor must be a UnrealPlanExecutor instance")
        self._bridge = UnrealProductionControllerBridge(executor)
        self._loop = UnrealProductionAutonomousLoop(self._bridge)

    @property
    def complete(self) -> bool:
        return self._bridge.complete

    @property
    def loop(self) -> UnrealProductionAutonomousLoop:
        return self._loop

    def start(self, authorized: UnrealAuthorizedProductionPlan) -> UnrealProductionRuntimeSnapshot:
        return self._snapshot(self._loop.start(authorized))

    def reassess(
        self,
        reassessment_authorization: UnrealPlanAuthorization,
    ) -> UnrealProductionRuntimeSnapshot:
        return self._snapshot(self._loop.reassess(reassessment_authorization))

    def resume(
        self,
        replacement_authorization: UnrealPlanAuthorization,
    ) -> UnrealProductionRuntimeSnapshot:
        return self._snapshot(self._loop.resume_recovery(replacement_authorization))

    @staticmethod
    def _snapshot(outcome: UnrealProductionLoopOutcome) -> UnrealProductionRuntimeSnapshot:
        return UnrealProductionRuntimeSnapshot(
            state=outcome.state,
            phase=outcome.phase,
            waiting_for_reassessment=outcome.state == "awaiting_reassessment",
            waiting_for_replacement=outcome.state == "awaiting_replacement",
            failure=outcome.failure,
            recovery=outcome.recovery,
            required_authorizations=outcome.required_authorizations,
        )
