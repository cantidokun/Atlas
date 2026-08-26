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
    "verify_actor_location": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "expected_location": dict}),
    "set_actor_rotation": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "rotation": dict}),
    "verify_actor_rotation": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "expected_rotation": dict}),
    "set_actor_scale": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "scale": dict}),
    "verify_actor_scale": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "expected_scale": dict}),
    "inspect_sequencer_state": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str}),
    "set_sequencer_playback_range": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "start_frame": int, "end_frame": int}),
    "verify_sequencer_playback_range": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "expected_start_frame": int, "expected_end_frame": int}),
    "inspect_blueprint_state": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "asset_path": str}),
    "set_blueprint_metadata": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "asset_path": str, "metadata_key": str, "metadata_value": str}),
    "compile_blueprint": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "asset_path": str}),
    "verify_blueprint_state": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "asset_path": str, "expected_compile_status": str}),
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
    if tool in {"inspect_blueprint_state", "set_blueprint_metadata", "compile_blueprint", "verify_blueprint_state"}:
        asset_path = snapshot["asset_path"]
        if not asset_path.strip() or not asset_path.startswith("/"):
            raise ValueError("asset_path must be a non-empty Unreal package path")
        snapshot["asset_path"] = asset_path.strip()
        if tool == "set_blueprint_metadata":
            for field in ("metadata_key", "metadata_value"):
                value = snapshot[field]
                if not value.strip():
                    raise ValueError(f"{field} must be a non-empty string")
                snapshot[field] = value.strip()
        if tool == "verify_blueprint_state":
            status = snapshot["expected_compile_status"]
            if not status.strip():
                raise ValueError("expected_compile_status must be a non-empty string")
            snapshot["expected_compile_status"] = status.strip()
    for tool_name, field, label in (
        ("apply_material_variant", "material_variant", "material_variant"),
        ("verify_material_variant", "material_variant", "material_variant"),
        ("apply_niagara_variant", "niagara_variant", "niagara_variant"),
        ("verify_niagara_variant", "niagara_variant", "niagara_variant"),
    ):
        if tool == tool_name:
            value = snapshot[field]
            if not isinstance(value, dict) or set(value.keys()) != {"name"}:
                raise ValueError(f"{label} must contain exactly name")
            if not isinstance(value["name"], str) or not value["name"].strip():
                raise ValueError(f"{label}.name must be a non-empty string")
            snapshot[field] = {"name": value["name"].strip()}
    for tool_name, field, axes, message in (
        ("set_actor_location", "location", {"x", "y", "z"}, "location coordinates must be numeric"),
        ("verify_actor_location", "expected_location", {"x", "y", "z"}, "expected location coordinates must be numeric"),
        ("set_actor_rotation", "rotation", {"pitch", "yaw", "roll"}, "rotation angles must be numeric"),
        ("verify_actor_rotation", "expected_rotation", {"pitch", "yaw", "roll"}, "expected rotation angles must be numeric"),
        ("set_actor_scale", "scale", {"x", "y", "z"}, "scale components must be numeric"),
        ("verify_actor_scale", "expected_scale", {"x", "y", "z"}, "expected scale components must be numeric"),
    ):
        if tool == tool_name:
            value = snapshot[field]
            if not isinstance(value, dict) or set(value.keys()) != axes:
                label = "x, y, and z" if field in {"location", "expected_location", "scale", "expected_scale"} else "pitch, yaw, and roll"
                raise ValueError(f"{field} must contain exactly {label}")
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in value.values()):
                raise TypeError(message)
            snapshot[field] = dict(value)
    if tool in {"set_sequencer_playback_range", "verify_sequencer_playback_range"}:
        start_key = "start_frame" if tool == "set_sequencer_playback_range" else "expected_start_frame"
        end_key = "end_frame" if tool == "set_sequencer_playback_range" else "expected_end_frame"
        start_frame = snapshot[start_key]
        end_frame = snapshot[end_key]
        if isinstance(start_frame, bool) or not isinstance(start_frame, int):
            raise TypeError(f"{start_key} must be an integer")
        if isinstance(end_frame, bool) or not isinstance(end_frame, int):
            raise TypeError(f"{end_key} must be an integer")
        if start_frame > end_frame:
            raise ValueError("Sequencer start frame must not exceed end frame")
    return snapshot
