"""Tool executor that connects autonomous runtime steps to Blender safely."""

from typing import Any, Dict, Optional

from controller.command_registry import ControllerCommandRegistry, CommandRegistryError
from controller.blender_capabilities import create_blender_command_registry
from planning.blender_execution_boundary import BlenderExecutionBoundary, BlenderExecutor
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_result_contract import BlenderExecutionResult
from planning.blender_tool_adapter import BlenderToolAdapter


class BlenderAutonomousExecutor:
    """Adapt the verified Blender boundary to the autonomous ToolExecutor API."""

    def __init__(
        self,
        executor: Optional[BlenderExecutor] = None,
        command_registry: Optional[ControllerCommandRegistry] = None,
    ):
        self._adapter = executor if executor is not None else BlenderToolAdapter()
        self._boundary = BlenderExecutionBoundary(self._adapter)
        self._command_registry = command_registry or create_blender_command_registry()
        self._last_result: Optional[BlenderExecutionResult] = None
        self._last_receipt: Optional[BlenderExecutionReceipt] = None

    @property
    def last_result(self) -> Optional[BlenderExecutionResult]:
        return self._last_result

    @property
    def last_receipt(self) -> Optional[BlenderExecutionReceipt]:
        return self._last_receipt

    def capability_for(self, tool: str):
        try:
            return self._command_registry.resolve(tool)
        except CommandRegistryError as exc:
            raise ValueError(str(exc)) from exc

    def __call__(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        self.capability_for(tool)
        normalized, receipt = self._boundary.execute_with_receipt(tool, arguments)
        self._last_result = normalized
        self._last_receipt = receipt
        return {"ok": normalized.ok, "state": normalized.state, "details": dict(normalized.details)}

    def execute_authorized_replan(self, authorized_step: Any, fresh_evidence: Any):
        """Execute one authorized corrective step through the protected boundary."""
        actions = getattr(authorized_step, "actions", None)
        if not isinstance(actions, list) or len(actions) != 1:
            raise RuntimeError("authorized corrective execution requires exactly one ActionSpec")
        action = actions[0]
        self.capability_for(action.tool)
        normalized, receipt = self._boundary.execute_authorized_replan(authorized_step, fresh_evidence)
        self._last_result = normalized
        self._last_receipt = receipt
        return normalized, receipt

    def receipt_matches_last_execution(self, tool: str, arguments: Dict[str, Any]) -> bool:
        if self._last_result is None or self._last_receipt is None:
            return False
        return self._last_receipt.matches(tool, arguments, self._last_result)
