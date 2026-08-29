import pytest

from planning.object_delete_task import TARGET_OBJECT, object_delete_task_definition


def test_delete_object_task_definition_is_write_capable():
    definition = object_delete_task_definition("cleanup.blend")
    assert definition.allow_writes is True
    assert definition.verify_after_action is True
    assert definition.allowed_action_tools == ("delete_object",)
    assert definition.actions[0].tool == "delete_object"


def test_delete_object_planning_schema_rejects_unknown_arguments():
    from planning.tool_schema import validate_tool_arguments

    with pytest.raises(ValueError, match=r"Unknown argument\(s\) for delete_object: force"):
        validate_tool_arguments(
            "delete_object",
            {"file_name": "cleanup.blend", "object_name": TARGET_OBJECT, "force": True},
        )
