from planning.action_authorization import ActionAuthorization
from planning.action_plan import ActionPlan, ActionSpec
from planning.blender_execution_coordinator import BlenderExecutionCoordinator


def _authorized_plan():
    plan = ActionPlan([ActionSpec("inspect_scene", {"file_name": "scene.blend"})])
    plan.authorize(ActionAuthorization.issue(plan.actions, "auth-result-integrity"))
    return plan


def test_coordinator_treats_explicit_ok_false_as_execution_failure():
    plan = _authorized_plan()
    coordinator = BlenderExecutionCoordinator(
        plan,
        lambda *_: {"ok": False, "state": "blocked", "details": {"error": "Blender rejected write"}},
    )

    step = coordinator.step()

    assert step.verified is False
    assert step.complete is False
    assert plan.blocked is True
    assert plan.failed["success"] is False


def test_coordinator_preserves_legacy_status_success_contract():
    plan = _authorized_plan()
    coordinator = BlenderExecutionCoordinator(
        plan,
        lambda *_: {"status": "ok", "objects": 42},
    )

    step = coordinator.step()

    assert step.verified is True
    assert step.complete is True
