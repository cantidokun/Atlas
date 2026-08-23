"""Runtime adapter for reusable corrective tasks on the protected Blender executor."""
from __future__ import annotations

from typing import Any, Callable, Sequence

from action_plan import ActionSpec
from planning.autonomous_corrective_task import AutonomousCorrectiveTask, CorrectiveTaskResult
from planning.blender_autonomous_executor import BlenderAutonomousExecutor


class BlenderCorrectiveRuntime:
    """Run an authorized corrective planner using the production Blender executor."""

    def __init__(
        self,
        observe: Callable[[], Any],
        plan: Callable[[Any], Sequence[ActionSpec]],
        authorization_id: str,
        executor: BlenderAutonomousExecutor | None = None,
    ) -> None:
        self.executor = executor or BlenderAutonomousExecutor()
        self.task = AutonomousCorrectiveTask(
            self.executor,
            observe,
            plan,
            authorization_id,
        )

    def run(self, max_steps: int = 16) -> CorrectiveTaskResult:
        return self.task.run(max_steps=max_steps)
