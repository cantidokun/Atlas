from action_plan import ActionSpec
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_write_authorization import BlenderWriteAuthorization


class FakeReceipt:
    def matches_authorization(self, authorization_id):
        return True


class FailedResult:
    ok = False
    state = "error"
    details = {"error": "write failed"}


def _action():
    return ActionSpec(
        tool="move_object",
        arguments={"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2, 3]},
    )


def test_executor_failure_blocks_without_authoritative_verification():
    action = _action()
    authorization = BlenderWriteAuthorization.issue(action, "live-executor-failure")
    calls = []

    class Boundary:
        def execute_authorized_write(self, action, authorization):
            return FailedResult(), FakeReceipt()

    def verifier(action, receipt):
        calls.append((action, receipt))
        return True, {"authoritative": {"ok": True}}

    outcome = BlenderLiveWriteGate(Boundary(), verifier=verifier).execute(action, authorization)

    assert outcome.status == "BLOCKED"
    assert outcome.receipt is None
    assert calls == []
    assert "successful write" in outcome.reason
