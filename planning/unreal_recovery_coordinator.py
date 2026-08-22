"""Execute fail-closed Unreal reassessment without authorizing a retry.

This layer closes the recovery loop for actor-location mutations:
1. classify the execution failure;
2. build the targeted read-only reassessment plan;
3. execute only that read-only plan; and
4. compare fresh evidence with the original mutation intent.

It deliberately has no mutation path. A reassessment decision can confirm or
reject state, but it can never authorize repeating the failed write.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from planning.unreal_plan_executor import (
    UnrealPlanExecutionFailure,
    UnrealPlanExecutionResult,
    UnrealPlanExecutor,
)
from planning.unreal_reassessment_decision import (
    UnrealReassessmentDecision,
    decide_reassessment,
)
from planning.unreal_recovery_orchestrator import UnrealRecoveryOrchestrator
from planning.unreal_recovery_policy import UnrealRecoveryAssessment, UnrealRecoveryDisposition


@dataclass(frozen=True)
class UnrealRecoveryReassessmentResult:
    """Result of a read-only recovery reassessment."""

    assessment: UnrealRecoveryAssessment
    execution_result: Optional[UnrealPlanExecutionResult]
    decision: Optional[UnrealReassessmentDecision]


def _location_from_arguments(arguments: Mapping[str, Any]) -> Optional[Mapping[str, float]]:
    location = arguments.get("location")
    if location is None:
        return None
    if not isinstance(location, Mapping):
        raise ValueError("recovery location intent must be a mapping")
    if set(location.keys()) != {"x", "y", "z"}:
        raise ValueError("recovery location intent must contain exactly x, y, and z")
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in location.values()
    ):
        raise ValueError("recovery location intent coordinates must be numeric")
    return dict(location)


def _expected_location(failure: UnrealPlanExecutionFailure) -> Optional[Mapping[str, float]]:
    """Recover the original location intent from the failure boundary."""
    location = _location_from_arguments(failure.operation_arguments)
    if location is not None:
        return location

    for arguments in reversed(failure.completed_operation_arguments):
        location = _location_from_arguments(arguments)
        if location is not None:
            return location

    return None


class UnrealRecoveryCoordinator:
    """Perform the safe read-only portion of Unreal recovery."""

    def __init__(
        self,
        executor: UnrealPlanExecutor,
        orchestrator: Optional[UnrealRecoveryOrchestrator] = None,
    ) -> None:
        if not isinstance(executor, UnrealPlanExecutor):
            raise TypeError("executor must be an UnrealPlanExecutor instance")
        self._executor = executor
        self._orchestrator = orchestrator or UnrealRecoveryOrchestrator()

    def reassess(
        self,
        failure: UnrealPlanExecutionFailure,
        authorization_id: str,
    ) -> UnrealRecoveryReassessmentResult:
        """Execute the targeted reassessment and classify its fresh evidence.

        The only plan executed here is the read-only plan produced by the
        recovery orchestrator. A confirmed or changed state is returned as
        information only; neither outcome authorizes a mutation.
        """
        recovery = self._orchestrator.plan(failure)
        if recovery.assessment.disposition is UnrealRecoveryDisposition.HALT:
            return UnrealRecoveryReassessmentResult(
                assessment=recovery.assessment,
                execution_result=None,
                decision=None,
            )

        if recovery.reassessment_plan is None:
            raise ValueError("REASSESS_STATE recovery must provide a reassessment plan")

        execution_result = self._executor.execute(
            recovery.reassessment_plan,
            authorization_id,
        )
        if len(execution_result.evidence_ledger) != 1:
            raise ValueError("reassessment execution must produce exactly one evidence item")

        expected_location = _expected_location(failure)
        if expected_location is None:
            return UnrealRecoveryReassessmentResult(
                assessment=recovery.assessment,
                execution_result=execution_result,
                decision=None,
            )

        decision = decide_reassessment(
            recovery.assessment,
            execution_result.evidence_ledger[0],
            expected_location,
        )
        return UnrealRecoveryReassessmentResult(
            assessment=recovery.assessment,
            execution_result=execution_result,
            decision=decision,
        )
