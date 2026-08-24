import pytest

from action_plan import ActionPlan, ActionSpec
from planning.action_authorization import ActionAuthorization
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.replan_authorization import ReplanAuthorization


MOVE = {
    "file_name": "test_scene.blend",
    "object_name": "Goal_Left_post",
    "location": [1, 2, 3],
}


def _authorized_replan(evidence):
    action = ActionSpec("move_object", dict(MOVE), "move object")
    plan = ActionPlan([action])
    authorization = ReplanAuthorization.issue(evidence, plan.actions, "replan-1")
    plan.authorization = authorization
    return plan, authorization


def test_replan_requires_replan_authorization_type():
    action = ActionSpec("move_object", dict(MOVE), "move object")
    plan = ActionPlan([action])
    plan.authorization = ActionAuthorization.issue(plan.actions, "ordinary-1")
    boundary = BlenderExecutionBoundary(lambda tool, args: {"ok": True, "state": "moved", "details": {}})

    with pytest.raises(RuntimeError, match="ReplanAuthorization"):
        boundary.execute_authorized_replan(plan, {"objects": []})


def test_replan_authorization_binds_fresh_evidence_and_actions():
    evidence = {"objects": [{"name": "Goal_Left_post"}]}
    plan, authorization = _authorized_replan(evidence)
    calls = []

    boundary = BlenderExecutionBoundary(
        lambda tool, args: calls.append((tool, dict(args))) or {
            "ok": True,
            "state": "moved",
            "details": {"object_name": args["object_name"]},
        }
    )

    result, receipt = boundary.execute_authorized_replan(plan, evidence)

    assert result.state == "moved"
    assert receipt.matches("move_object", MOVE, result)
    assert calls == [("move_object", MOVE)]
    assert authorization.matches(evidence, plan.actions)


def test_stale_replan_evidence_is_blocked_before_execution():
    evidence = {"objects": [{"name": "Goal_Left_post"}]}
    plan, _ = _authorized_replan(evidence)
    calls = []
    boundary = BlenderExecutionBoundary(lambda tool, args: calls.append((tool, args)))

    with pytest.raises(RuntimeError, match="stale or invalid"):
        boundary.execute_authorized_replan(
            plan,
            {"objects": [{"name": "Goal_Left_post", "location": [9, 9, 9]}]},
        )

    assert calls == []
