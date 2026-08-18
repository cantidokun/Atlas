import pytest

from action_plan import ActionSpec
from planning.blender_tool_schema import validate_blender_tool_call
from planning.object_rotation_task import (
    TARGET_OBJECT,
    TARGET_ROTATION,
    object_rotation_action,
    object_rotation_target_evaluator,
)
from planning.tool_schema import validate_tool_arguments


def test_rotation_target_requires_exact_rotation():
    evaluator = object_rotation_target_evaluator()
    assert not evaluator.evaluate({"object_name": TARGET_OBJECT, "rotation_degrees": [0, 0, 0]}).satisfied
    assert evaluator.evaluate({"object_name": TARGET_OBJECT, "rotation_degrees": TARGET_ROTATION}).satisfied


def test_rotation_action_shape_is_exact():
    action = object_rotation_action("rotation.blend")
    assert isinstance(action, ActionSpec)
    assert action.tool == "set_object_rotation"
    assert action.arguments == {
        "file_name": "rotation.blend",
        "object_name": TARGET_OBJECT,
        "rotation_degrees": TARGET_ROTATION,
    }


def test_rotation_boundary_rejects_wrong_vector_shape():
    with pytest.raises(ValueError, match="exactly three numeric values"):
        validate_blender_tool_call(
            "set_object_rotation",
            {"file_name": "rotation.blend", "object_name": TARGET_OBJECT, "rotation_degrees": [90, 0]},
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
