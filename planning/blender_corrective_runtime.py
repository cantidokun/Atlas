"""Runtime adapter for reusable corrective tasks on the protected Blender executor."""
from __future__ import annotations

from typing import Any, Callable, Optional, Union

from planning.autonomous_corrective_task import AutonomousCorrectiveTask, CorrectiveTaskResult
from planning.blender_autonomous_executor import BlenderAutonomousExecutor
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.corrective_execution_boundary import CorrectiveExecutionBoundary

Executor = Union[
    BlenderAutonomousExecutor,
    Callable[[str, dict[str, Any]], dict[str, Any]],
]


class BlenderCorrectiveRuntime:
    """Run an authorized corrective planner using the protected Blender executor."""

    def __init__(
        self,
        observe: Callable[[], Any],
        plan: Callable[[Any], list],
        authorization_id: str,
        executor: Optional[Executor] = None,
    ) -> None:
        raw_executor = executor or BlenderAutonomousExecutor()
        self.executor = raw_executor
        if isinstance(raw_executor, BlenderExecutionBoundary):
            boundary = raw_executor
        elif isinstance(raw_executor, BlenderAutonomousExecutor):
            boundary = raw_executor._boundary
        elif callable(raw_executor):
            boundary = CorrectiveExecutionBoundary(raw_executor)
        else:
            raise TypeError("executor must be BlenderAutonomousExecutor, BlenderExecutionBoundary, or callable")
        self.task = AutonomousCorrectiveTask(
            boundary,
            observe,
            plan,
            authorization_id,
        )

    def run(self, max_steps: int = 16) -> CorrectiveTaskResult:
        return self.task.run(max_steps=max_steps)
