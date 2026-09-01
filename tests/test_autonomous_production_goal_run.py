from planning.action_plan import ActionSpec
from planning.action_authorization import ActionAuthorization
from planning.autonomous_production_goal import AutonomousProductionGoal
from planning.autonomous_production_goal_run import AutonomousProductionGoalRun
from planning.autonomous_task_sequence import AutonomousTaskSequenceResult
from planning.production_operation_lifecycle import ProductionOperationState


def test_completed_goal_has_no_follow_up_request():
    goal = AutonomousProductionGoal(
        "goal-1",
        "inspect the scene",
        (ActionSpec("inspect_scene", {"file_name": "scene.blend"}, name="inspect"),),
    )
    authorization = ActionAuthorization.issue(list(goal.actions), "goal-authorized")
    sequence = AutonomousTaskSequenceResult(
        ProductionOperationState.COMPLETED,
        ("inspect",),
        1,
        "verified",
    )

    result = AutonomousProductionGoalRun.from_goal(goal, authorization, sequence)

    assert result.requires_follow_up is False
    assert result.follow_up_reason is None
    assert result.follow_up_request() is None


def test_blocked_goal_follow_up_is_non_executable_context():
    goal = AutonomousProductionGoal(
        "goal-1",
        "inspect the scene",
        (ActionSpec("inspect_scene", {"file_name": "scene.blend"}, name="inspect"),),
    )
    authorization = ActionAuthorization.issue(list(goal.actions), "goal-authorized")
    sequence = AutonomousTaskSequenceResult(
        ProductionOperationState.BLOCKED,
        (),
        0,
        "runtime admission rejected",
    )

    result = AutonomousProductionGoalRun.from_goal(goal, authorization, sequence)
    request = result.follow_up_request()

    assert request == {
        "goal_id": "goal-1",
        "objective": "inspect the scene",
        "state": "blocked",
        "completed_steps": [],
        "next_step_index": 0,
        "authorization_id": "goal-authorized",
        "plan_digest": authorization.plan_digest,
        "reason": "runtime admission rejected",
        "decision_required": True,
    }
    assert "tool" not in request
    assert "arguments" not in request
    assert "dispatch" not in request
