"""Reusable observe-plan-authorize-execute-verify corrective task loop."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Sequence, Tuple

from action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.multi_step_corrective_recovery import CorrectiveStep, MultiStepCorrectiveRecovery


@dataclass(frozen=True)
class CorrectiveTaskResult:
    receipts: Tuple[Any, ...]
    final_evidence: Any
    converged: bool


@dataclass(frozen=True)
class AuthorizedCorrectiveStep:
    """Boundary-shaped authorization envelope for exactly one corrective action."""
    actions: List[ActionSpec]
    authorization: Any


class AutonomousCorrectiveTask:
    """Drive authorized corrective tasks through fresh-state correction."""

    def __init__(self, boundary: BlenderExecutionBoundary, observe: Callable[[], Any], plan: Callable[[Any], Sequence[ActionSpec]], authorization_id: str):
        self.boundary = boundary
        self.recovery = MultiStepCorrectiveRecovery(observe, plan, authorization_id)
        self.observe = observe
        self.plan = plan

    def _execute_step(self, step: CorrectiveStep, fresh_evidence: Any) -> Any:
        envelope = AuthorizedCorrectiveStep(actions=[step.action], authorization=step.authorization)
        normalized, receipt = self.boundary.execute_authorized_replan(envelope, fresh_evidence)
        if not receipt.matches(step.action.tool, step.action.arguments, normalized):
            raise RuntimeError("corrective execution receipt does not bind the requested action")
        return receipt

    def run(self, max_steps: int = 16) -> CorrectiveTaskResult:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        receipts: List[Any] = []
        for _ in range(max_steps):
            fresh = self.observe()
            step = self.recovery.next_step(fresh)
            if step is None:
                return CorrectiveTaskResult(tuple(receipts), fresh, True)
            receipts.append(self._execute_step(step, fresh))
        final = self.observe()
        return CorrectiveTaskResult(tuple(receipts), final, not bool(self.plan(final)))
