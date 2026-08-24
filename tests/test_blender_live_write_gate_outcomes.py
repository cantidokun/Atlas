from action_plan import ActionSpec
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_live_write_result import BlenderLiveWriteOutcome
from planning.blender_write_authorization import BlenderWriteAuthorization


class FakeReceipt:
    def __init__(self, authorized=True):
        self.authorized = authorized

    def matches_authorization(self, authorization_id):
        return self.authorized


class FakeResult:
    ok = True
    state = "ok"
    details = {}


def _action():
    return ActionSpec(
        tool="move_object",
        arguments={"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2, 3]},
    )


def _boundary(receipt):
    return type(
        "Boundary",
        (),
        {"execute_authorized_write": lambda self, a, z: (FakeResult(), receipt)},
    )()


def test_gate_returns_verified_only_after_authoritative_verification():
    action = _action()
    auth = BlenderWriteAuthorization.issue(action, "live-1")
    gate = BlenderLiveWriteGate(
        _boundary(FakeReceipt(True)),
        verifier=lambda action, receipt: (True, {"authoritative": {"ok": True}}),
    )

    outcome = gate.execute(action, auth)
    assert isinstance(outcome, BlenderLiveWriteOutcome)
    assert outcome.status == "VERIFIED"
    assert outcome.receipt is not None


def test_gate_blocks_when_authoritative_verification_disagrees():
    action = _action()
    auth = BlenderWriteAuthorization.issue(action, "live-2")
    gate = BlenderLiveWriteGate(
        _boundary(FakeReceipt(True)),
        verifier=lambda action, receipt: (False, {"authoritative": {"ok": True}}),
    )

    outcome = gate.execute(action, auth)
    assert outcome.status == "BLOCKED"
    assert outcome.receipt is None
    assert not outcome.is_verified


def test_gate_blocks_when_receipt_is_unbound():
    action = _action()
    auth = BlenderWriteAuthorization.issue(action, "live-3")
    gate = BlenderLiveWriteGate(
        _boundary(FakeReceipt(False)),
        verifier=lambda action, receipt: (True, {"authoritative": {"ok": True}}),
    )

    outcome = gate.execute(action, auth)
    assert outcome.status == "BLOCKED"
    assert outcome.receipt is None
