"""Runtime adapter for reusable corrective tasks on the protected Blender executor."""
from __future__ import annotations

from typing import Any, Callable, Optional, Sequence, Union

from action_plan import ActionSpec
from planning.autonomous_corrective_task import AutonomousCorrectiveTask, CorrectiveTaskResult
from planning.blender_autonomous_executor import BlenderAutonomousExecutor
from planning.blender_execution_boundary import BlenderExecutionBoundary

Executor = Union[
    BlenderAutonomousExecutor,
    Callable[[str, dict[str, Any]], dict[str, Any]],
]


class BlenderCorrectiveRuntime:
    """Run an authorized corrective planner using the production Blender executor."""

    def __init__(
        self,
        observe: Callable[[], Any],
        plan: Callable[[Any], Sequence[ActionSpec]],
        authorization_id: str,
        executor: Optional[Executor] = None,
    ) -> None:
        raw_executor = executor or BlenderAutonomousExecutor()
        # The corrective task consumes the protected boundary, not the raw
        # callable.  This keeps injected test executors on the same
        # authorization/receipt path as the production executor.
        self.executor = raw_executor
        boundary = raw_executor if isinstance(raw_executor, BlenderExecutionBoundary) else BlenderExecutionBoundary(raw_executor)
        self.task = AutonomousCorrectiveTask(
            boundary,
            observe,
            plan,
            authorization_id,
        )

    def run(self, max_steps: int = 16) -> CorrectiveTaskResult:
        return self.task.run(max_steps=max_steps)
