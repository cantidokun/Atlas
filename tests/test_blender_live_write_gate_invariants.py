from planning.action_plan import ActionSpec
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_live_write_result import BlenderLiveWriteOutcome
from planning.blender_write_authorization import BlenderWriteAuthorization


class _Boundary:
    def __init__(self, result, receipt):
        self.result = result
        self.receipt = receipt
        self.calls = 0

    def execute_authorized_write(self, action, authorization):
        self.calls += 1
        return self.result, self.receipt


def _action():
    return ActionSpec(
        tool="move_object",
        arguments={"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2, 3]},
    )


def test_live_gate_rejects_non_receipt_before_reporting_verified():
    action = _action()
    auth = BlenderWriteAuthorization.issue(action, "auth-invariant")
    boundary = _Boundary({"ok": True}, object())
    gate = BlenderLiveWriteGate(boundary)

    try:
        gate.execute(action, auth)
    except AttributeError:
        pass
    else:
        raise AssertionError("invalid receipt must not produce a verified outcome")

    assert boundary.calls == 1


def test_live_gate_never_returns_verified_without_receipt_binding():
    action = _action()
    auth = BlenderWriteAuthorization.issue(action, "auth-bound")
    outcome = BlenderLiveWriteOutcome.blocked(
        {"receipt_authorized": False},
        "receipt authorization mismatch",
    )
    assert not outcome.is_verified
    assert outcome.receipt is None
