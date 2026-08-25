"""Bridge reusable corrective recovery into the autonomous runtime boundary."""
from __future__ import annotations

from typing import Any, Callable, Sequence, Union

from action_plan import ActionSpec
from planning.autonomous_corrective_task import AutonomousCorrectiveTask, CorrectiveTaskResult
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.corrective_execution_boundary import CorrectiveExecutionBoundary


class CorrectiveRuntimeAdapter:
    """Runtime-facing adapter for arbitrary authorized corrective tasks.

    A real BlenderExecutionBoundary is preserved for production Blender work.
    A plain callable is treated as an explicit in-memory corrective executor.
    """

    def __init__(
        self,
        boundary: Union[BlenderExecutionBoundary, Callable[[str, dict[str, Any]], dict[str, Any]]],
        observe: Callable[[], Any],
        plan: Callable[[Any], Sequence[ActionSpec]],
        authorization_id: str,
    ) -> None:
        if isinstance(boundary, BlenderExecutionBoundary):
            self.task = AutonomousCorrectiveTask(boundary, observe, plan, authorization_id)
        elif callable(boundary):
            self.task = AutonomousCorrectiveTask(
                CorrectiveExecutionBoundary(boundary), observe, plan, authorization_id
            )
        else:
            raise TypeError("boundary must be BlenderExecutionBoundary or corrective executor callable")

    def run(self, max_steps: int = 16) -> CorrectiveTaskResult:
        """Run until convergence or the explicit correction budget is exhausted."""
        return self.task.run(max_steps=max_steps)

    @property
    def boundary(self):
        return self.task.boundary
