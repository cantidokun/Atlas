"""Bridge reusable corrective recovery into the autonomous runtime boundary."""
from __future__ import annotations

from typing import Any, Callable, Sequence

from action_plan import ActionSpec
from planning.autonomous_corrective_task import AutonomousCorrectiveTask, CorrectiveTaskResult
from planning.blender_execution_boundary import BlenderExecutionBoundary


class CorrectiveRuntimeAdapter:
    """Runtime-facing adapter for arbitrary authorized corrective tasks."""

    def __init__(
        self,
        boundary: BlenderExecutionBoundary,
        observe: Callable[[], Any],
        plan: Callable[[Any], Sequence[ActionSpec]],
        authorization_id: str,
    ) -> None:
        self.task = AutonomousCorrectiveTask(boundary, observe, plan, authorization_id)

    def run(self, max_steps: int = 16) -> CorrectiveTaskResult:
        """Run until convergence or the explicit correction budget is exhausted."""
        return self.task.run(max_steps=max_steps)

    @property
    def boundary(self) -> BlenderExecutionBoundary:
        return self.task.boundary
