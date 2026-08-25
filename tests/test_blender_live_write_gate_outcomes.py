from action_plan import ActionSpec
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_live_write_result import BlenderLiveWriteOutcome
from planning.blender_write_authorization import BlenderWriteAuthorization


class FakeResult:
    ok = True
    state = "ok"
    details = {}


def _action():
    return ActionSpec(
        tool="move_object",
        arguments={"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2, 3]},
    )


def _boundary(receipt_factory):
    return type(
        "Boundary",
        (),
        {
            "execute_authorized_write": lambda self, action, authorization: (
                FakeResult(),
                receipt_factory(action, authorization),
            )
        },
    )()


def _receipt(action, authorization):
    return BlenderExecutionReceipt.create_authorized(
        action.tool,
        action.arguments,
        FakeResult(),
        authorization.authorization_id,
    )


def test_gate_returns_verified_only_after_authoritative_verification():
    action = _action()
    auth = BlenderWriteAuthorization.issue(action, "live-1")
    gate = BlenderLiveWriteGate(
        _boundary(_receipt),
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
        _boundary(_receipt),
        verifier=lambda action, receipt: (False, {"authoritative": {"ok": True}}),
    )

    outcome = gate.execute(action, auth)
    assert outcome.status == "BLOCKED"
    assert outcome.receipt is None
    assert not outcome.is_verified


def test_gate_blocks_when_receipt_is_unbound():
    action = _action()
    auth = BlenderWriteAuthorization.issue(action, "live-3")

    def unbound_receipt(action, _authorization):
        return BlenderExecutionReceipt.create(action.tool, action.arguments, FakeResult())

    gate = BlenderLiveWriteGate(
        _boundary(unbound_receipt),
        verifier=lambda action, receipt: (True, {"authoritative": {"ok": True}}),
    )

    outcome = gate.execute(action, auth)
    assert outcome.status == "BLOCKED"
    assert outcome.receipt is None
