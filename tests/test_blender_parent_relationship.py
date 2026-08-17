import pytest

from planning.blender_tool_schema import validate_blender_tool_call
from planning.parent_marker_task import parent_marker_action, parent_target_satisfied
from tools.blender_relationship import ALLOWED_CHILD, ALLOWED_PARENT


def test_parent_object_schema_accepts_exact_relationship():
    args = validate_blender_tool_call(
        "parent_object",
        {"file_name": "parent_task_INCORRECT.blend", "child_name": ALLOWED_CHILD, "parent_name": ALLOWED_PARENT},
    )
    assert args["child_name"] == ALLOWED_CHILD
    assert args["parent_name"] == ALLOWED_PARENT


def test_parent_object_schema_rejects_missing_parent():
    with pytest.raises(ValueError):
        validate_blender_tool_call(
            "parent_object",
            {"file_name": "parent_task_INCORRECT.blend", "child_name": ALLOWED_CHILD},
        )


def test_parent_object_schema_rejects_empty_names():
    with pytest.raises(ValueError):
        validate_blender_tool_call(
            "parent_object",
            {"file_name": "parent_task_INCORRECT.blend", "child_name": "", "parent_name": ALLOWED_PARENT},
        )


def test_parent_task_action_has_single_relationship_write():
    action = parent_marker_action("parent_task_INCORRECT.blend")
    assert action.tool == "parent_object"
    assert action.arguments == {
        "file_name": "parent_task_INCORRECT.blend",
        "child_name": ALLOWED_CHILD,
        "parent_name": ALLOWED_PARENT,
    }


def test_parent_target_requires_both_object_and_parent():
    assert not parent_target_satisfied({"object_name": ALLOWED_CHILD, "parent_name": None})
    assert parent_target_satisfied({"object_name": ALLOWED_CHILD, "parent_name": ALLOWED_PARENT})
