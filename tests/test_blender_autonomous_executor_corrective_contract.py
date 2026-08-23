import pytest

from planning.blender_autonomous_executor import BlenderAutonomousExecutor


class FakeBoundary:
    def __init__(self):
        self.calls = []

    def execute_with_receipt(self, tool, arguments):
        self.calls.append((tool, arguments))
        return type("Result", (), {"ok": True, "state": "ok", "details": {"tool": tool}})(), type("Receipt", (), {"matches": lambda self, t, a, r: (t, a) == ("move_object", {"object_name": "Goal_Left_post", "location": [1, 0, 0]})})()


def test_executor_retains_result_and_receipt_for_corrective_runtime():
    boundary = FakeBoundary()
    executor = BlenderAutonomousExecutor(executor=lambda tool, args: {"status": "ok"})
    executor._boundary = boundary

    result = executor("move_object", {"object_name": "Goal_Left_post", "location": [1, 0, 0]})

    assert result["ok"] is True
    assert executor.last_result is not None
    assert executor.last_receipt is not None
    assert executor.receipt_matches_last_execution("move_object", {"object_name": "Goal_Left_post", "location": [1, 0, 0]})
