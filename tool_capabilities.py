"""Static capability classification for Atlas execution tools.

This registry is trusted Python metadata. A model proposal must not be able to
relabel a state-changing tool as read-only by changing its own plan metadata.
"""

READ_ONLY_TOOLS = frozenset(
    {
        "inspect_scene",
        "inspect_mesh",
        "inspect_scene_health",
        "inspect_scene_settings",
        "inspect_object_relationship",
        "inspect_soccer_components",
    }
)

WRITE_TOOLS = frozenset(
    {
        "create_collection",
        "create_empty_marker",
        "move_object",
    }
)

ALL_TOOLS = READ_ONLY_TOOLS | WRITE_TOOLS


def requires_write(tool: str) -> bool:
    """Return whether the trusted registry classifies a tool as a write."""
    if tool not in ALL_TOOLS:
        raise KeyError(f"Unknown Atlas tool: {tool}")
    return tool in WRITE_TOOLS
