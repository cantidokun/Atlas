import pytest

from planning.blender_autonomous_executor import BlenderAutonomousExecutor


def test_autonomous_executor_returns_verified_result_and_receipt():
    calls = []

    def fake_blender(tool, arguments):
        calls.append((tool, arguments))
        return {
            "ok": True,
            "state": "moved",
            "details": {"object_name": arguments["object_name"]},
        }

    executor = BlenderAutonomousExecutor(fake_blender)
    result = executor("move_object", {
        "file_name": "goalpost_test.blend",
        "object_name": "Goal_Left_post",
        "location": [1.0, 2.0, 3.0],
    })

    assert result["ok"] is True
    assert result["state"] == "moved"
    assert result["details"]["object_name"] == "Goal_Left_post"
    assert executor.last_result is not None
    assert executor.last_receipt is not None
    assert executor.receipt_matches_last_execution(
        "move_object",
        {
            "file_name": "goalpost_test.blend",
            "object_name": "Goal_Left_post",
            "location": [1.0, 2.0, 3.0],
        },
    )
    assert calls == [(
        "move_object",
        {
            "file_name": "goalpost_test.blend",
            "object_name": "Goal_Left_post",
            "location": [1.0, 2.0, 3.0],
        },
    )]


def test_autonomous_executor_rejects_invalid_call_before_blender():
    calls = []
    executor = BlenderAutonomousExecutor(
        lambda tool, arguments: calls.append((tool, arguments)) or {
            "ok": True,
            "state": "moved",
            "details": {},
        }
    )

    with pytest.raises(ValueError):
        executor("move_object", {
            "file_name": "goalpost_test.blend",
            "object_name": "Goal_Left_post",
            "location": [1.0, 2.0],
        })

    assert calls == []
    assert executor.last_result is None
    assert executor.last_receipt is None


def test_autonomous_executor_rejects_unsuccessful_blender_result():
    executor = BlenderAutonomousExecutor(
        lambda tool, arguments: {
            "ok": False,
            "state": "failed",
            "details": {"reason": "fixture"},
        }
    )

    with pytest.raises(RuntimeError, match="did not succeed"):
        executor("rename_object", {
            "file_name": "object_rename_INCORRECT.blend",
            "object_name": "Goal_Left_post",
            "new_name": "Goal_Left_Post",
        })

    assert executor.last_result is None
    assert executor.last_receipt is None


def test_autonomous_executor_receipt_detects_argument_tampering():
    executor = BlenderAutonomousExecutor(
        lambda tool, arguments: {
            "ok": True,
            "state": "renamed",
            "details": {"new_name": arguments["new_name"]},
        }
    )
    arguments = {
        "file_name": "object_rename_INCORRECT.blend",
        "object_name": "Goal_Left_post",
        "new_name": "Goal_Left_Post",
    }

    executor("rename_object", arguments)
    arguments["new_name"] = "Tampered"

    assert not executor.receipt_matches_last_execution("rename_object", arguments)


def test_autonomous_executor_rejects_adapter_error_details():
    executor = BlenderAutonomousExecutor(
        lambda tool, arguments: {
            "error": "Object not found",
            "object_name": arguments["object_name"],
        }
    )

    with pytest.raises(RuntimeError, match="did not succeed"):
        executor("move_object", {
            "file_name": "goalpost_test.blend",
            "object_name": "Goal_Left_post",
            "location": [1.0, 2.0, 3.0],
        })

    assert executor.last_result is None
    assert executor.last_receipt is None


def test_autonomous_executor_rejects_adapter_error_status():
    executor = BlenderAutonomousExecutor(
        lambda tool, arguments: {
            "status": "error",
            "error": "Object not found",
        }
    )

    with pytest.raises(RuntimeError, match="did not succeed"):
        executor("move_object", {
            "file_name": "goalpost_test.blend",
            "object_name": "Goal_Left_post",
            "location": [1.0, 2.0, 3.0],
        })
