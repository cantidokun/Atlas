"""Deterministic validation of Unreal tool calls before execution."""

from dataclasses import dataclass
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class UnrealToolSchema:
    required: Mapping[str, Any]


# Operation names currently produced by UnrealTaskPlanner.
# All Unreal operations in the current execution path receive both
# entity_ids and an authorization_id, so the schema requires both.
UNREAL_TOOL_SCHEMAS = {
    "inspect_target_actors": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str}),
    "verify_target_actor_mapping": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str}),
    "inspect_material_state": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str}),
    "apply_material_variant": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str}),
    "verify_material_variant": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str}),
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

    # Preserve tuple/list distinction like the Blender equivalent, but
    # normalize entity_ids to a tuple so callers can rely on Atlas's usual
    # immutable identity representation.
    ids = snapshot.get("entity_ids")
    if ids is not None:
        if not isinstance(ids, (list, tuple)):
            raise TypeError("entity_ids must be a list or tuple")
        snapshot["entity_ids"] = tuple(ids)

    # authorization_id is required by the current executor and adapter. Only
    # type-check it here; the executor already enforces non-empty earlier.
    if not isinstance(snapshot.get("authorization_id"), str) or not snapshot["authorization_id"].strip():
        raise ValueError("authorization_id must be a non-empty string")

    return snapshot
