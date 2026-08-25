"""Production-facing resume boundary for interrupted corrective work."""
from __future__ import annotations

from typing import Any, Callable, Sequence

from action_plan import ActionSpec
from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.blender_corrective_runtime import BlenderCorrectiveRuntime
from planning.continuation_resume import ContinuationState


class ResumableCorrectiveTask:
    """Admit a resume only after fresh evidence, then return to the normal runtime."""

    def __init__(
        self,
        checkpoint: ContinuationState,
        observe: Callable[[], Any],
        plan: Callable[[Any], Sequence[ActionSpec]],
        authorization_id: str,
        executor: Any = None,
    ) -> None:
        self.checkpoint = checkpoint
        self.observe = observe
        self.plan = plan
        self.runtime = BlenderCorrectiveRuntime(
            observe,
            plan,
            authorization_id,
            executor=executor,
        )

    def resume(self, max_steps: int = 16) -> CorrectiveTaskResult:
        """Require fresh state before allowing the ordinary corrective runtime to resume."""
        fresh = self.observe()
        remaining = list(self.plan(fresh))
        self.checkpoint.authorize_remaining(fresh, remaining)
        return self.runtime.run(max_steps=max_steps)
