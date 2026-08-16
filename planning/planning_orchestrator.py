"""Deterministic bridges between Atlas evidence, target state, and actions."""
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from action_plan import ActionPlan, ActionSpec
from conditional_action_plan import ConditionalActionPlan
from evidence_plan import EvidencePlan
from planning.future_execution import FutureExecutionController
from planning.future_generator import DeterministicFutureGenerator
from planning.future_recovery import FutureRecoveryGate, RecoveryDisposition
from planning.replan_authorization import ReplanAuthorization
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
    """Run evidence, target-state evaluation, conditional actions, and recovery deterministically."""

    evidence_plan: EvidencePlan
    conditional_plan: ConditionalActionPlan
    target_evaluator: TargetStateEvaluator
    verification_plan: Optional[VerificationPlan] = None
    target_state: Optional[TargetStateResult] = None
    evaluation_error: Optional[str] = None
    future_controller: Optional[FutureExecutionController] = None
    recovery_gate: Optional[FutureRecoveryGate] = None
    replan_authorization: Optional[ReplanAuthorization] = None

    def __post_init__(self) -> None:
        if self.verification_plan is None:
            self.verification_plan = VerificationPlan(self.target_evaluator)

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
    def verification_complete(self) -> bool:
        return bool(self.verification_plan and self.verification_plan.complete)

    @property
    def recovery_replan_ready(self) -> bool:
        return bool(
            self.recovery_gate
            and self.recovery_gate.decision
            and self.recovery_gate.decision.disposition is RecoveryDisposition.REPLAN_REQUIRED
            and self.recovery_gate.fresh_evidence_acquired
        )

    @property
    def blocked(self) -> bool:
        if self.recovery_replan_ready:
            return False
        return (
            self.evidence_plan.blocked
            or self.evaluation_error is not None
            or self.conditional_plan.blocked
            or bool(self.verification_plan and self.verification_plan.blocked)
            or bool(self.future_controller and self.future_controller.blocked)
        )

    def next_phase(self) -> str:
        if self.recovery_replan_ready:
            return "RECOVERY_REPLAN"
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

    def _record_future_failure(self) -> None:
        if self.future_controller is not None:
            self.recovery_gate = FutureRecoveryGate(self.future_controller)
            self.recovery_gate.classify_failure()
            self.replan_authorization = None

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
        try:
            result = self.future_controller.execute_current(execute)
        except Exception as exc:
            failure = {"error": str(exc), "exception_type": type(exc).__name__}
            self.conditional_plan.record_result(failure, False)
            self._record_future_failure()
            raise
        self.conditional_plan.record_result(result, "error" not in result)
        if "error" in result:
            self._record_future_failure()
        return result

    def verify_post_action(self, evidence: Any) -> TargetStateResult:
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
        if self.future_controller.blocked:
            self._record_future_failure()
        return result

    def record_recovery_evidence(self, evidence: Any) -> Any:
        """Record fresh evidence after a failure and advance to explicit replanning."""
        if self.recovery_gate is None:
            raise RuntimeError("No recoverable future failure exists.")
        self.recovery_gate.record_fresh_evidence(evidence)
        self.recovery_gate.advance_after_fresh_evidence()
        self.replan_authorization = None
        return evidence

    def authorize_replan(self, authorization_id: str, authorized_actions: List[ActionSpec]) -> ReplanAuthorization:
        """Create an immutable authorization receipt for a specific replacement plan."""
        if not self.recovery_replan_ready:
            raise RuntimeError("Recovery is not ready for replanning.")
        evidence = self.recovery_gate.authorize_replan()
        receipt = ReplanAuthorization.issue(evidence, authorized_actions, authorization_id)
        self.replan_authorization = receipt
        return receipt

    def install_authorized_replan(self, authorization: ReplanAuthorization) -> TargetStateResult:
        """Install only the exact replacement plan covered by an authorization receipt."""
        if not self.recovery_replan_ready:
            raise RuntimeError("Recovery is not ready for an authorized replan.")
        if not isinstance(authorization, ReplanAuthorization):
            raise TypeError("authorization must be a ReplanAuthorization.")
        if self.replan_authorization != authorization:
            raise RuntimeError("Replan authorization does not match the current recovery authorization.")
        evidence = self.recovery_gate.authorize_replan()
        raise RuntimeError("Authorized action payload is required to install the replan.")

    def install_authorized_replan_actions(self, authorization: ReplanAuthorization, authorized_actions: List[ActionSpec]) -> TargetStateResult:
        """Install a replacement plan only when its actions match the issued receipt."""
        if not self.recovery_replan_ready:
            raise RuntimeError("Recovery is not ready for an authorized replan.")
        if not isinstance(authorization, ReplanAuthorization):
            raise TypeError("authorization must be a ReplanAuthorization.")
        if self.replan_authorization != authorization:
            raise RuntimeError("Replan authorization does not match the current recovery authorization.")
        if not authorization.matches(self.recovery_gate.authorize_replan(), authorized_actions):
            raise RuntimeError("Replacement actions do not match the authorized replan.")

        result = self.target_evaluator.evaluate(self.recovery_gate.authorize_replan())
        self.target_state = result
        self.evaluation_error = None
        self.conditional_plan = ConditionalActionPlan(list(authorized_actions))
        self.conditional_plan.evaluate(result.satisfied)
        self.verification_plan = VerificationPlan(self.target_evaluator)
        self.future_controller = FutureExecutionController(
            DeterministicFutureGenerator(self.target_evaluator).generate(result.satisfied, list(authorized_actions))
        )
        self.future_controller.acknowledge({"recovery_evidence": True})
        self.future_controller.acknowledge(result.snapshot())
        if result.satisfied:
            self.future_controller.acknowledge({"writes_skipped": True})
        self.recovery_gate = None
        self.replan_authorization = None
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
            "recovery": self.recovery_gate.snapshot() if self.recovery_gate else None,
            "replan_authorization": self.replan_authorization.snapshot() if self.replan_authorization else None,
        }
