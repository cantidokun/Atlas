import pytest

from planning.action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_write_authorization import BlenderWriteAuthorization


def _result(_tool, _arguments):
    return {"ok": True, "state": "ok", "details": {}}


def test_mismatched_authorization_fails_before_execution():
    action = ActionSpec(tool="move_object", arguments={"object_name": "Cube", "location": [1, 2, 3]})
    different_action = ActionSpec(tool="move_object", arguments={"object_name": "Cube", "location": [4, 5, 6]})
    authorization = BlenderWriteAuthorization.issue(different_action, "mismatch")
    calls = []

    def executor(tool, arguments):
        calls.append((tool, arguments))
        return _result(tool, arguments)

    gate = BlenderLiveWriteGate(BlenderExecutionBoundary(executor), verifier=lambda *_: (True, {}))

    with pytest.raises(ValueError, match="does not match action"):
        gate.execute(action, authorization)

    assert calls == []
