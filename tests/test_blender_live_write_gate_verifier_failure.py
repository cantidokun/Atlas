from planning.action_plan import ActionSpec
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_write_authorization import BlenderWriteAuthorization


class _Receipt:
    authorization_id = "auth"

    def matches_authorization(self, authorization_id):
        return True


class _Boundary:
    def __init__(self):
        self.calls = 0

    def execute_authorized_write(self, action, authorization):
        self.calls += 1
        return {"ok": True}, _Receipt()


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
    assert outcome.details["verification_error"] == "RuntimeError"
    assert boundary.calls == 1
