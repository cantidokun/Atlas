import pytest

from planning.object_rename_task import (
    object_rename_target_evaluator,
    object_rename_task_definition,
    rename_object_action,
)
from planning.tool_schema import validate_tool_arguments
from task_planner import TaskPlanValidationError


def test_rename_tool_accepts_exact_arguments():
    validate_tool_arguments(
        "rename_object",
        {"file_name": "fixture.blend", "object_name": "Goal_Left_post", "new_name": "Goal_Left_Post"},
    )


def test_rename_tool_rejects_unknown_arguments():
    with pytest.raises(TaskPlanValidationError, match="Unknown argument"):
        validate_tool_arguments(
            "rename_object",
            {
                "file_name": "fixture.blend",
                "object_name": "Goal_Left_post",
                "new_name": "Goal_Left_Post",
                "location": [0, 0, 0],
            },
        )


def test_rename_tool_requires_all_fields():
    with pytest.raises(TaskPlanValidationError, match="Missing argument"):
        validate_tool_arguments(
            "rename_object",
            {"file_name": "fixture.blend", "object_name": "Goal_Left_post"},
        )


def test_rename_target_evaluator_distinguishes_correct_and_incorrect_states():
    evaluator = object_rename_target_evaluator()
    correct = evaluator.evaluate({"object_names": ["Goal_Left_Post"]})
    incorrect = evaluator.evaluate({"object_names": ["Goal_Left_post"]})
    assert correct.satisfied
    assert not incorrect.satisfied


def test_rename_action_is_exactly_bound_to_target():
    action = rename_object_action("fixture.blend")
    assert action.tool == "rename_object"
    assert action.arguments == {
        "file_name": "fixture.blend",
        "object_name": "Goal_Left_post",
        "new_name": "Goal_Left_Post",
    }
    assert action.name == "rename_object"


def test_rename_task_definition_is_write_verified_and_task_specific():
    task = object_rename_task_definition("fixture.blend")
    assert task.name == "object_rename"
    assert task.allow_writes is True
    assert task.verify_after_action is True
    assert task.allowed_action_tools == {"rename_object"}
    assert task.evidence[0].tool == "inspect_scene"
    assert task.evidence[0].arguments == {"file_name": "fixture.blend"}
    assert task.actions == (rename_object_action("fixture.blend"),)
    assert task.metadata["operation"] == "rename"
