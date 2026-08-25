"""Structured result contract for Blender execution and verification."""

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class BlenderExecutionResult:
    """Immutable, normalized result returned by the Blender adapter."""

    tool: str
    ok: bool
    state: Any
    details: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.tool, str) or not self.tool.strip():
            raise ValueError("result tool must be a non-empty string")
        if not isinstance(self.ok, bool):
            raise TypeError("result ok must be boolean")
        if not isinstance(self.state, (str, Mapping)):
            raise TypeError("result state must be a string or object")
        if isinstance(self.state, str) and not self.state.strip():
            raise ValueError("result state must be a non-empty string")
        if isinstance(self.state, Mapping) and not self.state:
            raise ValueError("result state object must not be empty")
        if not isinstance(self.details, dict):
            raise TypeError("result details must be an object")


def normalize_blender_result(tool: str, result: Any) -> BlenderExecutionResult:
    """Normalize current and legacy adapter responses without losing state."""
    if not isinstance(result, dict):
        raise TypeError("Blender executor must return an object")

    if "ok" not in result and "status" in result:
        status = result["status"]
        if not isinstance(status, str) or not status.strip():
            raise ValueError("Blender result status must be a non-empty string")
        result = {
            "ok": status not in {"error", "failed", "failure"},
            "state": result.get("state", status),
            "details": {key: value for key, value in result.items() if key not in {"status", "state"}},
        }

    for key in ("ok", "state"):
        if key not in result:
            raise ValueError(f"Blender result missing required field: {key}")

    if result["ok"] is not True and result["ok"] is not False:
        raise TypeError("Blender result ok must be boolean")
    state = result["state"]
    if not isinstance(state, (str, Mapping)):
        raise TypeError("Blender result state must be a string or object")
    if isinstance(state, str) and not state.strip():
        raise ValueError("Blender result state must be a non-empty string")
    if isinstance(state, Mapping) and not state:
        raise ValueError("Blender result state object must not be empty")

    details = result.get("details", {})
    if not isinstance(details, dict):
        raise TypeError("Blender result details must be an object")

    return BlenderExecutionResult(tool, result["ok"], state, dict(details))
