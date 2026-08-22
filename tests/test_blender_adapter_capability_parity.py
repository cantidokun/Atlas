import pytest

from controller.blender_capabilities import BLENDER_CAPABILITIES
from planning.blender_tool_schema import BLENDER_TOOL_SCHEMAS
from tools import TOOLS


def test_authorized_capabilities_have_schemas_and_concrete_tools():
    capability_names = {cap.name for cap in BLENDER_CAPABILITIES}
    assert capability_names == set(BLENDER_TOOL_SCHEMAS)
    assert capability_names == set(TOOLS)


def test_every_mutating_capability_is_declared_as_mutating():
    mutating = {cap.name for cap in BLENDER_CAPABILITIES if cap.mutates_state}
    assert mutating == {
        "create_collection", "create_empty_marker", "move_object", "parent_object",
        "move_object_to_collection", "rename_object", "delete_object", "set_object_rotation",
    }


def test_read_only_capabilities_are_not_marked_mutating():
    mutating = {cap.name for cap in BLENDER_CAPABILITIES if cap.mutates_state}
    assert all(not cap.mutates_state for cap in BLENDER_CAPABILITIES if cap.name not in mutating)


def test_capability_catalog_has_no_duplicate_names():
    names = [cap.name for cap in BLENDER_CAPABILITIES]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("tool", sorted(TOOLS))
def test_public_tool_registry_is_callable(tool):
    assert callable(TOOLS[tool])
