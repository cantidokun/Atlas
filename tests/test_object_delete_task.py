import pytest

from action_plan import ActionSpec
from planning.object_delete_task import (
    TARGET_OBJECT,
    object_delete_action,
    object_delete_target_evaluator,
    object_delete_task_definition,
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
    assert action.name == "delete_object"


def test_delete_action_has_no_implicit_force_or_collection_arguments():
    action = object_delete_action("cleanup.blend")
    assert "force" not in action.arguments
    assert "collection_name" not in action.arguments


def test_delete_boundary_requires_object_name():
    from planning.blender_tool_schema import validate_blender_tool_call

    with pytest.raises(ValueError, match="missing required argument: object_name"):
        validate_blender_tool_call("delete_object", {"file_name": "cleanup.blend"})


def test_delete_adapter_uses_standard_success_status(monkeypatch):
    import tools.blender_delete as blender_delete

    captured = {}

    def fake_validate_blend_file(file_name):
        return file_name

    def fake_run_blender(blend_path, script, start_marker, end_marker):
        captured["script"] = script
        return {"status": "ok", "object_name": TARGET_OBJECT}

    monkeypatch.setattr(blender_delete, "validate_blend_file", fake_validate_blend_file)
    monkeypatch.setattr(blender_delete, "run_blender", fake_run_blender)
    result = blender_delete.delete_object("cleanup.blend", TARGET_OBJECT)

    assert result["status"] == "ok"
    assert '"status": "ok"' in captured["script"]
    assert '"status": "deleted"' not in captured["script"]


def test_delete_adapter_reports_whether_mutation_occurred(monkeypatch):
    import tools.blender_delete as blender_delete

    def fake_validate_blend_file(file_name):
        return file_name

    def fake_run_blender(blend_path, script, start_marker, end_marker):
        return {"status": "already_absent", "object_name": TARGET_OBJECT, "mutation_performed": False}

    monkeypatch.setattr(blender_delete, "validate_blend_file", fake_validate_blend_file)
    monkeypatch.setattr(blender_delete, "run_blender", fake_run_blender)
    result = blender_delete.delete_object("cleanup.blend", TARGET_OBJECT)

    assert result["status"] == "already_absent"
    assert result["mutation_performed"] is False


def test_delete_object_is_admitted_by_qwen_planning_schema():
    from planning.tool_schema import validate_tool_arguments

    validate_tool_arguments(
        "delete_object",
        {"file_name": "cleanup.blend", "object_name": TARGET_OBJECT},
    )


def test_delete_object_planning_schema_rejects_unknown_arguments():
    from planning.tool_schema import validate_tool_arguments

    with pytest.raises(ValueError, match=r"Unknown argument\(s\) for delete_object: force"):
        validate_tool_arguments(
            "delete_object",
            {"file_name": "cleanup.blend", "object_name": TARGET_OBJECT, "force": True},
        )


def test_delete_task_definition_is_write_verified_and_task_specific():
    task = object_delete_task_definition("cleanup.blend")
    assert task.name == "object_delete"
    assert task.allow_writes is True
    assert task.verify_after_action is True
    assert task.allowed_action_tools == {"delete_object"}
    assert task.evidence[0].tool == "inspect_scene"
    assert task.evidence[0].arguments == {"file_name": "cleanup.blend"}
    assert task.actions == (object_delete_action("cleanup.blend"),)
    assert task.metadata["operation"] == "delete"
