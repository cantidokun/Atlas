"""Safe orchestration of Unreal failure assessment into fresh-state planning.

This layer connects the execution failure boundary to the existing fail-closed
recovery policy and reassessment planner. It may produce a read-only plan, but
it never retries, rolls back, or authorizes a mutation.
"""

from dataclasses import dataclass
from typing import Optional

from planning.unreal_plan_executor import UnrealPlanExecutionFailure
from planning.unreal_reassessment_planner import UnrealReassessmentPlanner
from planning.unreal_recovery_policy import (
    UnrealRecoveryAssessment,
    UnrealRecoveryDisposition,
    assess_unreal_failure,
)
from planning.unreal_task_planner import UnrealTaskPlan


@dataclass(frozen=True)
class UnrealRecoveryPlan:
    """Immutable recovery decision plus an optional read-only next plan."""

    assessment: UnrealRecoveryAssessment
    reassessment_plan: Optional[UnrealTaskPlan]


class UnrealRecoveryOrchestrator:
    """Convert an execution failure into the safest available next step.

    ``REASSESS_STATE`` produces exactly one read-only reassessment plan.
    ``HALT`` produces no plan. This class deliberately has no executor and
    therefore cannot perform a retry or mutation as a side effect.
    """

    def __init__(self, reassessment_planner: Optional[UnrealReassessmentPlanner] = None) -> None:
        self._reassessment_planner = reassessment_planner or UnrealReassessmentPlanner()

    def plan(self, failure: UnrealPlanExecutionFailure) -> UnrealRecoveryPlan:
        """Assess *failure* and, when safe, build a fresh-state read plan."""
        assessment = assess_unreal_failure(failure)

        if assessment.disposition is UnrealRecoveryDisposition.HALT:
            return UnrealRecoveryPlan(
                assessment=assessment,
                reassessment_plan=None,
            )

        if assessment.disposition is not UnrealRecoveryDisposition.REASSESS_STATE:
            raise ValueError(
                f"unsupported Unreal recovery disposition: {assessment.disposition.value}"
            )

        if not assessment.requires_fresh_evidence:
            raise ValueError("REASSESS_STATE recovery requires fresh evidence")

        return UnrealRecoveryPlan(
            assessment=assessment,
            reassessment_plan=self._reassessment_planner.plan(assessment),
        )
