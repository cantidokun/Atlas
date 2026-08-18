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
from .blender_collection import (
    inspect_object_collections,
    move_object_to_collection,
)
from .blender_object import rename_object
from .blender_delete import delete_object
from .blender_transform import inspect_object_transform, set_object_rotation


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
    "inspect_object_collections": inspect_object_collections,
    "move_object_to_collection": move_object_to_collection,
    "rename_object": rename_object,
    "delete_object": delete_object,
    "inspect_object_transform": inspect_object_transform,
    "set_object_rotation": set_object_rotation,
}
