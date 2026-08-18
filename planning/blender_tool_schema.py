"""Deterministic validation of Blender tool calls before execution."""
from dataclasses import dataclass
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class BlenderToolSchema:
    required: Mapping[str, Any]


BLENDER_TOOL_SCHEMAS = {
    "move_object": BlenderToolSchema({"object_name": str, "location": (list, tuple)}),
    "inspect_object": BlenderToolSchema({"object_name": str}),
    "inspect_object_relationship": BlenderToolSchema({"object_a": str, "object_b": str}),
    "inspect_scene": BlenderToolSchema({"file_name": str}),
    "inspect_scene_settings": BlenderToolSchema({"file_name": str}),
    "create_collection": BlenderToolSchema({"file_name": str, "collection_name": str}),
    "create_empty_marker": BlenderToolSchema({"file_name": str, "collection_name": str, "object_name": str}),
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
    if tool == "move_object":
        values = arguments["location"]
        if len(values) != 3:
            raise ValueError("location must contain exactly three numeric coordinates")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
            raise ValueError("location must contain exactly three numeric coordinates")
        snapshot["location"] = list(values) if isinstance(values, list) else tuple(values)
    if tool == "set_object_rotation":
        values = arguments["rotation_degrees"]
        if len(values) != 3:
            raise ValueError("rotation_degrees must contain exactly three numeric values")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
            raise ValueError("rotation_degrees must contain exactly three numeric values")
        snapshot["rotation_degrees"] = list(values) if isinstance(values, list) else tuple(values)
    return snapshot
