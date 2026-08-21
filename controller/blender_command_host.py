"""Blender-side command host for Atlas's transport-independent gateway."""

from __future__ import annotations

from typing import Any, Dict

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_tool_executor import BlenderToolExecutor


class BlenderCommandHost:
    """Adapt gateway commands into the existing validated Blender boundary."""

    def __init__(self, executor: BlenderToolExecutor | None = None):
        self._executor = executor or BlenderToolExecutor()
        self._boundary = BlenderExecutionBoundary(self._executor.execute)

    def handle(self, session_id: str, request_id: str, command: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(command, dict):
            raise ValueError("command must be an object")
        tool = command.get("command")
        arguments = command.get("arguments", {})
        result = self._boundary.execute_verified(tool, arguments)
        return {
            "session_id": session_id,
            "request_id": request_id,
            "tool": tool,
            "result": result,
        }
