"""Deterministic evaluation of Unreal plan execution results.

This pure evaluator consumes a completed ``UnrealPlanExecutionResult`` and the
originating ``UnrealTaskPlan``, then produces an explicit ``UnrealExecutionEvaluation``
describing whether the intent is satisfied, whether execution failed, whether
verification is still required, and what deterministic next-action category
should be taken.

Design invariants
-----------------
- **Pure**: no Unreal transport calls, no filesystem mutation, no authorization
  issuance, no hidden side effects.
- **Fail-closed**: execution failure surfaces as failure, never as success.
- **Honest**: unverified evidence is never treated as verified; incomplete
  evidence never yields a ``SATISFIED`` outcome.
- **Deterministic**: identical inputs always produce identical evaluations.

This module establishes the evaluation contract that later autonomous
replanning and task-generation layers will consume.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_executor import UnrealPlanExecutionResult
from planning.unreal_task_planner import UnrealTaskPlan


# ---------------------------------------------------------------------------
# Outcome and next-action enums
# ---------------------------------------------------------------------------

class EvaluationOutcome(str, Enum):
    """High-level evaluation of whether the intent was achieved."""

    SATISFIED = "satisfied"
    """All operations succeeded and all evidence is verified."""

    FAILED = "failed"
    """Execution reported failure; the intent was not achieved."""

    VERIFICATION_REQUIRED = "verification_required"
    """Execution succeeded but one or more evidence entries are unverified."""

    INCOMPLETE = "incomplete"
    """The evidence ledger does not cover every planned operation."""


class NextAction(str, Enum):
    """Deterministic next-action category for the autonomous loop."""

    NONE = "none"
    """No further action is needed (terminal success)."""

    REPORT_SUCCESS = "report_success"
    """Report successful completion to the orchestrator."""

    REPORT_FAILURE = "report_failure"
    """Report failure to the orchestrator."""

    REQUEST_VERIFICATION = "request_verification"
    """Request external verification of unverified evidence."""

    REQUEST_RETRY = "request_retry"
    """Request a retry or remediation pass."""


# ---------------------------------------------------------------------------
# Evaluation result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UnrealExecutionEvaluation:
    """Immutable, deterministic evaluation of a plan execution result."""

    intent_id: str
    outcome: EvaluationOutcome
    next_action: NextAction
    reason: str
    operation_count: int
    evidence_count: int
    unverified_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.intent_id, str) or not self.intent_id.strip():
            raise ValueError("intent_id must be a non-empty string")
        if not isinstance(self.outcome, EvaluationOutcome):
            raise TypeError("outcome must be an EvaluationOutcome")
        if not isinstance(self.next_action, NextAction):
            raise TypeError("next_action must be a NextAction")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")
        if self.operation_count < 0:
            raise ValueError("operation_count must be non-negative")
        if self.evidence_count < 0:
            raise ValueError("evidence_count must be non-negative")
        if self.unverified_count < 0:
            raise ValueError("unverified_count must be non-negative")


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class UnrealExecutionEvaluator:
    """Pure, deterministic evaluator of Unreal plan execution results.

    Usage::

        evaluator = UnrealExecutionEvaluator()
        evaluation = evaluator.evaluate(task_plan, execution_result)
    """

    def evaluate(
        self,
        plan: UnrealTaskPlan,
        result: UnrealPlanExecutionResult,
    ) -> UnrealExecutionEvaluation:
        """Evaluate *result* against *plan* and return a deterministic outcome.

        Parameters
        ----------
        plan:
            The ``UnrealTaskPlan`` that was executed.
        result:
            The ``UnrealPlanExecutionResult`` returned by the executor.

        Raises
        ------
        TypeError
            If *plan* or *result* are not the expected types.
        ValueError
            If *result* contains structurally invalid data.
        """
        self._validate_inputs(plan, result)

        operation_count = len(plan.operations)
        evidence_count = len(result.evidence_ledger)

        # ----- Fail-closed: explicit failure -----
        if not result.success:
            return UnrealExecutionEvaluation(
                intent_id=result.intent_id,
                outcome=EvaluationOutcome.FAILED,
                next_action=NextAction.REPORT_FAILURE,
                reason="Execution reported failure",
                operation_count=operation_count,
                evidence_count=evidence_count,
                unverified_count=self._count_unverified(result.evidence_ledger),
            )

        # ----- Incomplete evidence -----
        if evidence_count < operation_count:
            return UnrealExecutionEvaluation(
                intent_id=result.intent_id,
                outcome=EvaluationOutcome.INCOMPLETE,
                next_action=NextAction.REQUEST_RETRY,
                reason=(
                    f"Evidence ledger has {evidence_count} entries but plan "
                    f"requires {operation_count}"
                ),
                operation_count=operation_count,
                evidence_count=evidence_count,
                unverified_count=self._count_unverified(result.evidence_ledger),
            )

        # ----- Evidence / operation name mismatch -----
        mismatches = self._find_name_mismatches(plan, result)
        if mismatches:
            return UnrealExecutionEvaluation(
                intent_id=result.intent_id,
                outcome=EvaluationOutcome.INCOMPLETE,
                next_action=NextAction.REQUEST_RETRY,
                reason=(
                    f"Evidence does not match planned operations at "
                    f"indices: {mismatches}"
                ),
                operation_count=operation_count,
                evidence_count=evidence_count,
                unverified_count=self._count_unverified(result.evidence_ledger),
            )

        # ----- Unverified evidence -----
        unverified = self._count_unverified(result.evidence_ledger)
        if unverified > 0:
            return UnrealExecutionEvaluation(
                intent_id=result.intent_id,
                outcome=EvaluationOutcome.VERIFICATION_REQUIRED,
                next_action=NextAction.REQUEST_VERIFICATION,
                reason=(
                    f"{unverified} of {evidence_count} evidence entries "
                    f"are not yet verified"
                ),
                operation_count=operation_count,
                evidence_count=evidence_count,
                unverified_count=unverified,
            )

        # ----- All verified — intent satisfied -----
        return UnrealExecutionEvaluation(
            intent_id=result.intent_id,
            outcome=EvaluationOutcome.SATISFIED,
            next_action=NextAction.REPORT_SUCCESS,
            reason="All operations executed and all evidence verified",
            operation_count=operation_count,
            evidence_count=evidence_count,
            unverified_count=0,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_inputs(
        plan: UnrealTaskPlan,
        result: UnrealPlanExecutionResult,
    ) -> None:
        if not isinstance(plan, UnrealTaskPlan):
            raise TypeError("plan must be a UnrealTaskPlan instance")
        if not isinstance(result, UnrealPlanExecutionResult):
            raise TypeError("result must be a UnrealPlanExecutionResult instance")
        if result.intent_id != plan.intent_id:
            raise ValueError(
                f"Result intent_id '{result.intent_id}' does not match "
                f"plan intent_id '{plan.intent_id}'"
            )

    @staticmethod
    def _count_unverified(ledger: Tuple[UnrealEvidence, ...]) -> int:
        return sum(1 for ev in ledger if not ev.verified)

    @staticmethod
    def _find_name_mismatches(
        plan: UnrealTaskPlan,
        result: UnrealPlanExecutionResult,
    ) -> Tuple[int, ...]:
        """Return indices where evidence operation_name ≠ plan operation name."""
        mismatches = []
        pairs = min(len(plan.operations), len(result.evidence_ledger))
        for i in range(pairs):
            if result.evidence_ledger[i].operation_name != plan.operations[i].name:
                mismatches.append(i)
        return tuple(mismatches)
