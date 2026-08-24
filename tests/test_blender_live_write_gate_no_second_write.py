from planning.action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_write_authorization import BlenderWriteAuthorization


class _CountingExecutor:
    def __init__(self):
        self.calls = 0

    def __call__(self, tool, arguments):
        self.calls += 1
        return {"status": "ok", "details": {"write": True}}


def test_authoritative_mismatch_does_not_trigger_second_write():
    action = ActionSpec(
        tool="move_object",
        arguments={
            "file_name": "scene.blend",
            "object_name": "Cube",
            "location": [1, 2, 3],
        },
    )
    authorization = BlenderWriteAuthorization.issue(action, "no-second-write")
    executor = _CountingExecutor()
    boundary = BlenderExecutionBoundary(executor)

    gate = BlenderLiveWriteGate(
        boundary,
        verifier=lambda _action, _receipt: (
            False,
            {"authoritative": {"status": "ok", "location": [9, 9, 9]}},
        ),
    )

    outcome = gate.execute(action, authorization)

    assert outcome.status == "BLOCKED"
    assert outcome.receipt is None
    assert executor.calls == 1
