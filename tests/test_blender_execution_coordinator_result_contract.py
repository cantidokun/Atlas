import pytest

from planning.action_authorization import ActionAuthorization
from planning.action_plan import ActionPlan, ActionSpec
from planning.blender_execution_coordinator import BlenderExecutionCoordinator, BlenderExecutionError


def _plan():
    plan = ActionPlan([ActionSpec("inspect_scene", {"file_name": "scene.blend"})])
    plan.authorize(ActionAuthorization.issue(plan.actions, "runner-contract-001"))
    return plan


def test_explicit_false_ok_blocks_plan():
    plan = _plan()
    step = BlenderExecutionCoordinator(plan, lambda *_: {"ok": False, "error": "failed"}).step()

    assert not step.verified
    assert plan.blocked
    assert not plan.complete


def test_explicit_non_boolean_ok_is_not_success():
    plan = _plan()
    step = BlenderExecutionCoordinator(plan, lambda *_: {"ok": 1}).step()

    assert not step.verified
    assert plan.blocked


def test_legacy_success_without_ok_remains_supported():
    plan = _plan()
    step = BlenderExecutionCoordinator(plan, lambda *_: {"status": "ok"}).step()

    assert step.verified
    assert step.complete


def test_legacy_failure_status_blocks_plan():
    plan = _plan()
    step = BlenderExecutionCoordinator(plan, lambda *_: {"status": "failed"}).step()

    assert not step.verified
    assert plan.blocked


def test_blocked_plan_cannot_be_run_again():
    plan = _plan()
    coordinator = BlenderExecutionCoordinator(plan, lambda *_: {"ok": False})
    coordinator.step()

    with pytest.raises(BlenderExecutionError):
        coordinator.run()
