from .blender import (
    inspect_scene,
    inspect_mesh,
    inspect_scene_health,
    inspect_scene_settings,
    inspect_object_relationship,
    inspect_soccer_components,
    create_collection,
    create_empty_marker,
    move_object
)
from .blender_relationship import (
    inspect_object_parent,
    parent_object
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
    "inspect_object_parent": inspect_object_parent,
    "parent_object": parent_object,
}
