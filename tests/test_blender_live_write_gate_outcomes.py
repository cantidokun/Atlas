from action_plan import ActionSpec
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_live_write_result import BlenderLiveWriteOutcome
from planning.blender_write_authorization import BlenderWriteAuthorization


class FakeReceipt:
    def __init__(self, authorized=True):
        self.authorized = authorized

    def matches_authorization(self, authorization_id):
        return self.authorized


def _action():
    return ActionSpec(
        tool="move_object",
        arguments={"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2, 3]},
    )


def test_gate_returns_verified_for_authorization_bound_receipt():
    action = _action()
    auth = BlenderWriteAuthorization.issue(action, "live-1")
    gate = BlenderLiveWriteGate(type("Boundary", (), {"execute_authorized_write": lambda self, a, z: FakeReceipt(True)})())

    outcome = gate.execute(action, auth)
    assert isinstance(outcome, BlenderLiveWriteOutcome)
    assert outcome.status == "VERIFIED"
    assert outcome.receipt is not None


def test_gate_returns_blocked_for_unbound_receipt():
    action = _action()
    auth = BlenderWriteAuthorization.issue(action, "live-2")
    gate = BlenderLiveWriteGate(type("Boundary", (), {"execute_authorized_write": lambda self, a, z: FakeReceipt(False)})())

    outcome = gate.execute(action, auth)
    assert outcome.status == "BLOCKED"
    assert outcome.receipt is None
    assert not outcome.is_verified
