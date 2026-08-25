"""Production-facing composition boundary for multi-operation Blender correction.

The reusable corrective runtime already owns observation, authorization,
execution, receipt binding, and re-observation. This module adds the explicit
production composition boundary: a composed planner may emit multiple scene-
writing Blender operations, but every emitted operation must be an admitted
verified write capability. No per-tool lifecycle is introduced here.
"""
from __future__ import annotations

from typing import Any, Callable, Sequence

from action_plan import ActionSpec
from planning.blender_capability_catalog import get_blender_capability
from planning.blender_corrective_runtime import BlenderCorrectiveRuntime


class ProductionMultiOperationCorrectiveTask:
    """Run a composed corrective plan through the generalized protected runtime."""

    def __init__(
        self,
        observe: Callable[[], Any],
        plan: Callable[[Any], Sequence[ActionSpec]],
        authorization_id: str,
        executor: Any = None,
    ) -> None:
        self._plan = plan
        self.runtime = BlenderCorrectiveRuntime(
            observe,
            self._validated_plan,
            authorization_id,
            executor=executor,
        )

    def _validated_plan(self, evidence: Any) -> list[ActionSpec]:
        actions = list(self._plan(evidence))
        for action in actions:
            if not isinstance(action, ActionSpec):
                raise TypeError("production corrective plans must contain ActionSpec values")
            capability = get_blender_capability(action.tool)
            if not capability.writes_scene or not capability.requires_verification:
                raise ValueError(
                    f"production corrective composition requires a verified Blender write capability: {action.tool}"
                )
        return actions

    def run(self, max_steps: int = 16):
        return self.runtime.run(max_steps=max_steps)
