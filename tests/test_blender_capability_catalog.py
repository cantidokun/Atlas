import pytest

from planning.blender_capability_catalog import (
    BLENDER_CAPABILITIES,
    get_blender_capability,
    is_blender_write,
)
from planning.blender_tool_schema import BLENDER_TOOL_SCHEMAS


WRITE_TOOLS = {
    "create_collection",
    "create_empty_marker",
    "move_object",
    "parent_object",
    "move_object_to_collection",
    "rename_object",
    "delete_object",
    "set_object_rotation",
}


def test_every_registered_blender_tool_has_explicit_capability_metadata():
    assert set(BLENDER_CAPABILITIES) == set(BLENDER_TOOL_SCHEMAS)
    assert all(capability.name == name for name, capability in BLENDER_CAPABILITIES.items())


def test_write_capabilities_require_verification():
    for name, capability in BLENDER_CAPABILITIES.items():
        assert capability.writes_scene == (name in WRITE_TOOLS)
        assert capability.requires_verification == capability.writes_scene


def test_read_only_capabilities_are_not_write_capabilities():
    assert all(not is_blender_write(name) for name in BLENDER_CAPABILITIES if name not in WRITE_TOOLS)


def test_unknown_capability_fails_closed():
    with pytest.raises(ValueError, match="unsupported Blender capability"):
        get_blender_capability("arbitrary_python")
