from planning.action_authorization import ActionAuthorization
from planning.action_plan import ActionSpec
from planning.autonomous_production_goal import AutonomousProductionGoal
from planning.autonomous_production_goal_feedback import AutonomousProductionGoalFeedback
from planning.autonomous_production_goal_run import AutonomousProductionGoalRun
from planning.autonomous_production_orchestrator import AutonomousProductionOrchestrator
from planning.autonomous_task_sequence import AutonomousTaskSequenceResult
from planning.blender_task_planner import BlenderTaskPlanner
from planning.autonomous_production_goal_planner import AutonomousProductionGoalPlanner
from planning.production_operation_lifecycle import ProductionOperationState


def _blocked_run() -> AutonomousProductionGoalRun:
    goal = AutonomousProductionGoal(
        "goal-1",
        "inspect the scene",
        (ActionSpec("inspect_scene", {"file_name": "scene.blend"}, name="inspect"),),
    )
    authorization = ActionAuthorization.issue(list(goal.actions), "old-authorization")
    sequence = AutonomousTaskSequenceResult(
        ProductionOperationState.BLOCKED,
        (),
        0,
        "authoritative verification failed",
    )
    return AutonomousProductionGoalRun.from_goal(goal, authorization, sequence)


def test_feedback_binds_authoritative_evidence_to_blocked_run():
    run = _blocked_run()
    evidence = {"verified": False, "failed_invariant": "object_at_target"}

    feedback = AutonomousProductionGoalFeedback.from_run(run, evidence)

    assert feedback.snapshot() == {
        "goal_id": "goal-1",
        "objective": "inspect the scene",
        "state": "blocked",
        "completed_steps": [],
        "next_step_index": 0,
        "authorization_id": "old-authorization",
        "plan_digest": run.plan_digest,
        "reason": "authoritative verification failed",
        "evidence": evidence,
    }


def test_completed_run_cannot_enter_feedback_loop():
    goal = AutonomousProductionGoal(
        "goal-1",
        "inspect the scene",
        (ActionSpec("inspect_scene", {"file_name": "scene.blend"}, name="inspect"),),
    )
    authorization = ActionAuthorization.issue(list(goal.actions), "authorization")
    sequence = AutonomousTaskSequenceResult(
        ProductionOperationState.COMPLETED,
        ("inspect",),
        1,
        "verified",
    )
    run = AutonomousProductionGoalRun.from_goal(goal, authorization, sequence)

    try:
        AutonomousProductionGoalFeedback.from_run(run, {})
    except RuntimeError as exc:
        assert str(exc) == "completed goal runs do not require corrective feedback"
    else:
        raise AssertionError("completed run unexpectedly produced corrective feedback")


def test_replan_compiles_and_reauthorizes_replacement_goal():
    original = _blocked_run()
    feedback = AutonomousProductionGoalFeedback.from_run(original, {"verified": False})
    orchestrator = object.__new__(AutonomousProductionOrchestrator)
    object.__setattr__(orchestrator, "goal_planner", AutonomousProductionGoalPlanner(BlenderTaskPlanner()))
    object.__setattr__(orchestrator, "authorize", lambda plan: ActionAuthorization.issue(plan.actions, "new-authorization"))

    replacement = AutonomousProductionGoal(
        "goal-2",
        "inspect a corrected scene",
        (ActionSpec("inspect_scene", {"file_name": "corrected.blend"}, name="inspect-corrected"),),
    )
    seen = []

    goal, action_plan, authorization = orchestrator.prepare_replan(
        feedback,
        lambda incoming: (seen.append(incoming), replacement)[1],
    )

    assert seen == [feedback]
    assert goal == replacement
    assert action_plan.actions[0].arguments == {"file_name": "corrected.blend"}
    assert authorization.authorization_id == "new-authorization"
    assert authorization.authorization_id != feedback.authorization_id
