"""Safe Blender executor boundary used by the planning agent."""
from typing import Any, Dict, Protocol

from planning.blender_result_contract import BlenderExecutionResult, normalize_blender_result
from planning.blender_tool_schema import validate_blender_tool_call


class BlenderExecutor(Protocol):
    def __call__(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]: ...


class BlenderExecutionBoundary:
    """Validate calls and normalize adapter results before Atlas consumes them."""

    def __init__(self, executor: BlenderExecutor):
        self._executor = executor

    def execute(self, tool: str, arguments: Dict[str, Any]) -> BlenderExecutionResult:
        validated = validate_blender_tool_call(tool, arguments)
        result = self._executor(tool, validated)
        return normalize_blender_result(tool, result)
