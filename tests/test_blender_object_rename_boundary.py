import pytest

from planning.blender_tool_schema import validate_blender_tool_call


def test_object_rename_is_admitted_at_blender_boundary():
    snapshot = validate_blender_tool_call(
        "rename_object",
        {"file_name": "fixture.blend", "object_name": "Goal_Left_post", "new_name": "Goal_Left_Post"},
    )
    assert snapshot == {
        "file_name": "fixture.blend",
        "object_name": "Goal_Left_post",
        "new_name": "Goal_Left_Post",
    }


def test_object_rename_rejects_missing_argument():
    with pytest.raises(ValueError, match="missing required argument: new_name"):
        validate_blender_tool_call(
            "rename_object",
            {"file_name": "fixture.blend", "object_name": "Goal_Left_post"},
        )


def test_object_rename_rejects_empty_names():
    with pytest.raises(ValueError, match="argument new_name must not be empty"):
        validate_blender_tool_call(
            "rename_object",
            {"file_name": "fixture.blend", "object_name": "Goal_Left_post", "new_name": ""},
        )
