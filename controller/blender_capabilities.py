"""Explicit capability catalog for the Atlas Blender Agent.

The catalog is intentionally independent of Blender imports. It describes what
an autonomous controller is permitted to ask the Blender execution boundary
to do; the execution boundary remains responsible for argument validation,
execution, independent verification, and receipts.
"""

from __future__ import annotations

from controller.command_registry import CommandCapability, ControllerCommandRegistry


BLENDER_CAPABILITIES = (
    # Read-only evidence acquisition. These correspond to the current public
    # Blender tool surface in tools/__init__.py.
    CommandCapability("inspect_scene", "blender.scene.read"),
    CommandCapability("inspect_mesh", "blender.mesh.read"),
    CommandCapability("inspect_scene_health", "blender.scene.read"),
    CommandCapability("inspect_scene_settings", "blender.scene.read"),
    CommandCapability("inspect_object_relationship", "blender.relationship.read"),
    CommandCapability("inspect_soccer_components", "blender.scene.read"),
    CommandCapability("inspect_object_parent", "blender.relationship.read"),
    CommandCapability("inspect_object_collections", "blender.collection.read"),
    CommandCapability("inspect_object_transform", "blender.transform.read"),

    # State-changing operations. These must remain behind the controller's
    # authorization/verification path; the mutates_state flag is declarative.
    CommandCapability("create_collection", "blender.collection.write", mutates_state=True),
    CommandCapability("create_empty_marker", "blender.object.write", mutates_state=True),
    CommandCapability("move_object", "blender.transform.write", mutates_state=True),
    CommandCapability("parent_object", "blender.relationship.write", mutates_state=True),
    CommandCapability("move_object_to_collection", "blender.collection.write", mutates_state=True),
    CommandCapability("rename_object", "blender.object.write", mutates_state=True),
    CommandCapability("delete_object", "blender.object.write", mutates_state=True),
    CommandCapability("set_object_rotation", "blender.transform.write", mutates_state=True),
)


def create_blender_command_registry() -> ControllerCommandRegistry:
    """Return a fresh fail-closed registry for the current Blender tool surface."""
    return ControllerCommandRegistry(BLENDER_CAPABILITIES)
