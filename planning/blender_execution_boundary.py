"""Safe Blender executor boundary used by the planning agent."""
from typing import Any, Dict, Protocol

from planning.action_plan import ActionSpec
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_result_contract import BlenderExecutionResult, normalize_blender_result
from planning.blender_tool_schema import validate_blender_tool_call
from planning.blender_verification import verify_blender_execution
from planning.blender_write_authorization import BlenderWriteAuthorization
from planning.replan_authorization import ReplanAuthorization


class BlenderExecutor(Protocol):
    def __call__(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]: ...


class BlenderExecutionBoundary:
    """Validate, execute, verify, and receipt-bind Blender calls."""

    def __init__(self, executor: BlenderExecutor):
        self._executor = executor

    def execute(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Backward-compatible execution API returning the raw adapter object."""
        validated = validate_blender_tool_call(tool, arguments)
        result = self._executor(tool, validated)
        if not isinstance(result, dict):
            raise TypeError("Blender executor must return an object")
        return result

    def execute_verified(self, tool: str, arguments: Dict[str, Any]) -> BlenderExecutionResult:
        """Execute and require a successful result for the requested Blender tool."""
        validated = validate_blender_tool_call(tool, arguments)
        result = self._executor(tool, validated)
        normalized = normalize_blender_result(tool, result)
        return verify_blender_execution(normalized, tool)

    def execute_with_receipt(self, tool: str, arguments: Dict[str, Any]):
        """Execute successfully and return the verified result plus an immutable receipt."""
        validated = validate_blender_tool_call(tool, arguments)
        result = self._executor(tool, validated)
        normalized = verify_blender_execution(normalize_blender_result(tool, result), tool)
        receipt = BlenderExecutionReceipt.create(tool, validated, normalized)
        return normalized, receipt

    def execute_authorized_write(
        self,
        action: ActionSpec,
        authorization: BlenderWriteAuthorization,
    ):
        """Execute exactly one explicitly authorized Blender scene write."""
        if not isinstance(action, ActionSpec):
            raise TypeError("action must be an ActionSpec")
        if not isinstance(authorization, BlenderWriteAuthorization):
            raise TypeError("authorization must be BlenderWriteAuthorization")
        if not authorization.matches(action):
            raise RuntimeError("Blender write authorization is stale or invalid")
        capability = authorization.tool
        return self.execute_with_receipt(capability, action.arguments)

    def execute_authorized_replan(self, replan: Any, current_evidence: Any):
        """Execute one corrective action only after fresh-evidence-bound authorization is revalidated."""
        actions = getattr(replan, "actions", None)
        authorization = getattr(replan, "authorization", None)
        if not isinstance(actions, list) or len(actions) != 1 or not isinstance(actions[0], ActionSpec):
            raise RuntimeError("authorized corrective execution requires exactly one ActionSpec")
        if not isinstance(authorization, ReplanAuthorization):
            raise RuntimeError("corrective replan requires ReplanAuthorization")
        if not authorization.matches(current_evidence, actions):
            raise RuntimeError("corrective replan authorization is stale or invalid")

        action = actions[0]
        return self.execute_with_receipt(action.tool, action.arguments)
