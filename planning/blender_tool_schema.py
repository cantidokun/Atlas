"""Deterministic validation of Blender tool calls before execution."""

from dataclasses import dataclass
from numbers import Real
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class BlenderToolSchema:
    required: Mapping[str, Any]


BLENDER_TOOL_SCHEMAS = {
    "move_object": BlenderToolSchema({"object_name": str, "location": (list, tuple)}),
    "inspect_object": BlenderToolSchema({"object_name": str}),
    "inspect_object_relationship": BlenderToolSchema({"object_a": str, "object_b": str}),
}


def _validate_required(name: str, value: Any, expected: Any) -> None:
    if not isinstance(value, expected):
        raise TypeError(f"argument {name} has invalid type")
    if name.startswith("object") and isinstance(value, str) and not value.strip():
        raise ValueError(f"argument {name} must not be empty")


def validate_blender_tool_call(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Return a defensive copy or raise before a Blender executor is reached."""
    if not isinstance(tool, str) or not tool.strip():
        raise ValueError("tool must be a non-empty string")
    if not isinstance(arguments, dict):
        raise TypeError("arguments must be an object")

    schema = BLENDER_TOOL_SCHEMAS.get(tool)
    if schema is None:
        raise ValueError(f"unsupported Blender tool: {tool}")

    for name, expected in schema.required.items():
        if name not in arguments:
            raise ValueError(f"missing required argument: {name}")
        _validate_required(name, arguments[name], expected)

    if tool == "move_object":
        location = arguments["location"]
        if len(location) != 3:
            raise ValueError("location must contain exactly three numeric coordinates")
        if not all(isinstance(value, Real) and not isinstance(value, bool) for value in location):
            raise ValueError("location must contain exactly three numeric coordinates")

    # Preserve the caller's supported sequence representation for compatibility,
    # while returning a new mapping so top-level mutations cannot affect execution.
    return dict(arguments)
