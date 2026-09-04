import pytest

from action_plan import ActionSpec
from planning.blender_tool_schema import validate_blender_tool_call
from planning.object_rotation_task import (
    TARGET_OBJECT,
    TARGET_ROTATION,
    object_rotation_action,
    object_rotation_target_evaluator,
    object_rotation_task_definition,
)
from planning.tool_schema import validate_tool_arguments


def test_rotation_target_requires_exact_rotation():
    evaluator = object_rotation_target_evaluator()
    assert not evaluator.evaluate({"object_name": TARGET_OBJECT, "rotation_degrees": [0, 0, 0]}).satisfied
    assert evaluator.evaluate({"object_name": TARGET_OBJECT, "rotation_degrees": TARGET_ROTATION}).satisfied


def test_rotation_target_accepts_canonical_blender_result_shape():
    evaluator = object_rotation_target_evaluator("Goal_Left_post", [0.0, 0.0, 15.0])
    assert evaluator.evaluate({
        "ok": True,
        "state": "transform_inspected",
        "details": {
            "object_name": "Goal_Left_post",
            "rotation_degrees": [0.0, 0.0, 15.0],
        },
    }).satisfied


def test_rotation_action_shape_is_exact():
    action = object_rotation_action("rotation.blend")
    assert isinstance(action, ActionSpec)
    assert action.tool == "set_object_rotation"
    assert action.arguments == {
        "file_name": "rotation.blend",
        "object_name": TARGET_OBJECT,
        "rotation_degrees": TARGET_ROTATION,
    }
    assert action.name == "set_object_rotation"


def test_rotation_boundary_rejects_wrong_vector_shape():
    with pytest.raises(ValueError, match="exactly three numeric values"):
        validate_blender_tool_call(
            "set_object_rotation",
            {"file_name": "rotation.blend", "object_name": TARGET_OBJECT, "rotation_degrees": [90, 0]},
        )


def test_rotation_boundary_rejects_non_finite_values():
    with pytest.raises(ValueError, match="only finite numeric values"):
        validate_blender_tool_call(
            "set_object_rotation",
            {"file_name": "rotation.blend", "object_name": TARGET_OBJECT, "rotation_degrees": [0, float("nan"), 90]},
        )


def test_rotation_qwen_schema_rejects_unknown_arguments():
    with pytest.raises(Exception, match="Unknown argument"):
        validate_tool_arguments(
            "set_object_rotation",
            {
                "file_name": "rotation.blend",
                "object_name": TARGET_OBJECT,
                "rotation_degrees": TARGET_ROTATION,
                "force": True,
            },
        )


def test_rotation_task_definition_is_write_verified_and_task_specific():
    task = object_rotation_task_definition("rotation.blend")
    assert task.name == "object_rotation"
    assert task.allow_writes is True
    assert task.verify_after_action is True
    assert task.allowed_action_tools == {"set_object_rotation"}
    assert task.evidence[0].tool == "inspect_object_transform"
    assert task.evidence[0].arguments == {
        "file_name": "rotation.blend",
        "object_name": TARGET_OBJECT,
    }
    assert task.actions == (object_rotation_action("rotation.blend"),)
    assert task.metadata["operation"] == "rotation"
