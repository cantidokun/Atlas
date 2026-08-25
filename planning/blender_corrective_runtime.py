"""Runtime adapter for reusable corrective tasks on the protected Blender executor."""
from __future__ import annotations

from typing import Any, Callable, Optional, Sequence, Union

from action_plan import ActionSpec
from planning.autonomous_corrective_task import AutonomousCorrectiveTask, CorrectiveTaskResult
from planning.blender_autonomous_executor import BlenderAutonomousExecutor
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_result_contract import normalize_blender_result
from planning.replan_authorization import ReplanAuthorization

Executor = Union[
    BlenderAutonomousExecutor,
    Callable[[str, dict[str, Any]], dict[str, Any]],
]


class _InjectedCorrectiveExecutorBoundary:
    """Compatibility boundary for explicit in-memory corrective test executors.

    The production Blender path remains BlenderExecutionBoundary, including its
    canonical tool schema.  This adapter exists only so older injected callable
    executors used by deterministic corrective-runtime tests can model arbitrary
    state transitions (for example ``set_value``) without making those names
    executable Blender capabilities.
    """

    def __init__(self, executor: Callable[[str, dict[str, Any]], dict[str, Any]]):
        self._executor = executor

    def execute_authorized_replan(self, authorized_step: Any, fresh_evidence: Any):
        actions = getattr(authorized_step, "actions", None)
        authorization = getattr(authorized_step, "authorization", None)
        if not isinstance(actions, list) or len(actions) != 1 or not isinstance(actions[0], ActionSpec):
            raise RuntimeError("authorized corrective execution requires exactly one ActionSpec")
        if not isinstance(authorization, ReplanAuthorization):
            raise RuntimeError("corrective replan requires ReplanAuthorization")
        if not authorization.matches(fresh_evidence, actions):
            raise RuntimeError("corrective replan authorization is stale or invalid")

        action = actions[0]
        raw = self._executor(action.tool, dict(action.arguments))
        normalized = normalize_blender_result(action.tool, raw)
        receipt = BlenderExecutionReceipt.create_authorized(
            action.tool,
            action.arguments,
            normalized,
            authorization.authorization_id,
        )
        return normalized, receipt


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
        self.executor = raw_executor
        if isinstance(raw_executor, BlenderExecutionBoundary):
            boundary = raw_executor
        elif isinstance(raw_executor, BlenderAutonomousExecutor):
            boundary = raw_executor._boundary
        else:
            boundary = _InjectedCorrectiveExecutorBoundary(raw_executor)
        self.task = AutonomousCorrectiveTask(
            boundary,
            observe,
            plan,
            authorization_id,
        )

    def run(self, max_steps: int = 16) -> CorrectiveTaskResult:
        return self.task.run(max_steps=max_steps)
