import pytest

from planning.tool_schema import validate_tool_arguments
from task_planner import TaskPlanValidationError


def test_collection_membership_tools_accept_exact_arguments():
    validate_tool_arguments(
        "inspect_object_collections",
        {"file_name": "fixture.blend", "object_name": "Atlas_Marker"},
    )
    validate_tool_arguments(
        "move_object_to_collection",
        {
            "file_name": "fixture.blend",
            "object_name": "Atlas_Marker",
            "collection_name": "Atlas_Test",
        },
    )


def test_collection_membership_tools_reject_unknown_arguments():
    with pytest.raises(TaskPlanValidationError, match="Unknown argument"):
        validate_tool_arguments(
            "move_object_to_collection",
            {
                "file_name": "fixture.blend",
                "object_name": "Atlas_Marker",
                "collection_name": "Atlas_Test",
                "location": [0, 0, 0],
            },
        )


def test_collection_membership_tools_require_exact_fields():
    with pytest.raises(TaskPlanValidationError, match="Missing argument"):
        validate_tool_arguments(
            "inspect_object_collections",
            {"file_name": "fixture.blend"},
        )
