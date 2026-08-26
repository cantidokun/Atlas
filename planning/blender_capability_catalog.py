"""Explicit capability metadata for Atlas Blender tools.

The catalog is intentionally separate from argument validation. Schemas answer
"is this call well formed?"; this catalog answers "what authority does this
capability require?". Keeping those questions separate prevents transport code
from becoming an authorization system.
"""
from dataclasses import dataclass
from typing import Dict, FrozenSet

from planning.blender_tool_schema import BLENDER_TOOL_SCHEMAS


@dataclass(frozen=True)
class BlenderCapability:
    name: str
    writes_scene: bool
    requires_verification: bool


_READ_ONLY: FrozenSet[str] = frozenset(
    {
        "inspect_scene",
        "inspect_mesh",
        "inspect_scene_health",
        "inspect_scene_settings",
        "inspect_object_relationship",
        "inspect_soccer_components",
        "inspect_object_parent",
        "inspect_object_collections",
        "inspect_object_transform",
    }
)

_WRITE: FrozenSet[str] = frozenset(
    {
        "create_collection",
        "create_empty_marker",
        "move_object",
        "parent_object",
        "move_object_to_collection",
        "rename_object",
        "delete_object",
        "set_object_rotation",
    }
)

if _READ_ONLY & _WRITE:
    raise RuntimeError("Blender capability cannot be both read-only and write-capable")
if _READ_ONLY | _WRITE != frozenset(BLENDER_TOOL_SCHEMAS):
    raise RuntimeError("Blender capability catalog must cover every registered tool")


BLENDER_CAPABILITIES: Dict[str, BlenderCapability] = {
    name: BlenderCapability(
        name=name,
        writes_scene=name in _WRITE,
        requires_verification=name in _WRITE,
    )
    for name in BLENDER_TOOL_SCHEMAS
}


def get_blender_capability(tool: str) -> BlenderCapability:
    """Return explicit authority metadata for one registered Blender tool."""
    try:
        return BLENDER_CAPABILITIES[tool]
    except KeyError as exc:
        raise ValueError(f"Unknown Blender capability: {tool}") from exc


def require_verified_blender_write(tool: str) -> BlenderCapability:
    """Return a capability only when it is an admitted verified scene write.

    This is the single catalog-level gate used by Blender write authorization.
    Keeping the policy here prevents individual authorization callers from
    independently deciding what constitutes a production write capability.
    """
    capability = get_blender_capability(tool)
    if not capability.writes_scene or not capability.requires_verification:
        raise ValueError(
            f"verified Blender write capability required: scene-writing capability is not admitted for {tool}"
        )
    return capability


def is_blender_write(tool: str) -> bool:
    return get_blender_capability(tool).writes_scene
