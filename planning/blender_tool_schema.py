"""Deterministic validation of Blender tool calls before execution."""

from dataclasses import dataclass
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class BlenderToolSchema:
    required: Mapping[str, type]


BLENDER_TOOL_SCHEMAS = {
    "move_object": BlenderToolSchema({"object_name": str, "location": (list, tuple)}),
    "inspect_object": BlenderToolSchema({"object_name": str}),
    "inspect_object_relationship": BlenderToolSchema({"object_a": str, "object_b": str}),
}


def validate_blender_tool_call(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Return normalized arguments or raise before an executor is reached."""
    if not isinstance(tool, str) or not tool:
        raise ValueError("tool must be a non-empty string")
    if not isinstance(arguments, dict):
        raise TypeError("arguments must be an object")
    schema = BLENDER_TOOL_SCHEMAS.get(tool)
    if schema is None:
        raise ValueError(f"unsupported Blender tool: {tool}")
    for name, expected in schema.required.items():
        if name not in arguments:
            raise ValueError(f"missing required argument: {name}")
        if not isinstance(arguments[name], expected):
            raise TypeError(f"argument {name} has invalid type")
    if tool == "move_object":
        location = arguments["location"]
        if len(location) != 3 or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in location):
            raise ValueError("location must contain exactly three numeric coordinates")
    return dict(arguments)
