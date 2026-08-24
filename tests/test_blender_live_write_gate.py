import pytest

from action_plan import ActionSpec
from planning.blender_live_write_gate import BlenderLiveWriteGate
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
