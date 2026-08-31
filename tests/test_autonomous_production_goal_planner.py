import pytest

from planning.action_plan import ActionPlan, ActionSpec
from planning.autonomous_production_goal import AutonomousProductionGoal
from planning.autonomous_production_goal_planner import (
    AutonomousProductionGoalPlanner,
    AutonomousProductionGoalPlanningError,
)
from planning.blender_task_planner import BlenderTaskPlanner


def test_compile_routes_goal_through_canonical_task_planner():
    goal = AutonomousProductionGoal(
        "goal-1",
        "inspect the scene",
        (ActionSpec("inspect_scene", {"file_name": "scene.blend"}),),
    )
    plan = AutonomousProductionGoalPlanner(BlenderTaskPlanner()).compile(goal)
    assert isinstance(plan, ActionPlan)
    assert plan.actions[0].tool == "inspect_scene"
    assert plan.authorized is False


def test_compile_rejects_invalid_goal_type():
    planner = AutonomousProductionGoalPlanner(BlenderTaskPlanner())
    with pytest.raises(AutonomousProductionGoalPlanningError, match="goal must be"):
        planner.compile(object())


def test_compile_rejects_unknown_blender_capability():
    goal = AutonomousProductionGoal(
        "goal-1",
        "do unsafe thing",
        (ActionSpec("not_registered", {}),),
    )
    with pytest.raises(AutonomousProductionGoalPlanningError, match="not registered"):
        AutonomousProductionGoalPlanner(BlenderTaskPlanner()).compile(goal)
