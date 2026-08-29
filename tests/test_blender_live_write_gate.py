import pytest

from action_plan import ActionSpec
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_result_contract import BlenderExecutionResult
from planning.blender_write_authorization import BlenderWriteAuthorization


class FakeBoundary:
    def __init__(self, receipt):
        self.receipt = receipt
        self.calls = 0

    def execute_authorized_write(self, action, authorization):
        self.calls += 1
        return self.receipt


def _action(location=(1, 2, 3)):
    return ActionSpec(
        tool="move_object",
        arguments={"file_name": "scene.blend", "object_name": "Cube", "location": list(location)},
    )


def _successful_execution(action, authorization, mutation_performed=True):
    result = BlenderExecutionResult(
        tool=action.tool,
        ok=True,
        state="moved",
        details={"mutation_performed": mutation_performed},
    )
    receipt = BlenderExecutionReceipt.create_authorized(
        action.tool,
        action.arguments,
        result,
        authorization.authorization_id,
    )
    return result, receipt


def test_live_gate_requires_exact_authorization_before_boundary_call():
    action = _action()
    changed = _action((4, 5, 6))
    authorization = BlenderWriteAuthorization.issue(action, "live-auth")
    boundary = FakeBoundary(receipt=None)
    gate = BlenderLiveWriteGate(boundary)

    with pytest.raises(ValueError, match="does not match action"):
        gate.execute(changed, authorization)
    assert boundary.calls == 0


def test_live_gate_blocks_explicit_noop_mutation_before_authoritative_verification():
    action = _action()
    authorization = BlenderWriteAuthorization.issue(action, "live-auth")
    result, receipt = _successful_execution(action, authorization, mutation_performed=False)
    boundary = FakeBoundary((result, receipt))
    verifier_calls = []

    def verifier(_action, _receipt):
        verifier_calls.append(True)
        return True, {"authoritative": True}

    gate = BlenderLiveWriteGate(boundary, verifier)
    outcome = gate.execute(action, authorization)

    assert outcome.status == "BLOCKED"
    assert outcome.receipt is None
    assert "no mutation was performed" in outcome.reason
    assert outcome.verification["mutation_performed"] is False
    assert verifier_calls == []


def test_live_gate_requires_authoritative_verification_for_success():
    action = _action()
    authorization = BlenderWriteAuthorization.issue(action, "live-auth")
    result, receipt = _successful_execution(action, authorization)
    boundary = FakeBoundary((result, receipt))
    verifier_calls = []

    def verifier(received_action, received_receipt):
        verifier_calls.append((received_action, received_receipt))
        return True, {"authoritative": True, "observed_location": [1, 2, 3]}

    gate = BlenderLiveWriteGate(boundary, verifier)
    outcome = gate.execute(action, authorization)

    assert outcome.status == "VERIFIED"
    assert outcome.receipt == receipt
    assert verifier_calls == [(action, receipt)]
    assert outcome.verification["authoritative"] is True


def test_live_gate_blocks_when_authoritative_verification_rejects_mutation():
    action = _action()
    authorization = BlenderWriteAuthorization.issue(action, "live-auth")
    result, receipt = _successful_execution(action, authorization)
    boundary = FakeBoundary((result, receipt))
    verifier_calls = []

    def verifier(received_action, received_receipt):
        verifier_calls.append((received_action, received_receipt))
        return False, {"authoritative": False, "observed_location": [9, 9, 9]}

    gate = BlenderLiveWriteGate(boundary, verifier)
    outcome = gate.execute(action, authorization)

    assert outcome.status == "BLOCKED"
    assert outcome.receipt is None
    assert "did not verify" in outcome.reason
    assert verifier_calls == [(action, receipt)]
    assert outcome.verification["authoritative"] is False
