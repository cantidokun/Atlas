"""Controlled adapter from authorized Atlas calls to concrete Blender tools.

The adapter resolves an already-authorized tool name to an explicit concrete
capability and forwards the validated argument snapshot unchanged. Legacy
Blender response shapes are normalized into the shared execution-result
contract at this boundary.
"""

from types import MappingProxyType
from typing import Any, Callable, Dict, Mapping, Optional

from planning.blender_result_contract import BlenderExecutionResult, normalize_blender_result
from tools import TOOLS


BlenderTool = Callable[..., Dict[str, Any]]


class BlenderToolAdapter:
    """Expose only an explicit, immutable set of concrete Blender tools."""

    def __init__(self, tools: Optional[Mapping[str, BlenderTool]] = None):
        registry = dict(TOOLS if tools is None else tools)
        if not registry:
            raise ValueError("Blender tool adapter requires at least one capability")
        for name, tool in registry.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Blender tool capability names must be non-empty strings")
            if not callable(tool):
                raise TypeError(f"Blender tool capability is not callable: {name}")
        self._tools = MappingProxyType(registry)

    @property
    def supported_tools(self):
        return tuple(sorted(self._tools))

    @staticmethod
    def _normalize_result(result: Dict[str, Any]) -> Dict[str, Any]:
        """Preserve the historical dict helper used by adapter contract tests.

        The public adapter dispatch path returns the canonical
        ``BlenderExecutionResult``. This compatibility helper intentionally
        retains its historical mapping contract for callers that use it
        directly.
        """
        if not isinstance(result, dict):
            raise TypeError("Blender adapter result must be an object")
        if "ok" in result:
            if not isinstance(result["ok"], bool):
                raise TypeError("Blender result ok must be boolean")
            if "state" not in result:
                raise ValueError("Blender result missing required field: state")
            if "details" not in result:
                result["details"] = {}
            if not isinstance(result["details"], dict):
                raise TypeError("Blender result details must be an object")
            return result
        return normalize_blender_result("adapter", result).__dict__.copy()

    def __call__(self, tool: str, arguments: Dict[str, Any]) -> BlenderExecutionResult:
        """Dispatch one already-authorized call without altering its payload."""
        if not isinstance(tool, str) or not tool.strip():
            raise ValueError("tool must be a non-empty string")
        if not isinstance(arguments, dict):
            raise TypeError("arguments must be an object")
        implementation = self._tools.get(tool)
        if implementation is None:
            raise ValueError(f"Blender adapter does not expose capability: {tool}")
        raw = implementation(**dict(arguments))
        return normalize_blender_result(tool, raw)
