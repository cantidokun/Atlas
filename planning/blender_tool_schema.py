"""Deterministic validation of Blender tool calls before execution."""
from dataclasses import dataclass
from math import isfinite
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class BlenderToolSchema:
    required: Mapping[str, Any]


# This is the canonical argument surface for the public Blender tools.  The
# capability catalog and tools/__init__.py are tested against this registry so
# the autonomous agent cannot advertise a tool with no executable schema.
BLENDER_TOOL_SCHEMAS = {
    "inspect_scene": BlenderToolSchema({"file_name": str}),
    "inspect_mesh": BlenderToolSchema({"file_name": str, "object_name": str}),
    "inspect_scene_health": BlenderToolSchema({"file_name": str}),
    "inspect_scene_settings": BlenderToolSchema({"file_name": str}),
    "inspect_object_relationship": BlenderToolSchema({"file_name": str, "object1_name": str, "object2_name": str}),
    "inspect_soccer_components": BlenderToolSchema({"file_name": str}),
    "create_collection": BlenderToolSchema({"file_name": str, "collection_name": str}),
    "create_empty_marker": BlenderToolSchema({"file_name": str, "collection_name": str, "object_name": str}),
    "move_object": BlenderToolSchema({"file_name": str, "object_name": str, "location": (list, tuple)}),
    "inspect_object_parent": BlenderToolSchema({"file_name": str, "object_name": str}),
    "parent_object": BlenderToolSchema({"file_name": str, "child_name": str, "parent_name": str}),
    "inspect_object_collections": BlenderToolSchema({"file_name": str, "object_name": str}),
    "move_object_to_collection": BlenderToolSchema({"file_name": str, "object_name": str, "collection_name": str}),
    "rename_object": BlenderToolSchema({"file_name": str, "object_name": str, "new_name": str}),
    "delete_object": BlenderToolSchema({"file_name": str, "object_name": str}),
    "inspect_object_transform": BlenderToolSchema({"file_name": str, "object_name": str}),
    "set_object_rotation": BlenderToolSchema({"file_name": str, "object_name": str, "rotation_degrees": (list, tuple)}),
}


def validate_blender_tool_call(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a Blender call and create a safe snapshot of supported arguments."""
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
        if not isinstance(arguments[name], expected):
            raise TypeError(f"argument {name} has invalid type")
        if isinstance(arguments[name], str) and not arguments[name].strip():
            raise ValueError(f"argument {name} must not be empty")
    snapshot = dict(arguments)
    if tool in {"move_object", "set_object_rotation"}:
        field = "location" if tool == "move_object" else "rotation_degrees"
        values = arguments[field]
        if len(values) != 3:
            raise ValueError(f"{field} must contain exactly three numeric values")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
            raise ValueError(f"{field} must contain exactly three numeric values")
        if any(not isfinite(float(value)) for value in values):
            raise ValueError(f"{field} must contain only finite numeric values")
        snapshot[field] = list(values) if isinstance(values, list) else tuple(values)
    return snapshot
