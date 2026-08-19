"""Bounded autonomous execution loop for a single Unreal task intent.

Composes the existing deterministic components into a closed loop:

    plan → authorize → execute → evaluate → recover (bounded)

Design invariants
-----------------
- **Single intent**: operates on one supplied ``UnrealTaskIntent``; does not
  invent operations or generate autonomous goals.
- **Authorization-gated**: every execution pass goes through
  ``UnrealAuthorizedExecutionGate``; the loop never calls Unreal transport
  directly.
- **Bounded**: explicit ``max_iterations`` and ``max_recovery_attempts``
  prevent unbounded retry loops.
- **Fail-closed**: malformed inputs, missing authorization, transport
  failures, and exhausted bounds all terminate with failure.
- **Deterministic**: identical inputs with deterministic adapter behaviour
  produce equivalent histories.
- **Auditable**: every state transition is recorded in an immutable history
  of ``LoopStepRecord`` entries.
- **Context-preserving**: the original intent ID and entity IDs are
  propagated through every step.

Python 3.9 compatible.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, Tuple

from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_authorized_execution_gate import (
    UnrealAuthorizationGateError,
    UnrealAuthorizedExecutionGate,
)
from planning.unreal_execution_evaluator import (
    EvaluationOutcome,
    UnrealExecutionEvaluation,
    UnrealExecutionEvaluator,
)
from planning.unreal_plan_executor import (
    UnrealPlanExecutionError,
    UnrealPlanExecutionResult,
    UnrealPlanExecutor,
)
from planning.unreal_recovery_planner import (
    RecoveryAction,
    RecoveryContext,
    RecoveryDecision,
    UnrealRecoveryPlanner,
)
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner


# ---------------------------------------------------------------------------
# Public type alias for the authorization-id provider
# ---------------------------------------------------------------------------

AuthorizationIdProvider = Callable[[int], str]
"""Callable that receives the current iteration (1-based) and returns a
non-empty authorization ID string for that pass."""


# ---------------------------------------------------------------------------
# Loop configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LoopConfig:
    """Immutable, explicit bounds for the autonomous loop."""

    max_iterations: int = 5
    max_recovery_attempts: int = 3

    def __post_init__(self) -> None:
        if not isinstance(self.max_iterations, int) or self.max_iterations < 1:
            raise ValueError("max_iterations must be a positive integer (>= 1)")
        if not isinstance(self.max_recovery_attempts, int) or self.max_recovery_attempts < 1:
            raise ValueError(
                "max_recovery_attempts must be a positive integer (>= 1)"
            )


# ---------------------------------------------------------------------------
# Loop terminal status
# ---------------------------------------------------------------------------

class LoopTermination(str, Enum):
    """Why the autonomous loop stopped."""

    SATISFIED = "satisfied"
    """Intent fully satisfied with verified evidence."""

    FAILED = "failed"
    """Unrecoverable failure (transport, authorization, or evaluation)."""

    RECOVERY_EXHAUSTED = "recovery_exhausted"
    """Recovery planner escalated to review (retry budget spent)."""

    ITERATION_LIMIT = "iteration_limit"
    """Maximum iteration count reached without satisfaction."""


# ---------------------------------------------------------------------------
# Step record (immutable history entry)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LoopStepRecord:
    """One immutable record of a loop iteration."""

    iteration: int
    plan_intent_id: str
    plan_operation_count: int
    authorization_id: str
    execution_success: Optional[bool]
    evaluation: Optional[UnrealExecutionEvaluation]
    recovery_decision: Optional[RecoveryDecision]
    error: Optional[str]


# ---------------------------------------------------------------------------
# Loop result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AutonomousLoopResult:
    """Immutable result of the autonomous execution loop."""

    intent_id: str
    termination: LoopTermination
    iterations_used: int
    history: Tuple[LoopStepRecord, ...]
    final_evaluation: Optional[UnrealExecutionEvaluation]
    final_recovery: Optional[RecoveryDecision]

    def __post_init__(self) -> None:
        if not isinstance(self.intent_id, str) or not self.intent_id.strip():
            raise ValueError("intent_id must be a non-empty string")
        if not isinstance(self.termination, LoopTermination):
            raise TypeError("termination must be a LoopTermination")
        if not isinstance(self.iterations_used, int) or self.iterations_used < 0:
            raise ValueError("iterations_used must be a non-negative integer")
        if not isinstance(self.history, tuple):
            raise TypeError("history must be a tuple")


# ---------------------------------------------------------------------------
# Autonomous execution loop
# ---------------------------------------------------------------------------

class UnrealAutonomousExecutionLoop:
    """Bounded, authorization-gated autonomous loop for one Unreal intent.

    Usage::

        loop = UnrealAutonomousExecutionLoop(
            planner=UnrealTaskPlanner(),
            gate=gate,
            evaluator=UnrealExecutionEvaluator(),
            recovery_planner=UnrealRecoveryPlanner(),
        )
        result = loop.run(intent, auth_id_provider, config)
    """

    def __init__(
        self,
        planner: UnrealTaskPlanner,
        gate: UnrealAuthorizedExecutionGate,
        evaluator: UnrealExecutionEvaluator,
        recovery_planner: UnrealRecoveryPlanner,
    ) -> None:
        if not isinstance(planner, UnrealTaskPlanner):
            raise TypeError("planner must be a UnrealTaskPlanner instance")
        if not isinstance(gate, UnrealAuthorizedExecutionGate):
            raise TypeError(
                "gate must be a UnrealAuthorizedExecutionGate instance"
            )
        if not isinstance(evaluator, UnrealExecutionEvaluator):
            raise TypeError(
                "evaluator must be a UnrealExecutionEvaluator instance"
            )
        if not isinstance(recovery_planner, UnrealRecoveryPlanner):
            raise TypeError(
                "recovery_planner must be a UnrealRecoveryPlanner instance"
            )
        self._planner = planner
        self._gate = gate
        self._evaluator = evaluator
        self._recovery = recovery_planner

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(
        self,
        intent: UnrealTaskIntent,
        auth_id_provider: AuthorizationIdProvider,
        config: Optional[LoopConfig] = None,
    ) -> AutonomousLoopResult:
        """Execute the bounded autonomous loop for *intent*.

        Parameters
        ----------
        intent:
            A validated ``UnrealTaskIntent``.
        auth_id_provider:
            Callable ``(iteration: int) -> str`` returning a fresh
            authorization ID for each pass.
        config:
            Optional ``LoopConfig``; defaults are used when ``None``.

        Returns
        -------
        AutonomousLoopResult
            Immutable result with full auditable history.

        Raises
        ------
        TypeError / ValueError
            On malformed inputs (fail-closed).
        """
        self._validate_run_inputs(intent, auth_id_provider, config)
        if config is None:
            config = LoopConfig()

        history: List[LoopStepRecord] = []
        recovery_attempt = 0
        last_evaluation: Optional[UnrealExecutionEvaluation] = None
        last_recovery: Optional[RecoveryDecision] = None

        for iteration in range(1, config.max_iterations + 1):
            # ---- Plan ----
            try:
                task_plan = self._plan_for_intent(intent, iteration)
            except (TypeError, ValueError) as exc:
                history.append(self._error_record(
                    iteration, intent.intent_id, str(exc),
                ))
                return self._terminal(
                    intent.intent_id,
                    LoopTermination.FAILED,
                    iteration,
                    history,
                    last_evaluation,
                    last_recovery,
                )

            # ---- Authorize ----
            auth_id = self._obtain_auth_id(auth_id_provider, iteration)
            if not isinstance(auth_id, str) or not auth_id.strip():
                history.append(self._error_record(
                    iteration,
                    intent.intent_id,
                    "auth_id_provider returned an invalid authorization ID",
                    plan=task_plan,
                ))
                return self._terminal(
                    intent.intent_id,
                    LoopTermination.FAILED,
                    iteration,
                    history,
                    last_evaluation,
                    last_recovery,
                )

            # ---- Execute (through authorized gate) ----
            try:
                exec_result = self._authorized_execute(task_plan, auth_id)
            except (UnrealPlanExecutionError, UnrealAuthorizationGateError) as exc:
                history.append(self._error_record(
                    iteration,
                    intent.intent_id,
                    str(exc),
                    plan=task_plan,
                    authorization_id=auth_id,
                ))
                return self._terminal(
                    intent.intent_id,
                    LoopTermination.FAILED,
                    iteration,
                    history,
                    last_evaluation,
                    last_recovery,
                )

            # ---- Evaluate ----
            evaluation = self._evaluator.evaluate(task_plan, exec_result)
            last_evaluation = evaluation

            # ---- SATISFIED → immediate termination ----
            if evaluation.outcome == EvaluationOutcome.SATISFIED:
                history.append(self._step_record(
                    iteration, task_plan, auth_id, exec_result, evaluation, None,
                ))
                return self._terminal(
                    intent.intent_id,
                    LoopTermination.SATISFIED,
                    iteration,
                    history,
                    evaluation,
                    None,
                )

            # ---- Recovery decision ----
            recovery_attempt += 1
            ctx = RecoveryContext(
                attempt=min(recovery_attempt, config.max_recovery_attempts),
                max_attempts=config.max_recovery_attempts,
            )
            decision = self._recovery.decide(evaluation, task_plan, ctx)
            last_recovery = decision

            history.append(self._step_record(
                iteration, task_plan, auth_id, exec_result, evaluation, decision,
            ))

            # ---- Terminal recovery actions ----
            if decision.action == RecoveryAction.REQUEST_REVIEW:
                return self._terminal(
                    intent.intent_id,
                    LoopTermination.RECOVERY_EXHAUSTED,
                    iteration,
                    history,
                    evaluation,
                    decision,
                )

            # Non-terminal: loop continues to next iteration

        # ---- Iteration limit reached ----
        return self._terminal(
            intent.intent_id,
            LoopTermination.ITERATION_LIMIT,
            config.max_iterations,
            history,
            last_evaluation,
            last_recovery,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _plan_for_intent(
        self,
        intent: UnrealTaskIntent,
        iteration: int,
    ) -> UnrealTaskPlan:
        """Create a task plan.  Uses inspection planning as the default
        single-intent strategy.  A future extension point for plan-type
        selection lives here."""
        # For the bounded single-intent loop we re-plan each iteration
        # so that the gate always receives a fresh, un-executed plan.
        return self._planner.plan_inspection(intent)

    def _obtain_auth_id(
        self,
        provider: AuthorizationIdProvider,
        iteration: int,
    ) -> str:
        try:
            return provider(iteration)
        except Exception:
            return ""

    def _authorized_execute(
        self,
        plan: UnrealTaskPlan,
        authorization_id: str,
    ) -> UnrealPlanExecutionResult:
        """Load, authorize, and execute through the gate."""
        self._gate.load_plan(plan)
        self._gate.authorize(authorization_id)
        return self._gate.execute()

    # ------------------------------------------------------------------
    # Record builders
    # ------------------------------------------------------------------

    @staticmethod
    def _step_record(
        iteration: int,
        plan: UnrealTaskPlan,
        authorization_id: str,
        exec_result: UnrealPlanExecutionResult,
        evaluation: UnrealExecutionEvaluation,
        recovery: Optional[RecoveryDecision],
    ) -> LoopStepRecord:
        return LoopStepRecord(
            iteration=iteration,
            plan_intent_id=plan.intent_id,
            plan_operation_count=len(plan.operations),
            authorization_id=authorization_id,
            execution_success=exec_result.success,
            evaluation=evaluation,
            recovery_decision=recovery,
            error=None,
        )

    @staticmethod
    def _error_record(
        iteration: int,
        intent_id: str,
        error: str,
        plan: Optional[UnrealTaskPlan] = None,
        authorization_id: str = "",
    ) -> LoopStepRecord:
        return LoopStepRecord(
            iteration=iteration,
            plan_intent_id=intent_id,
            plan_operation_count=len(plan.operations) if plan else 0,
            authorization_id=authorization_id,
            execution_success=None,
            evaluation=None,
            recovery_decision=None,
            error=error,
        )

    @staticmethod
    def _terminal(
        intent_id: str,
        termination: LoopTermination,
        iterations_used: int,
        history: List[LoopStepRecord],
        evaluation: Optional[UnrealExecutionEvaluation],
        recovery: Optional[RecoveryDecision],
    ) -> AutonomousLoopResult:
        return AutonomousLoopResult(
            intent_id=intent_id,
            termination=termination,
            iterations_used=iterations_used,
            history=tuple(history),
            final_evaluation=evaluation,
            final_recovery=recovery,
        )

    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_run_inputs(
        intent: UnrealTaskIntent,
        auth_id_provider: AuthorizationIdProvider,
        config: Optional[LoopConfig],
    ) -> None:
        if not isinstance(intent, UnrealTaskIntent):
            raise TypeError("intent must be a UnrealTaskIntent instance")
        if not callable(auth_id_provider):
            raise TypeError("auth_id_provider must be callable")
        if config is not None and not isinstance(config, LoopConfig):
            raise TypeError("config must be a LoopConfig instance or None")
