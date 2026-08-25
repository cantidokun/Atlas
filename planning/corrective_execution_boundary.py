"""Generic authorized execution boundary for non-Blender corrective tasks."""
from __future__ import annotations

from typing import Any, Callable, Dict

from planning.action_plan import ActionSpec
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_result_contract import BlenderExecutionResult, normalize_blender_result
from planning.replan_authorization import ReplanAuthorization


class CorrectiveExecutionBoundary:
    """Normalize and receipt-bind injected corrective executors without Blender tool assumptions."""

    def __init__(self, executor: Callable[[str, Dict[str, Any]], Dict[str, Any]]):
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
        result = self._executor(action.tool, dict(action.arguments))
        if not isinstance(result, dict):
            raise TypeError("corrective executor must return an object")
        normalized = normalize_blender_result(action.tool, result)
        receipt = BlenderExecutionReceipt.create_authorized(
            action.tool,
            action.arguments,
            normalized,
            authorization.authorization_id,
        )
        return normalized, receipt
