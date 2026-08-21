"""Explicit bridge from authorized Blender tool names to local adapters.

This module is the first execution-side seam between Atlas's validated action
model and the concrete Blender adapter functions. It deliberately uses an
explicit allow-list instead of dynamic attribute lookup so a model cannot turn
an arbitrary string into executable Python.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping

from tools import blender
from tools import blender_transform


BlenderToolHandler = Callable[..., Dict[str, Any]]


class BlenderToolExecutorError(ValueError):
    """Raised when a tool cannot be dispatched through the approved surface."""


# Keep this mapping explicit. Adding a tool here requires a corresponding
# capability and canonical schema entry before it can become executable.
BLENDER_TOOL_HANDLERS: Mapping[str, BlenderToolHandler] = {
    "inspect_scene": blender.inspect_scene,
    "inspect_mesh": blender.inspect_mesh,
    "inspect_scene_health": blender.inspect_scene_health,
    "inspect_scene_settings": blender.inspect_scene_settings,
    "inspect_object_relationship": blender.inspect_object_relationship,
    "inspect_soccer_components": blender.inspect_soccer_components,
    "inspect_object_transform": blender_transform.inspect_object_transform,
    "create_collection": blender.create_collection,
    "create_empty_marker": blender.create_empty_marker,
    "move_object": blender.move_object,
    "parent_object": blender.parent_object,
    "move_object_to_collection": blender.move_object_to_collection,
    "rename_object": blender.rename_object,
    "delete_object": blender.delete_object,
    "set_object_rotation": blender_transform.set_object_rotation,
}


class BlenderToolExecutor:
    """Dispatch only canonical, already-authorized Blender tool calls."""

    def __init__(self, handlers: Mapping[str, BlenderToolHandler] = BLENDER_TOOL_HANDLERS):
        self._handlers = dict(handlers)

    def tool_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))

    def execute(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(tool, str) or not tool.strip():
            raise BlenderToolExecutorError("tool must be a non-empty string")
        if not isinstance(arguments, dict):
            raise BlenderToolExecutorError("arguments must be an object")

        handler = self._handlers.get(tool)
        if handler is None:
            raise BlenderToolExecutorError(
                f"Blender tool is not executable through the approved adapter: {tool}"
            )

        try:
            result = handler(**dict(arguments))
        except TypeError as exc:
            raise BlenderToolExecutorError(
                f"invalid invocation for Blender tool '{tool}': {exc}"
            ) from exc

        if not isinstance(result, dict):
            raise BlenderToolExecutorError(
                f"Blender tool '{tool}' returned a non-object result"
            )
        return result
