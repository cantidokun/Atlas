import pytest

from planning.action_authorization import ActionAuthorization
from planning.action_plan import ActionPlan, ActionSpec
from planning.blender_execution_coordinator import BlenderExecutionCoordinator, BlenderExecutionError


def _authorized_plan(actions):
    plan = ActionPlan(actions=list(actions))
    plan.authorize(ActionAuthorization.issue(plan.actions, "auth-001"))
    return plan


def test_coordinator_executes_one_verified_action_and_checkpoints():
    plan = _authorized_plan([
        ActionSpec("inspect_scene", {"file_name": "scene.blend"}),
    ])
    calls = []
    checkpoints = []

    def execute(tool, arguments):
        calls.append((tool, arguments))
        return {"status": "ok", "objects": 42}

    def verify(tool, arguments, result):
        return result.get("objects") == 42

    coordinator = BlenderExecutionCoordinator(plan, execute, verify, checkpoints.append)
    step = coordinator.step()

    assert step.verified is True
    assert step.complete is True
    assert calls == [("inspect_scene", {"file_name": "scene.blend"})]
    assert checkpoints[-1]["complete"] is True


def test_coordinator_does_not_execute_without_authorization():
    plan = ActionPlan([ActionSpec("inspect_scene", {"file_name": "scene.blend"})])
    called = False

    def execute(*args):
        nonlocal called
        called = True
        return {"status": "ok"}

    with pytest.raises(BlenderExecutionError, match="requires valid authorization"):
        BlenderExecutionCoordinator(plan, execute).step()

    assert called is False


def test_failed_verification_blocks_required_action():
    plan = _authorized_plan([
        ActionSpec("inspect_scene", {"file_name": "scene.blend"}, requires_success=True),
        ActionSpec("inspect_scene_health", {"file_name": "scene.blend"}),
    ])

    coordinator = BlenderExecutionCoordinator(
        plan,
        lambda *_: {"status": "ok"},
        lambda *_: False,
    )

    step = coordinator.step()

    assert step.verified is False
    assert plan.blocked is True
    assert plan.next_action is None


def test_executor_failure_is_recorded_and_blocks_required_action():
    plan = _authorized_plan([
        ActionSpec("inspect_scene", {"file_name": "scene.blend"}),
    ])

    coordinator = BlenderExecutionCoordinator(
        plan,
        lambda *_: {"status": "error", "error": "Blender unavailable"},
    )

    step = coordinator.step()

    assert step.verified is False
    assert plan.blocked is True
    assert plan.failed["result"]["error"] == "Blender unavailable"


def test_run_stops_at_required_failure_without_executing_following_actions():
    plan = _authorized_plan([
        ActionSpec("inspect_scene", {"file_name": "scene.blend"}),
        ActionSpec("inspect_scene_health", {"file_name": "scene.blend"}),
    ])
    calls = []

    def execute(tool, arguments):
        calls.append(tool)
        return {"status": "error"}

    steps = BlenderExecutionCoordinator(plan, execute).run()

    assert len(steps) == 1
    assert calls == ["inspect_scene"]
    assert plan.blocked is True
