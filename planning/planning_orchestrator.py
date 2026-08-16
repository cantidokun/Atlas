"""Deterministic bridges between Atlas evidence, target state, and actions."""
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from action_plan import ActionPlan
from conditional_action_plan import ConditionalActionPlan
from evidence_plan import EvidencePlan
from planning.target_state import TargetStateEvaluationError, TargetStateEvaluator, TargetStateResult

ToolExecutor = Callable[[str, Dict[str, Any]], Dict[str, Any]]


@dataclass
class PlanningOrchestrator:
    evidence_plan: EvidencePlan
    action_plan: ActionPlan

    @property
    def evidence_complete(self) -> bool:
        return self.evidence_plan.complete

    @property
    def action_complete(self) -> bool:
        return self.action_plan.complete

    @property
    def blocked(self) -> bool:
        return self.evidence_plan.blocked or self.action_plan.blocked

    def next_phase(self) -> str:
        if self.blocked:
            return "BLOCKED"
        if not self.evidence_complete:
            return "EVIDENCE"
        if not self.action_complete:
            return "ACTION"
        return "COMPLETE"

    def acquire_next_evidence(
        self,
        execute: ToolExecutor,
        reused_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self.evidence_plan.complete:
            raise RuntimeError("Evidence plan is already complete.")
        if self.evidence_plan.blocked:
            raise RuntimeError("Evidence plan is blocked.")
        request = self.evidence_plan.next_request
        if request is None:
            raise RuntimeError("No next evidence request is available.")
        if reused_result is not None:
            self.evidence_plan.record_result(reused_result, True, reused=True)
            return reused_result
        result = execute(request.tool, request.arguments)
        self.evidence_plan.record_result(result, "error" not in result)
        return result

    def execute_next_action(self, execute: ToolExecutor) -> Dict[str, Any]:
        if not self.evidence_complete:
            raise RuntimeError("Action execution is blocked until evidence is complete.")
        if self.action_plan.complete:
            raise RuntimeError("Action plan is already complete.")
        if self.action_plan.blocked:
            raise RuntimeError("Action plan is blocked.")
        action = self.action_plan.next_action
        if action is None:
            raise RuntimeError("No next action is available.")
        result = execute(action.tool, action.arguments)
        self.action_plan.record_result(result, "error" not in result)
        return result

    def snapshot(self) -> Dict[str, Any]:
        return {
            "phase": self.next_phase(),
            "blocked": self.blocked,
            "evidence": self.evidence_plan.snapshot(),
            "actions": self.action_plan.snapshot(),
        }


@dataclass
class ConditionalPlanningOrchestrator:
    """Run evidence, target-state evaluation, and conditional actions deterministically.

    The orchestrator owns the phase boundary. No action is exposed until required
    evidence is complete and the target state has been evaluated. A satisfied target
    completes without exposing any action. An unsatisfied target exposes the already-
    authorized conditional action sequence. Evaluation failures fail closed.
    """

    evidence_plan: EvidencePlan
    conditional_plan: ConditionalActionPlan
    target_evaluator: TargetStateEvaluator
    target_state: Optional[TargetStateResult] = None
    evaluation_error: Optional[str] = None

    @property
    def evidence_complete(self) -> bool:
        return self.evidence_plan.complete

    @property
    def evaluated(self) -> bool:
        return self.target_state is not None

    @property
    def blocked(self) -> bool:
        return self.evidence_plan.blocked or self.evaluation_error is not None

    @property
    def skipped(self) -> bool:
        return self.conditional_plan.skipped

    @property
    def action_complete(self) -> bool:
        return self.conditional_plan.complete

    def next_phase(self) -> str:
        if self.blocked:
            return "BLOCKED"
        if not self.evidence_complete:
            return "EVIDENCE"
        if not self.evaluated:
            return "TARGET_EVALUATION"
        if self.skipped:
            return "COMPLETE"
        if not self.action_complete:
            return "ACTION"
        return "COMPLETE"

    def acquire_next_evidence(
        self,
        execute: ToolExecutor,
        reused_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self.evidence_plan.complete:
            raise RuntimeError("Evidence plan is already complete.")
        if self.evidence_plan.blocked:
            raise RuntimeError("Evidence plan is blocked.")
        request = self.evidence_plan.next_request
        if request is None:
            raise RuntimeError("No next evidence request is available.")
        if reused_result is not None:
            self.evidence_plan.record_result(reused_result, True, reused=True)
            return reused_result
        result = execute(request.tool, request.arguments)
        self.evidence_plan.record_result(result, "error" not in result)
        return result

    def evaluate_target_state(self, evidence: Any) -> TargetStateResult:
        if not self.evidence_complete:
            raise RuntimeError("Target-state evaluation is blocked until evidence is complete.")
        if self.evaluated:
            raise RuntimeError("Target state has already been evaluated.")
        try:
            result = self.target_evaluator.evaluate(evidence)
        except TargetStateEvaluationError as exc:
            self.evaluation_error = str(exc)
            raise
        self.target_state = result
        self.conditional_plan.evaluate(result.satisfied)
        return result

    def execute_next_action(self, execute: ToolExecutor) -> Dict[str, Any]:
        if not self.evidence_complete:
            raise RuntimeError("Action execution is blocked until evidence is complete.")
        if not self.evaluated:
            raise RuntimeError("Action execution is blocked until target state is evaluated.")
        if self.evaluation_error is not None:
            raise RuntimeError("Action execution is blocked by target-state evaluation failure.")
        if self.skipped:
            raise RuntimeError("Action execution is skipped because the target state is already satisfied.")
        action = self.conditional_plan.next_action
        if action is None:
            raise RuntimeError("No conditional action is available.")
        result = execute(action.tool, action.arguments)
        self.conditional_plan.record_result(result, "error" not in result)
        return result

    def snapshot(self) -> Dict[str, Any]:
        return {
            "phase": self.next_phase(),
            "blocked": self.blocked,
            "evidence": self.evidence_plan.snapshot(),
            "target_state": self.target_state.snapshot() if self.target_state else None,
            "evaluation_error": self.evaluation_error,
            "conditional_actions": self.conditional_plan.snapshot(),
        }
