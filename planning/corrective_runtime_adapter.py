"""Bridge reusable corrective recovery into the autonomous runtime boundary."""
from __future__ import annotations

from typing import Any, Callable, Sequence, Union

from action_plan import ActionSpec
from planning.autonomous_corrective_task import AutonomousCorrectiveTask, CorrectiveTaskResult
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_result_contract import normalize_blender_result
from planning.replan_authorization import ReplanAuthorization


class _GenericCorrectiveBoundary:
    """Boundary for explicitly injected, non-Blender corrective simulations."""

    def __init__(self, executor: Callable[[str, dict[str, Any]], dict[str, Any]]):
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
        normalized = normalize_blender_result(action.tool, self._executor(action.tool, dict(action.arguments)))
        receipt = BlenderExecutionReceipt.create_authorized(
            action.tool, action.arguments, normalized, authorization.authorization_id
        )
        return normalized, receipt


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
                _GenericCorrectiveBoundary(boundary), observe, plan, authorization_id
            )
        else:
            raise TypeError("boundary must be BlenderExecutionBoundary or corrective executor callable")

    def run(self, max_steps: int = 16) -> CorrectiveTaskResult:
        """Run until convergence or the explicit correction budget is exhausted."""
        return self.task.run(max_steps=max_steps)

    @property
    def boundary(self):
        return self.task.boundary
