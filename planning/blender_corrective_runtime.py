"""Runtime adapter for reusable corrective tasks on the protected Blender executor."""
from __future__ import annotations

from typing import Any, Callable, Optional, Union

from planning.action_plan import ActionSpec
from planning.autonomous_corrective_task import AutonomousCorrectiveTask, CorrectiveTaskResult
from planning.blender_autonomous_executor import BlenderAutonomousExecutor
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_result_contract import normalize_blender_result
from planning.corrective_execution_boundary import CorrectiveExecutionBoundary
from planning.replan_authorization import ReplanAuthorization

Executor = Union[
    BlenderAutonomousExecutor,
    BlenderExecutionBoundary,
    Callable[[str, dict[str, Any]], dict[str, Any]],
]


class _InjectedAuthorizedExecutorBoundary:
    """Compatibility boundary for explicitly injected authorized test executors.

    These executors already own the replan authorization protocol, but older
    injected implementations may return raw result/receipt-shaped dictionaries.
    Normalize those values here so the task loop always consumes the canonical
    Blender result and immutable receipt contracts.
    """

    def __init__(self, executor: Any):
        self._executor = executor

    def execute_authorized_replan(self, replan: Any, current_evidence: Any):
        actions = getattr(replan, "actions", None)
        authorization = getattr(replan, "authorization", None)
        if not isinstance(actions, list) or len(actions) != 1 or not isinstance(actions[0], ActionSpec):
            raise RuntimeError("authorized corrective execution requires exactly one ActionSpec")
        if not isinstance(authorization, ReplanAuthorization):
            raise RuntimeError("corrective replan requires ReplanAuthorization")
        if not authorization.matches(current_evidence, actions):
            raise RuntimeError("corrective replan authorization is stale or invalid")

        action = actions[0]
        raw_result, raw_receipt = self._executor.execute_authorized_replan(replan, current_evidence)
        normalized = normalize_blender_result(action.tool, raw_result)
        if isinstance(raw_receipt, BlenderExecutionReceipt):
            receipt = raw_receipt
        else:
            receipt = BlenderExecutionReceipt.create_authorized(
                action.tool,
                action.arguments,
                normalized,
                authorization.authorization_id,
            )
        return normalized, receipt


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
        elif hasattr(raw_executor, "execute_authorized_replan") and callable(raw_executor.execute_authorized_replan):
            boundary = _InjectedAuthorizedExecutorBoundary(raw_executor)
        else:
            raise TypeError(
                "executor must be BlenderAutonomousExecutor, BlenderExecutionBoundary, "
                "authorized corrective executor, or callable"
            )
        self.task = AutonomousCorrectiveTask(
            boundary,
            observe,
            plan,
            authorization_id,
        )

    def run(self, max_steps: int = 16) -> CorrectiveTaskResult:
        return self.task.run(max_steps=max_steps)
