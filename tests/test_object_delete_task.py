import pytest

from action_plan import ActionSpec
from planning.object_delete_task import (
    TARGET_OBJECT,
    object_delete_action,
    object_delete_target_evaluator,
)


def test_delete_target_is_satisfied_only_when_candidate_is_absent():
    evaluator = object_delete_target_evaluator()
    assert not evaluator.evaluate({"object_names": [TARGET_OBJECT]}).satisfied
    assert evaluator.evaluate({"object_names": []}).satisfied


def test_delete_action_shape_is_exact():
    action = object_delete_action("cleanup.blend")
    assert isinstance(action, ActionSpec)
    assert action.tool == "delete_object"
    assert action.arguments == {
        "file_name": "cleanup.blend",
        "object_name": TARGET_OBJECT,
    }


def test_delete_action_has_no_implicit_force_or_collection_arguments():
    action = object_delete_action("cleanup.blend")
    assert "force" not in action.arguments
    assert "collection_name" not in action.arguments


def test_delete_boundary_requires_object_name():
    from planning.blender_tool_schema import validate_blender_tool_call

    with pytest.raises(ValueError, match="missing required argument: object_name"):
        validate_blender_tool_call("delete_object", {"file_name": "cleanup.blend"})
