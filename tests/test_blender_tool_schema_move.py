import pytest

from planning.blender_tool_schema import validate_blender_tool_call


def test_move_object_requires_blend_file():
    with pytest.raises(ValueError, match="missing required argument: file_name"):
        validate_blender_tool_call(
            "move_object",
            {"object_name": "Goal_Left_post", "location": [1, 2, 3]},
        )


def test_move_object_accepts_complete_valid_call():
    result = validate_blender_tool_call(
        "move_object",
        {
            "file_name": "goalpost_test.blend",
            "object_name": "Goal_Left_post",
            "location": [1, 2, 3],
        },
    )

    assert result["file_name"] == "goalpost_test.blend"
    assert result["object_name"] == "Goal_Left_post"
    assert result["location"] == [1, 2, 3]


def test_move_object_rejects_non_finite_coordinates():
    with pytest.raises(ValueError, match="finite numeric"):
        validate_blender_tool_call(
            "move_object",
            {
                "file_name": "goalpost_test.blend",
                "object_name": "Goal_Left_post",
                "location": [1, float("inf"), 3],
            },
        )
