from planning.action_authorization import ActionAuthorization
from planning.action_plan import ActionPlan, ActionSpec


def _authorized_plan():
    plan = ActionPlan([ActionSpec("inspect_scene", {"file_name": "scene.blend"})])
    plan.authorize(ActionAuthorization.issue(plan.actions, "auth-evidence-integrity"))
    return plan


def test_recorded_arguments_are_not_affected_by_later_action_mutation():
    plan = _authorized_plan()
    action = plan.next_action
    assert action is not None

    plan.record_result({"ok": True}, True)
    action.arguments["file_name"] = "mutated.blend"

    assert plan.completed[0]["arguments"] == {"file_name": "scene.blend"}


def test_recorded_result_is_not_affected_by_later_result_mutation():
    plan = _authorized_plan()
    result = {"ok": True, "objects": ["Cube"]}

    plan.record_result(result, True)
    result["objects"].append("Camera")
    result["ok"] = False

    assert plan.completed[0]["result"] == {"ok": True, "objects": ["Cube"]}


def test_snapshot_isolated_from_mutation_of_completed_evidence():
    plan = _authorized_plan()
    plan.record_result({"ok": True, "details": {"objects": 1}}, True)

    snapshot = plan.snapshot()
    plan.completed[0]["result"]["details"]["objects"] = 99

    assert snapshot["completed"][0]["result"]["details"]["objects"] == 1
