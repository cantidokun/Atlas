"""Regression coverage for production-goal planner integration."""

import pytest

from planning.action_plan import ActionSpec
from planning.autonomous_production_goal import AutonomousProductionGoal
from planning.blender_task_planner import BlenderPlanningError, BlenderTaskPlanner


def test_planner_compiles_goal_through_existing_validation_pipeline():
    goal = AutonomousProductionGoal(
        "goal-001",
        "inspect the scene",
        (ActionSpec("inspect_scene", {"file_name": "scene.blend"}, name="inspect"),),
    )

    plan = BlenderTaskPlanner().plan_goal(goal)

    assert plan.actions[0].tool == "inspect_scene"
    assert plan.actions[0].arguments == {"file_name": "scene.blend"}
    assert plan.current_index == 0
    assert plan.authorization is None


def test_planner_goal_rejects_unregistered_capability():
    goal = AutonomousProductionGoal(
        "goal-001",
        "do unsafe thing",
        (ActionSpec("unknown_blender_capability", {}),),
    )

    with pytest.raises(BlenderPlanningError, match="not registered"):
        BlenderTaskPlanner().plan_goal(goal)


def test_planner_goal_requires_goal_type():
    with pytest.raises(BlenderPlanningError, match="AutonomousProductionGoal"):
        BlenderTaskPlanner().plan_goal(object())
