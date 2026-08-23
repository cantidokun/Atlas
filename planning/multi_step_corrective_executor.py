"""Execute dependent corrective steps through the protected Blender boundary."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Tuple

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.multi_step_corrective_recovery import MultiStepCorrectiveRecovery


@dataclass(frozen=True)
class _AuthorizedStep:
    actions: list
    authorization: Any


class MultiStepCorrectiveExecutor:
    """Run one freshly authorized corrective step at a time."""

    def __init__(
        self,
        boundary: BlenderExecutionBoundary,
        observe: Callable[[], Any],
        plan: Callable[[Any], list],
        authorization_id: str,
    ):
        self.boundary = boundary
        self.recovery = MultiStepCorrectiveRecovery(observe, plan, authorization_id)
        self.observe = observe

    def execute_all(self, max_steps: int = 16) -> List[Tuple[Any, Any]]:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        receipts: List[Tuple[Any, Any]] = []
        for _ in range(max_steps):
            step = self.recovery.next_step()
            if step is None:
                return receipts
            fresh_evidence = self.observe()
            self.recovery.validate_step(step, fresh_evidence)
            authorized = _AuthorizedStep(actions=[step.action], authorization=step.authorization)
            result, receipt = self.boundary.execute_authorized_replan(authorized, fresh_evidence)
            receipts.append((result, receipt))
        return receipts
