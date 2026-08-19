from planning.object_delete_task import object_delete_task_definition
from planning.object_rename_task import object_rename_task_definition
from planning.object_rotation_task import object_rotation_task_definition


def test_blender_task_definitions_share_canonical_action_metadata():
    tasks = (
        object_delete_task_definition("delete.blend"),
        object_rename_task_definition("rename.blend"),
        object_rotation_task_definition("rotation.blend"),
    )

    for task in tasks:
        assert task.allow_writes is True
        assert task.verify_after_action is True
        assert len(task.evidence) == 1
        assert task.evidence[0].name == task.evidence[0].tool
        assert len(task.actions) == 1
        assert task.actions[0].name == task.actions[0].tool
        assert task.allowed_action_tools == {task.actions[0].tool}
        assert task.metadata["domain"] == "blender"


def test_blender_task_snapshots_preserve_action_and_evidence_names():
    tasks = (
        object_delete_task_definition("delete.blend"),
        object_rename_task_definition("rename.blend"),
        object_rotation_task_definition("rotation.blend"),
    )

    for task in tasks:
        snapshot = task.snapshot()
        assert snapshot["evidence"][0]["tool"] == snapshot["evidence"][0]["name"]
        assert snapshot["actions"][0]["tool"] == snapshot["actions"][0]["name"]
        assert snapshot["allowed_action_tools"] == [snapshot["actions"][0]["tool"]]
