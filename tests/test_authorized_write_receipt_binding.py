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


def test_authorized_write_receipt_binds_authorization():
    action = _action([1, 2, 3])
    authorization = BlenderWriteAuthorization.issue(action, "write-receipt-1")

    result, receipt = BlenderExecutionBoundary(lambda tool, arguments: _success()).execute_authorized_write(
        action, authorization
    )

    assert result.ok is True
    assert receipt.matches(action.tool, action.arguments, result)
    assert receipt.matches_authorization("write-receipt-1")
    assert not receipt.matches_authorization("different-authorization")


def test_unauthorized_or_changed_action_never_gets_receipt():
    calls = []

    def executor(tool, arguments):
        calls.append((tool, arguments))
        return _success()

    action = _action([1, 2, 3])
    changed = _action([9, 9, 9])
    authorization = BlenderWriteAuthorization.issue(action, "write-receipt-2")

    with pytest.raises(RuntimeError, match="stale or invalid"):
        BlenderExecutionBoundary(executor).execute_authorized_write(changed, authorization)

    assert calls == []
