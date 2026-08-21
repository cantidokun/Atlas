"""Deterministic validation of Unreal tool calls before execution."""

from dataclasses import dataclass
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class UnrealToolSchema:
    required: Mapping[str, Any]


# Operation names currently produced by UnrealTaskPlanner.
# Every Unreal operation receives entity_ids and authorization_id. Write
# operations additionally validate their mutation payload at this boundary.
UNREAL_TOOL_SCHEMAS = {
    "inspect_target_actors": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str}),
    "verify_target_actor_mapping": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str}),
    "inspect_material_state": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str}),
    "apply_material_variant": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str}),
    "verify_material_variant": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str}),
    "set_actor_location": UnrealToolSchema({
        "entity_ids": (list, tuple),
        "authorization_id": str,
        "location": dict,
    }),
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
        if not isinstance(ids, (list, tuple)):
            raise TypeError("entity_ids must be a list or tuple")
        snapshot["entity_ids"] = tuple(ids)

    if not isinstance(snapshot.get("authorization_id"), str) or not snapshot["authorization_id"].strip():
        raise ValueError("authorization_id must be a non-empty string")

    if tool == "set_actor_location":
        location = snapshot["location"]
        if set(location.keys()) != {"x", "y", "z"}:
            raise ValueError("location must contain exactly x, y, and z")
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in location.values()
        ):
            raise TypeError("location coordinates must be numeric")
        snapshot["location"] = dict(location)

    return snapshot
