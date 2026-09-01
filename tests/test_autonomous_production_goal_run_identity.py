from planning.action_authorization import ActionAuthorization
from planning.action_plan import ActionSpec
from planning.autonomous_production_goal import AutonomousProductionGoal
from planning.autonomous_production_goal_run import AutonomousProductionGoalRun
from planning.autonomous_task_sequence import AutonomousTaskSequenceResult
from planning.production_operation_lifecycle import ProductionOperationState


def test_goal_run_exposes_authorization_identity_and_digest():
    goal = AutonomousProductionGoal(
        "goal-1",
        "inspect the scene",
        (ActionSpec("inspect_scene", {"file_name": "scene.blend"}),),
    )
    authorization = ActionAuthorization.issue(list(goal.actions), "goal-authorized")
    sequence = AutonomousTaskSequenceResult(
        ProductionOperationState.COMPLETED,
        ("inspect_scene",),
        1,
        "verified",
    )
    result = AutonomousProductionGoalRun.from_goal(goal, authorization, sequence)

    assert result.authorization_id == "goal-authorized"
    assert result.plan_digest == authorization.plan_digest
    assert result.next_step_index == 1
    assert result.requires_follow_up is False


def test_goal_run_requires_follow_up_when_blocked():
    goal = AutonomousProductionGoal(
        "goal-1",
        "inspect the scene",
        (ActionSpec("inspect_scene", {"file_name": "scene.blend"}),),
    )
    authorization = ActionAuthorization.issue(list(goal.actions), "goal-authorized")
    sequence = AutonomousTaskSequenceResult(
        ProductionOperationState.BLOCKED,
        (),
        0,
        "admission rejected",
    )
    result = AutonomousProductionGoalRun.from_goal(goal, authorization, sequence)

    assert result.requires_follow_up is True
    assert result.completed is False
