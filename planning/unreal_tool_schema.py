"""Deterministic validation of Unreal tool calls before execution."""

from dataclasses import dataclass
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class UnrealToolSchema:
    required: Mapping[str, Any]


UNREAL_TOOL_SCHEMAS = {
    "inspect_target_actors": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str}),
    "verify_target_actor_mapping": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str}),
    "inspect_material_state": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str}),
    "apply_material_variant": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "material_variant": dict}),
    "verify_material_variant": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "material_variant": dict}),
    "inspect_niagara_state": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str}),
    "apply_niagara_variant": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "niagara_variant": dict}),
    "verify_niagara_variant": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "niagara_variant": dict}),
    "set_actor_location": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "location": dict}),
    "set_actor_rotation": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "rotation": dict}),
    "set_actor_scale": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "scale": dict}),
}


def validate_unreal_tool_call(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Validate an Unreal call and return a safe snapshot of supported arguments."""
    if not isinstance(tool, str) or not tool.strip():
        raise ValueError("tool must be a non-empty string")
    if not isinstance(arguments, dict):
        raise TypeError("arguments must be an object")
    schema = UNREAL_TOOL_SCHEMAS.get(tool)
    if schema is None:
        raise ValueError(f"unsupported Unreal tool: {tool}")
    for name, expected in schema.required.items():
        if name not in arguments:
            raise ValueError(f"missing required argument: {name}")
        if not isinstance(arguments[name], expected):
            raise TypeError(f"argument {name} has invalid type")

    snapshot = dict(arguments)
    ids = snapshot.get("entity_ids")
    if ids is not None:
        snapshot["entity_ids"] = tuple(ids)
    if not isinstance(snapshot.get("authorization_id"), str) or not snapshot["authorization_id"].strip():
        raise ValueError("authorization_id must be a non-empty string")

    if tool in {"apply_material_variant", "verify_material_variant", "apply_niagara_variant", "verify_niagara_variant"}:
        key = "material_variant" if "material" in tool else "niagara_variant"
        variant = snapshot[key]
        if set(variant.keys()) != {"name"}:
            raise ValueError(f"{key} must contain exactly name")
        if not isinstance(variant["name"], str) or not variant["name"].strip():
            raise ValueError(f"{key}.name must be a non-empty string")
        snapshot[key] = {"name": variant["name"].strip()}

    for tool_name, key, axes, label, error in (
        ("set_actor_location", "location", {"x", "y", "z"}, "location", "location coordinates must be numeric"),
        ("set_actor_rotation", "rotation", {"pitch", "yaw", "roll"}, "rotation", "rotation angles must be numeric"),
        ("set_actor_scale", "scale", {"x", "y", "z"}, "scale", "scale components must be numeric"),
    ):
        if tool == tool_name:
            vector = snapshot[key]
            if set(vector.keys()) != axes:
                raise ValueError(f"{label} must contain exactly {', '.join(sorted(axes))}")
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in vector.values()):
                raise TypeError(error)
            snapshot[key] = dict(vector)

    return snapshot
