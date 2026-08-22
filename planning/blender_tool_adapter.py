"""Controlled adapter from authorized Atlas calls to concrete Blender tools.

The adapter is intentionally narrower than the execution boundary: it does not
validate plans, grant authorization, or perform verification. Those concerns
remain owned by the existing planning/execution machinery. Its job is only to
resolve an already-authorized tool name to an explicit capability and convert
the concrete tool response into the result shape consumed by that machinery.
"""

from types import MappingProxyType
from typing import Any, Callable, Dict, Mapping, Optional

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
        """Return the adapter's immutable capability names."""
        return tuple(sorted(self._tools))

    def __call__(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute one already-authorized tool without expanding its arguments."""
        if not isinstance(tool, str) or not tool.strip():
            raise ValueError("tool must be a non-empty string")
        if not isinstance(arguments, dict):
            raise TypeError("arguments must be an object")

        implementation = self._tools.get(tool)
        if implementation is None:
            raise ValueError(f"Blender adapter does not expose capability: {tool}")

        # Boundary validation has already produced the authoritative argument
        # snapshot. Copy only the mapping container so the tool cannot mutate the
        # caller's dictionary; values themselves are passed exactly as supplied.
        request = dict(arguments)
        raw = implementation(**request)
        return self._normalize(tool, raw)

    @staticmethod
    def _normalize(tool: str, raw: Any) -> Dict[str, Any]:
        """Convert concrete Blender output to the shared result contract input."""
        if not isinstance(raw, dict):
            raise TypeError(f"Blender tool {tool} returned a non-object response")

        # Allow test doubles or future concrete tools that already speak the
        # contract, while still rejecting malformed contract fields.
        if "ok" in raw or "state" in raw:
            if "ok" not in raw or "state" not in raw:
                raise ValueError(f"Blender tool {tool} returned a partial result contract")
            if not isinstance(raw["ok"], bool):
                raise TypeError(f"Blender tool {tool} returned a non-boolean ok field")
            if not isinstance(raw["state"], str) or not raw["state"].strip():
                raise ValueError(f"Blender tool {tool} returned an invalid state field")
            details = raw.get("details", {})
            if not isinstance(details, dict):
                raise TypeError(f"Blender tool {tool} returned non-object details")
            return {"ok": raw["ok"], "state": raw["state"], "details": dict(details)}

        if "error" in raw:
            return {"ok": False, "state": "error", "details": dict(raw)}

        status = raw.get("status")
        if status is not None:
            if not isinstance(status, str) or not status.strip():
                raise TypeError(f"Blender tool {tool} returned an invalid status")
            state = status
        else:
            state = "observed"

        return {"ok": True, "state": state, "details": dict(raw)}
