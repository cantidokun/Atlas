"""Guard the public Blender tool registry against incomplete module exports."""


def test_public_blender_tool_registry_imports_all_declared_capabilities():
    from tools import TOOLS

    expected = {
        "inspect_scene",
        "inspect_mesh",
        "inspect_scene_health",
        "inspect_scene_settings",
        "inspect_object_relationship",
        "inspect_soccer_components",
        "create_collection",
        "create_empty_marker",
        "move_object",
        "inspect_object_parent",
        "parent_object",
        "inspect_object_collections",
        "move_object_to_collection",
        "rename_object",
        "delete_object",
        "inspect_object_transform",
        "set_object_rotation",
    }

    assert set(TOOLS) == expected
    assert all(callable(tool) for tool in TOOLS.values())
