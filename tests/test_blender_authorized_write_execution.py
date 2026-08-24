import pytest

from planning.action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_write_authorization import BlenderWriteAuthorization


def _action(location):
    return ActionSpec(
        tool="move_object",
        arguments={"file_name": "scene.blend", "object_name": "Cube", "location": list(location)},
    )


def _success():
    return {"ok": True, "state": {"object_name": "Cube", "location": [1.0, 2.0, 3.0]}, "details": {}}


def test_authorized_write_executes_and_returns_receipt():
    calls = []

    def executor(tool, arguments):
        calls.append((tool, dict(arguments)))
        return _success()

    action = _action([1, 2, 3])
    authorization = BlenderWriteAuthorization.issue(action, "write-1")
    result, receipt = BlenderExecutionBoundary(executor).execute_authorized_write(action, authorization)

    assert result.ok is True
    assert receipt.tool == "move_object"
    assert calls == [("move_object", action.arguments)]


def test_changed_action_is_rejected_before_executor():
    calls = []

    def executor(tool, arguments):
        calls.append((tool, arguments))
        return _success()

    action = _action([1, 2, 3])
    changed = _action([4, 5, 6])
    authorization = BlenderWriteAuthorization.issue(action, "write-2")

    with pytest.raises(RuntimeError, match="stale or invalid"):
        BlenderExecutionBoundary(executor).execute_authorized_write(changed, authorization)

    assert calls == []


def test_read_capability_cannot_receive_write_authorization():
    action = ActionSpec(tool="inspect_scene", arguments={"file_name": "scene.blend"})
    with pytest.raises(ValueError, match="scene-writing capability"):
        BlenderWriteAuthorization.issue(action, "write-3")
