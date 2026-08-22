import pytest

from planning.blender_tool_schema import validate_blender_tool_call


def test_inspect_mesh_requires_file_and_object():
    with pytest.raises(ValueError, match="missing required argument: object_name"):
        validate_blender_tool_call("inspect_mesh", {"file_name": "scene.blend"})


def test_inspect_relationship_uses_actual_tool_argument_names():
    snapshot = validate_blender_tool_call(
        "inspect_object_relationship",
        {
            "file_name": "scene.blend",
            "object1_name": "Goal_Left_post",
            "object2_name": "Goal_Right_post",
        },
    )
    assert snapshot["object1_name"] == "Goal_Left_post"
    assert snapshot["object2_name"] == "Goal_Right_post"


def test_move_object_requires_finite_three_axis_location():
    with pytest.raises(ValueError, match="exactly three"):
        validate_blender_tool_call(
            "move_object",
            {"file_name": "scene.blend", "object_name": "Atlas_Marker", "location": [1, 2]},
        )

    with pytest.raises(ValueError, match="finite"):
        validate_blender_tool_call(
            "move_object",
            {"file_name": "scene.blend", "object_name": "Atlas_Marker", "location": [1, float("inf"), 3]},
        )
