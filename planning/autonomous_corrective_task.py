"""Reusable observe-plan-authorize-execute-verify corrective task loop."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Sequence, Tuple

from action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.multi_step_corrective_recovery import MultiStepCorrectiveRecovery


@dataclass(frozen=True)
class CorrectiveTaskResult:
    receipts: Tuple[Any, ...]
    final_evidence: Any
    converged: bool


class AutonomousCorrectiveTask:
    """Drive arbitrary authorized Blender tasks through fresh-state correction."""

    def __init__(self, boundary: BlenderExecutionBoundary, observe: Callable[[], Any], plan: Callable[[Any], Sequence[ActionSpec]], authorization_id: str):
        self.boundary = boundary
        self.recovery = MultiStepCorrectiveRecovery(observe, plan, authorization_id)
        self.observe = observe
        self.plan = plan

    def run(self, max_steps: int = 16) -> CorrectiveTaskResult:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        receipts: List[Any] = []
        for _ in range(max_steps):
            step = self.recovery.next_step()
            if step is None:
                final = self.observe()
                return CorrectiveTaskResult(tuple(receipts), final, True)
            fresh = self.observe()
            self.recovery.validate_step(step, fresh)
            _, receipt = self.boundary.execute_authorized_replan(
                type("AuthorizedStep", (), {"actions": [step.action], "authorization": step.authorization})(),
                fresh,
            )
            receipts.append(receipt)
        final = self.observe()
        return CorrectiveTaskResult(tuple(receipts), final, not bool(self.plan(final)))
