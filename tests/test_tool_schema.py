import pytest

from planning.tool_schema import validate_tool_arguments
from task_planner import TaskPlanValidationError


def test_create_collection_schema_accepts_generic_arguments():
    validate_tool_arguments(
        "create_collection",
        {"file_name": "fixture.blend", "collection_name": "Atlas_Test"},
    )


def test_move_object_schema_is_not_goalpost_specific():
    validate_tool_arguments(
        "move_object",
        {"file_name": "fixture.blend", "object_name": "Camera", "location": [1.0, 2.0, 3.0]},
    )


def test_unknown_arguments_are_rejected():
    with pytest.raises(TaskPlanValidationError):
        validate_tool_arguments(
            "create_collection",
            {"file_name": "fixture.blend", "collection_name": "Atlas_Test", "extra": True},
        )


def test_missing_arguments_are_rejected():
    with pytest.raises(TaskPlanValidationError):
        validate_tool_arguments("create_collection", {"file_name": "fixture.blend"})
