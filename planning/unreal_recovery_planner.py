"""Deterministic recovery/replanning decision component for Unreal execution.

Consumes an explicit ``UnrealExecutionEvaluation`` and the originating
intent/plan context, then returns a bounded, deterministic next-step decision.

Design invariants
-----------------
- **Pure**: no Unreal transport calls, no authorization issuance, no file
  mutation, no evidence fabrication, no execution of any kind.
- **Fail-closed**: failure is never silently converted to success.
- **Deterministic**: identical inputs always produce identical decisions.
- **Bounded**: retry/recovery limits are explicit in the decision contract;
  unbounded retry loops are structurally impossible.
- **Context-preserving**: the original intent ID and entity IDs are always
  propagated into the recovery decision.

This module establishes the recovery decision contract that a later
autonomous controller can consume.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from planning.unreal_execution_evaluator import (
    EvaluationOutcome,
    UnrealExecutionEvaluation,
)
from planning.unreal_task_planner import UnrealTaskPlan


# ---------------------------------------------------------------------------
# Recovery action enum
# ---------------------------------------------------------------------------

class RecoveryAction(str, Enum):
    """Deterministic next-step category produced by the recovery planner."""

    NO_ACTION = "no_action"
    """Intent is satisfied; no further action required."""

    REQUEST_VERIFICATION = "request_verification"
    """Evidence exists but is unverified; request a verification pass."""

    REQUEST_RECOVERY = "request_recovery"
    """Execution failed; request a bounded recovery/retry attempt."""

    REQUEST_REVIEW = "request_review"
    """Evidence is incomplete or unresolvable; request human/system review."""


# ---------------------------------------------------------------------------
# Recovery context (carries retry budget)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RecoveryContext:
    """Immutable context describing the current recovery state.

    Parameters
    ----------
    attempt:
        The current attempt number (1-based).  Must be >= 1.
    max_attempts:
        The maximum number of attempts allowed.  Must be >= 1.
    """

    attempt: int
    max_attempts: int

    def __post_init__(self) -> None:
        if not isinstance(self.attempt, int) or self.attempt < 1:
            raise ValueError("attempt must be a positive integer (>= 1)")
        if not isinstance(self.max_attempts, int) or self.max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer (>= 1)")
        if self.attempt > self.max_attempts:
            raise ValueError(
                f"attempt ({self.attempt}) must not exceed "
                f"max_attempts ({self.max_attempts})"
            )

    @property
    def retries_remaining(self) -> int:
        return self.max_attempts - self.attempt

    @property
    def exhausted(self) -> bool:
        return self.attempt >= self.max_attempts


# ---------------------------------------------------------------------------
# Recovery decision (immutable output)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RecoveryDecision:
    """Immutable, deterministic recovery decision.

    Carries the recommended next action, the originating context, and a
    human-readable reason.  The controller layer consumes this to decide
    whether to retry, verify, escalate, or stop.
    """

    intent_id: str
    entity_ids: Tuple[str, ...]
    action: RecoveryAction
    reason: str
    source_outcome: EvaluationOutcome
    attempt: int
    max_attempts: int
    retries_remaining: int

    def __post_init__(self) -> None:
        if not isinstance(self.intent_id, str) or not self.intent_id.strip():
            raise ValueError("intent_id must be a non-empty string")
        if not isinstance(self.entity_ids, tuple):
            raise TypeError("entity_ids must be a tuple")
        if not isinstance(self.action, RecoveryAction):
            raise TypeError("action must be a RecoveryAction")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")
        if not isinstance(self.source_outcome, EvaluationOutcome):
            raise TypeError("source_outcome must be an EvaluationOutcome")
        if not isinstance(self.attempt, int) or self.attempt < 1:
            raise ValueError("attempt must be a positive integer (>= 1)")
        if not isinstance(self.max_attempts, int) or self.max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer (>= 1)")
        if not isinstance(self.retries_remaining, int) or self.retries_remaining < 0:
            raise ValueError("retries_remaining must be a non-negative integer")

    @property
    def terminal(self) -> bool:
        """Whether this decision represents a terminal state (no further action)."""
        return self.action in (RecoveryAction.NO_ACTION, RecoveryAction.REQUEST_REVIEW)


# ---------------------------------------------------------------------------
# Recovery planner
# ---------------------------------------------------------------------------

_DEFAULT_MAX_ATTEMPTS = 3


class UnrealRecoveryPlanner:
    """Pure, deterministic recovery decision planner.

    Consumes an ``UnrealExecutionEvaluation`` and the originating task plan
    context, then returns a ``RecoveryDecision`` describing the bounded
    next step.

    Usage::

        planner = UnrealRecoveryPlanner()
        decision = planner.decide(evaluation, task_plan, recovery_context)
    """

    def decide(
        self,
        evaluation: UnrealExecutionEvaluation,
        task_plan: UnrealTaskPlan,
        context: RecoveryContext,
    ) -> RecoveryDecision:
        """Produce a deterministic recovery decision.

        Parameters
        ----------
        evaluation:
            The ``UnrealExecutionEvaluation`` from the evaluator.
        task_plan:
            The ``UnrealTaskPlan`` that was evaluated.
        context:
            The ``RecoveryContext`` carrying the current retry budget.

        Raises
        ------
        TypeError
            If any argument is not the expected type.
        ValueError
            If the evaluation's intent_id does not match the plan's.
        """
        self._validate_inputs(evaluation, task_plan, context)

        intent_id = task_plan.intent_id
        entity_ids = self._collect_entity_ids(task_plan)

        # ----- SATISFIED → no action -----
        if evaluation.outcome == EvaluationOutcome.SATISFIED:
            return RecoveryDecision(
                intent_id=intent_id,
                entity_ids=entity_ids,
                action=RecoveryAction.NO_ACTION,
                reason="Intent satisfied; all evidence verified",
                source_outcome=evaluation.outcome,
                attempt=context.attempt,
                max_attempts=context.max_attempts,
                retries_remaining=context.retries_remaining,
            )

        # ----- VERIFICATION_REQUIRED → request verification (or review if exhausted) -----
        if evaluation.outcome == EvaluationOutcome.VERIFICATION_REQUIRED:
            if context.exhausted:
                return RecoveryDecision(
                    intent_id=intent_id,
                    entity_ids=entity_ids,
                    action=RecoveryAction.REQUEST_REVIEW,
                    reason=(
                        "Verification still required after "
                        f"{context.max_attempts} attempt(s); escalating to review"
                    ),
                    source_outcome=evaluation.outcome,
                    attempt=context.attempt,
                    max_attempts=context.max_attempts,
                    retries_remaining=0,
                )
            return RecoveryDecision(
                intent_id=intent_id,
                entity_ids=entity_ids,
                action=RecoveryAction.REQUEST_VERIFICATION,
                reason=(
                    f"{evaluation.unverified_count} evidence entries require "
                    f"verification (attempt {context.attempt}/{context.max_attempts})"
                ),
                source_outcome=evaluation.outcome,
                attempt=context.attempt,
                max_attempts=context.max_attempts,
                retries_remaining=context.retries_remaining,
            )

        # ----- FAILED → request recovery (or review if exhausted) -----
        if evaluation.outcome == EvaluationOutcome.FAILED:
            if context.exhausted:
                return RecoveryDecision(
                    intent_id=intent_id,
                    entity_ids=entity_ids,
                    action=RecoveryAction.REQUEST_REVIEW,
                    reason=(
                        "Execution failed after "
                        f"{context.max_attempts} attempt(s); escalating to review"
                    ),
                    source_outcome=evaluation.outcome,
                    attempt=context.attempt,
                    max_attempts=context.max_attempts,
                    retries_remaining=0,
                )
            return RecoveryDecision(
                intent_id=intent_id,
                entity_ids=entity_ids,
                action=RecoveryAction.REQUEST_RECOVERY,
                reason=(
                    f"Execution failed (attempt {context.attempt}/"
                    f"{context.max_attempts}); requesting bounded recovery"
                ),
                source_outcome=evaluation.outcome,
                attempt=context.attempt,
                max_attempts=context.max_attempts,
                retries_remaining=context.retries_remaining,
            )

        # ----- INCOMPLETE → request recovery (or review if exhausted) -----
        if evaluation.outcome == EvaluationOutcome.INCOMPLETE:
            if context.exhausted:
                return RecoveryDecision(
                    intent_id=intent_id,
                    entity_ids=entity_ids,
                    action=RecoveryAction.REQUEST_REVIEW,
                    reason=(
                        "Evidence incomplete after "
                        f"{context.max_attempts} attempt(s); escalating to review"
                    ),
                    source_outcome=evaluation.outcome,
                    attempt=context.attempt,
                    max_attempts=context.max_attempts,
                    retries_remaining=0,
                )
            return RecoveryDecision(
                intent_id=intent_id,
                entity_ids=entity_ids,
                action=RecoveryAction.REQUEST_RECOVERY,
                reason=(
                    f"Evidence incomplete (attempt {context.attempt}/"
                    f"{context.max_attempts}); requesting bounded recovery"
                ),
                source_outcome=evaluation.outcome,
                attempt=context.attempt,
                max_attempts=context.max_attempts,
                retries_remaining=context.retries_remaining,
            )

        # Defensive: unknown outcome → review
        return RecoveryDecision(
            intent_id=intent_id,
            entity_ids=entity_ids,
            action=RecoveryAction.REQUEST_REVIEW,
            reason=f"Unrecognized evaluation outcome: {evaluation.outcome}",
            source_outcome=evaluation.outcome,
            attempt=context.attempt,
            max_attempts=context.max_attempts,
            retries_remaining=context.retries_remaining,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_inputs(
        evaluation: UnrealExecutionEvaluation,
        task_plan: UnrealTaskPlan,
        context: RecoveryContext,
    ) -> None:
        if not isinstance(evaluation, UnrealExecutionEvaluation):
            raise TypeError(
                "evaluation must be an UnrealExecutionEvaluation instance"
            )
        if not isinstance(task_plan, UnrealTaskPlan):
            raise TypeError("task_plan must be a UnrealTaskPlan instance")
        if not isinstance(context, RecoveryContext):
            raise TypeError("context must be a RecoveryContext instance")
        if evaluation.intent_id != task_plan.intent_id:
            raise ValueError(
                f"Evaluation intent_id '{evaluation.intent_id}' does not match "
                f"task plan intent_id '{task_plan.intent_id}'"
            )

    @staticmethod
    def _collect_entity_ids(task_plan: UnrealTaskPlan) -> Tuple[str, ...]:
        """Collect the union of entity IDs from all operations, preserving order."""
        seen: Dict[str, None] = {}
        for op in task_plan.operations:
            for eid in op.entity_ids:
                if eid not in seen:
                    seen[eid] = None
        return tuple(seen.keys())
