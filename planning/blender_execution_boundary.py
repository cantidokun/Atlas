"""Safe Blender executor boundary used by the planning agent."""
from typing import Any, Dict, Protocol

from planning.blender_tool_schema import validate_blender_tool_call


class BlenderExecutor(Protocol):
    def __call__(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]: ...


class BlenderExecutionBoundary:
    """Validate every proposed Blender call before handing it to Blender."""

    def __init__(self, executor: BlenderExecutor):
        self._executor = executor

    def execute(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        validated = validate_blender_tool_call(tool, arguments)
        result = self._executor(tool, validated)
        if not isinstance(result, dict):
            raise TypeError("Blender executor must return an object")
        return result
