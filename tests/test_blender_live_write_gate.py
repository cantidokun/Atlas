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
    result = BlenderExecutionResult(
        tool=action.tool,
        ok=True,
        state="already_at_target",
        details={"mutation_performed": False},
    )
    receipt = BlenderExecutionReceipt.create_authorized(
        action.tool,
        action.arguments,
        result,
        authorization.authorization_id,
    )
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
