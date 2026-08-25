from action_plan import ActionSpec
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_write_authorization import BlenderWriteAuthorization


class _Boundary:
    def __init__(self):
        self.calls = 0

    def execute_authorized_write(self, action, authorization):
        self.calls += 1
        result = type("Result", (), {"tool": action.tool, "ok": True, "state": "ok", "details": {}})()
        receipt = BlenderExecutionReceipt.create_authorized(
            action.tool,
            action.arguments,
            result,
            authorization.authorization_id,
        )
        return result, receipt


def _action():
    return ActionSpec(
        tool="move_object",
        arguments={"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2, 3]},
    )


def test_verifier_exception_fails_closed_without_retry():
    boundary = _Boundary()
    gate = BlenderLiveWriteGate(
        boundary,
        verifier=lambda action, receipt: (_ for _ in ()).throw(RuntimeError("inspection failed")),
    )
    action = _action()
    authorization = BlenderWriteAuthorization.issue(action, "auth")

    outcome = gate.execute(action, authorization)

    assert outcome.status == "BLOCKED"
    assert outcome.receipt is None
    assert not outcome.is_verified
    assert outcome.verification["verification_error"] == "RuntimeError"
    assert boundary.calls == 1
