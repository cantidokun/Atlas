from .blender import (
    inspect_scene,
    inspect_mesh,
    inspect_scene_health,
    inspect_scene_settings,
    inspect_object_relationship,
    inspect_soccer_components,
    create_collection,
    create_empty_marker,
    move_object,
)


TOOLS = {
    "inspect_scene": inspect_scene,
    "inspect_mesh": inspect_mesh,
    "inspect_scene_health": inspect_scene_health,
    "inspect_scene_settings": inspect_scene_settings,
    "inspect_object_relationship": inspect_object_relationship,
    "inspect_soccer_components": inspect_soccer_components,
    "create_collection": create_collection,
    "create_empty_marker": create_empty_marker,
    "move_object": move_object,
}

# Trusted Python-side capability metadata. The model never supplies this.
READ_ONLY_TOOLS = {
    "inspect_scene",
    "inspect_mesh",
    "inspect_scene_health",
    "inspect_scene_settings",
    "inspect_object_relationship",
    "inspect_soccer_components",
}

WRITE_TOOLS = {
    "create_collection",
    "create_empty_marker",
    "move_object",
}

ALL_TOOLS = set(TOOLS)

if READ_ONLY_TOOLS | WRITE_TOOLS != ALL_TOOLS:
    raise RuntimeError("Every Atlas tool must have an explicit capability classification.")
if READ_ONLY_TOOLS & WRITE_TOOLS:
    raise RuntimeError("Atlas tool capability classifications must not overlap.")
