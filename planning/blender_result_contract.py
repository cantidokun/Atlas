"""Structured result contract for Blender execution and verification."""

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class BlenderExecutionResult:
    """Immutable, normalized result returned by the Blender adapter."""

    tool: str
    ok: bool
    state: str
    details: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.tool, str) or not self.tool.strip():
            raise ValueError("result tool must be a non-empty string")
        if not isinstance(self.ok, bool):
            raise TypeError("result ok must be boolean")
        if not isinstance(self.state, str) or not self.state.strip():
            raise ValueError("result state must be a non-empty string")
        if not isinstance(self.details, dict):
            raise TypeError("result details must be an object")


def normalize_blender_result(tool: str, result: Any) -> BlenderExecutionResult:
    """Normalize an adapter response without allowing malformed results through."""
    if not isinstance(result, dict):
        raise TypeError("Blender executor must return an object")

    required = ("ok", "state")
    for key in required:
        if key not in result:
            raise ValueError(f"Blender result missing required field: {key}")

    if result["ok"] is not True and result["ok"] is not False:
        raise TypeError("Blender result ok must be boolean")
    if not isinstance(result["state"], str) or not result["state"].strip():
        raise ValueError("Blender result state must be a non-empty string")

    details = result.get("details", {})
    if not isinstance(details, dict):
        raise TypeError("Blender result details must be an object")

    return BlenderExecutionResult(tool, result["ok"], result["state"], dict(details))
