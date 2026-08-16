"""Deterministic bridges between Atlas evidence, target state, actions, and verification."""
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from action_plan import ActionPlan, ActionSpec
from conditional_action_plan import ConditionalActionPlan
from evidence_plan import EvidencePlan
from planning.future_execution import FutureExecutionController
from planning.future_generator import DeterministicFutureGenerator
from planning.target_state import TargetStateEvaluationError, TargetStateEvaluator, TargetStateResult
from planning.verification_plan import VerificationPlan

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

    def acquire_next_evidence(self, execute: ToolExecutor, reused_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        try:
            result = execute(request.tool, request.arguments)
        except Exception as exc:
            failure = {"error": str(exc), "exception_type": type(exc).__name__}
            self.evidence_plan.record_result(failure, False)
            raise
        self.evidence_plan.record_result(result, "error" not in result)
        return result

    def execute_next_action(self, execute: ToolExecutor) -> Dict[str, Any]:
        if not self.evidence_complete:
            raise RuntimeError("Action execution is blocked until evidence is complete.")
        if self.action_plan.complete:
            raise RuntimeError("Action plan is already complete.")
        if self.action_plan.blocked:
            raise RuntimeError("Action plan is blocked by a previous failure.")
        action = self.action_plan.next_action
        if action is None:
            raise RuntimeError("No next action is available.")
        try:
            result = execute(action.tool, action.arguments)
        except Exception as exc:
            failure = {"error": str(exc), "exception_type": type(exc).__name__}
            self.action_plan.record_result(failure, False)
            raise
        self.action_plan.record_result(result, "error" not in result)
        return result

    def snapshot(self) -> Dict[str, Any]:
        return {"phase": self.next_phase(), "blocked": self.blocked, "evidence": self.evidence_plan.snapshot(), "actions": self.action_plan.snapshot()}


@dataclass
class ConditionalPlanningOrchestrator:
    """Run evidence, target-state evaluation, conditional actions, verification, and deterministic future control."""

    evidence_plan: EvidencePlan
    conditional_plan: ConditionalActionPlan
    target_evaluator: TargetStateEvaluator
    target_state: Optional[TargetStateResult] = None
    evaluation_error: Optional[str] = None
    verification_plan: Optional[VerificationPlan] = None
    future_controller: Optional[FutureExecutionController] = None

    @property
    def evidence_complete(self) -> bool:
        return self.evidence_plan.complete

    @property
    def evaluated(self) -> bool:
        return self.target_state is not None

    @property
    def skipped(self) -> bool:
        return self.conditional_plan.skipped

    @property
    def action_complete(self) -> bool:
        return self.conditional_plan.complete

    @property
    def verification_required(self) -> bool:
        return self.verification_plan is not None

    @property
    def verification_complete(self) -> bool:
        return not self.verification_required or bool(self.verification_plan and self.verification_plan.complete)

    @property
    def blocked(self) -> bool:
        return (
            self.evidence_plan.blocked
            or self.evaluation_error is not None
            or self.conditional_plan.blocked
            or bool(self.verification_plan and self.verification_plan.blocked)
            or bool(self.future_controller and self.future_controller.blocked)
        )

    def next_phase(self) -> str:
        if self.blocked:
            return "BLOCKED"
        if not self.evidence_complete:
            return "EVIDENCE"
        if not self.evaluated:
            return "TARGET_EVALUATION"
        if self.skipped:
            if not self.verification_complete:
                return "VERIFICATION"
            return "COMPLETE"
        if not self.action_complete:
            return "ACTION"
        if not self.verification_complete:
            return "VERIFICATION"
        return "COMPLETE"

    def acquire_next_evidence(self, execute: ToolExecutor, reused_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        try:
            result = execute(request.tool, request.arguments)
        except Exception as exc:
            failure = {"error": str(exc), "exception_type": type(exc).__name__}
            self.evidence_plan.record_result(failure, False)
            raise
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
        actions = [
            ActionSpec(action.tool, dict(action.arguments), action.name, action.requires_success)
            for action in self.conditional_plan.action_plan.actions
        ]
        self.future_controller = FutureExecutionController(
            DeterministicFutureGenerator(self.target_evaluator).generate(result.satisfied, actions)
        )
        self.future_controller.acknowledge({"evidence_complete": True})
        self.future_controller.acknowledge(result.snapshot())
        if result.satisfied:
            self.future_controller.acknowledge({"writes_skipped": True})
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
        if self.conditional_plan.blocked:
            raise RuntimeError("Action execution is blocked by a previous failure.")
        if self.future_controller is None or self.future_controller.current_step is None:
            raise RuntimeError("No deterministic future is available for action execution.")
        if self.future_controller.current_step.phase != "ACTION":
            raise RuntimeError("Deterministic future is not at an ACTION checkpoint.")
        action = self.conditional_plan.next_action
        if action is None:
            raise RuntimeError("No conditional action is available.")
        expected = self.future_controller.next_action
        if expected is None or expected.get("index") != self.conditional_plan.action_plan.current_index:
            raise RuntimeError("Conditional action diverged from the deterministic future.")
        result = self.future_controller.execute_current(execute)
        self.conditional_plan.record_result(result, "error" not in result)
        return result

    def verify_post_action(self, evidence: Any) -> TargetStateResult:
        """Verify final state from fresh authoritative evidence and advance the future."""
        if not self.evidence_complete:
            raise RuntimeError("Verification is blocked until required evidence is complete.")
        if not self.evaluated:
            raise RuntimeError("Verification is blocked until target state has been evaluated.")
        if not self.skipped and not self.action_complete:
            raise RuntimeError("Verification is blocked until all authorized actions complete.")
        if self.verification_plan is None:
            raise RuntimeError("No verification plan is configured.")
        if self.future_controller is None or self.future_controller.current_step is None:
            raise RuntimeError("No deterministic future is available for verification.")
        if self.future_controller.current_step.phase != "VERIFICATION":
            raise RuntimeError("Deterministic future is not at the verification checkpoint.")
        result = self.verification_plan.verify(evidence)
        self.future_controller.verify(result.snapshot())
        return result

    def finalize_future(self) -> Dict[str, Any]:
        if self.future_controller is None:
            raise RuntimeError("No deterministic future is available.")
        if self.future_controller.current_step and self.future_controller.current_step.phase == "COMPLETE":
            return self.future_controller.finalize()
        if not self.future_controller.complete:
            raise RuntimeError("Deterministic future is not ready to finalize.")
        return self.future_controller.snapshot()

    def snapshot(self) -> Dict[str, Any]:
        return {
            "phase": self.next_phase(),
            "blocked": self.blocked,
            "evidence": self.evidence_plan.snapshot(),
            "target_state": self.target_state.snapshot() if self.target_state else None,
            "evaluation_error": self.evaluation_error,
            "conditional_actions": self.conditional_plan.snapshot(),
            "verification": self.verification_plan.snapshot() if self.verification_plan else None,
            "future": self.future_controller.snapshot() if self.future_controller else None,
        }
