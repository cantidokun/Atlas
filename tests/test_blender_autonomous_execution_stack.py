import pytest

from controller.blender_capabilities import create_blender_command_registry
from planning.blender_autonomous_executor import BlenderAutonomousExecutor
from planning.blender_verification import BlenderVerificationError


MOVE = {
    "file_name": "test_scene.blend",
    "object_name": "Goal_Left_post",
    "location": [1.0, 2.0, 3.0],
}


def test_full_offline_autonomous_stack_reaches_verified_receipt():
    calls = []

    def fake_blender(tool, arguments):
        calls.append((tool, arguments.copy()))
        return {
            "ok": True,
            "state": "moved",
            "details": {"object_name": arguments["object_name"]},
        }

    executor = BlenderAutonomousExecutor(fake_blender)
    result = executor("move_object", MOVE)

    assert result == {
        "ok": True,
        "state": "moved",
        "details": {"object_name": "Goal_Left_post"},
    }
    assert executor.last_result is not None
    assert executor.last_receipt is not None
    assert executor.receipt_matches_last_execution("move_object", MOVE)
    assert calls == [("move_object", MOVE)]


def test_full_stack_blocks_unauthorized_command_before_execution():
    calls = []
    executor = BlenderAutonomousExecutor(
        lambda tool, args: calls.append((tool, args)) or {
            "ok": True, "state": "unexpected", "details": {}
        }
    )

    with pytest.raises(ValueError, match="not registered"):
        executor("execute_arbitrary_python", {})

    assert calls == []
    assert executor.last_receipt is None


def test_full_stack_blocks_malformed_arguments_before_execution():
    calls = []
    executor = BlenderAutonomousExecutor(
        lambda tool, args: calls.append((tool, args)) or {
            "ok": True, "state": "unexpected", "details": {}
        }
    )

    with pytest.raises(ValueError, match="exactly three numeric values"):
        executor("move_object", {**MOVE, "location": [1.0, 2.0]})

    assert calls == []
    assert executor.last_receipt is None


def test_full_stack_blocks_failed_result_before_receipt():
    executor = BlenderAutonomousExecutor(
        lambda tool, args: {"ok": False, "state": "failed", "details": {"reason": "fixture"}}
    )

    with pytest.raises(BlenderVerificationError):
        executor("move_object", MOVE)

    assert executor.last_result is None
    assert executor.last_receipt is None


def test_default_stack_uses_live_concrete_registry_without_authority_expansion():
    executor = BlenderAutonomousExecutor(command_registry=create_blender_command_registry())
    assert set(executor._adapter.supported_tools) == set(create_blender_command_registry().names())
