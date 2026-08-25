from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_write_authorization import BlenderWriteAuthorization


def _result(_tool, _arguments):
    return {
        "ok": True,
        "state": "ok",
        "details": {},
    }


def test_blocked_outcome_does_not_expose_receipt():
    action = ActionSpec(tool="move_object", arguments={"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2, 3]})
    authorization = BlenderWriteAuthorization.issue(action, "receipt-sanitization")
    boundary = BlenderExecutionBoundary(_result)
    gate = BlenderLiveWriteGate(boundary, verifier=lambda _action, _receipt: (False, {"verified": False}))

    outcome = gate.execute(action, authorization)

    assert outcome.status == "BLOCKED"
    assert outcome.receipt is None


def test_verified_outcome_requires_the_authorization_bound_receipt():
    action = ActionSpec(tool="move_object", arguments={"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2, 3]})
    authorization = BlenderWriteAuthorization.issue(action, "receipt-sanitization-verified")
    boundary = BlenderExecutionBoundary(_result)
    gate = BlenderLiveWriteGate(boundary, verifier=lambda _action, _receipt: (True, {"verified": True}))

    outcome = gate.execute(action, authorization)

    assert outcome.status == "VERIFIED"
    assert isinstance(outcome.receipt, BlenderExecutionReceipt)
    assert outcome.receipt.matches_authorization(authorization.authorization_id)
