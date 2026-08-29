import pytest

from controller.controller_runtime import ControllerRuntime


RELATIONSHIP = {
    "object_a": {"name": "Goal_Left_post", "location": [-1.0, 0.0, 0.0]},
    "object_b": {"name": "Goal_Right_Post", "location": [1.0, 0.0, 0.0]},
    "midpoint": [0.0, 0.0, 0.0],
}


def _runtime_ready_for_write():
    runtime = ControllerRuntime("scene.blend")
    runtime.step(lambda *_: {"status": "ok", **RELATIONSHIP})
    return runtime


def test_explicit_false_ok_blocks_before_state_mutation():
    runtime = ControllerRuntime("scene.blend")

    result = runtime.step(lambda *_: {"ok": False, "state": "failed", "details": {"reason": "fixture"}})

    assert result["status"] == "error"
    assert result["error"]["type"] == "ToolExecutionError"
    assert runtime.state.before is None
    assert runtime.state.writes == []


def test_canonical_success_result_is_accepted_for_midpoint_write():
    runtime = _runtime_ready_for_write()

    result = runtime.step(
        lambda *_: {
            "ok": True,
            "state": "moved",
            "details": {"object_name": "Goal_Left_post", "location": [-1.0, 0.0, 0.0]},
        }
    )

    assert result["status"] == "progress"
    assert runtime.state.writes
    assert runtime.state.writes[-1]["object_name"] == "Goal_Left_post"


def test_malformed_result_fails_closed():
    runtime = ControllerRuntime("scene.blend")

    result = runtime.step(lambda *_: {"ok": True})

    assert result["status"] == "error"
    assert result["error"]["type"] == "ValueError"
    assert runtime.state.before is None
