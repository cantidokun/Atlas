"""Regression coverage for the autonomous production-goal boundary."""
from dataclasses import FrozenInstanceError

import pytest

from planning.action_plan import ActionSpec
from planning.autonomous_production_goal import AutonomousProductionGoal


def test_goal_requires_non_empty_identity_objective_and_actions():
    action = ActionSpec("inspect_scene", {"file_name": "scene.blend"})
    with pytest.raises(ValueError, match="goal_id"):
        AutonomousProductionGoal("", "inspect", (action,))
    with pytest.raises(ValueError, match="objective"):
        AutonomousProductionGoal("goal-1", "", (action,))
    with pytest.raises(ValueError, match="at least one"):
        AutonomousProductionGoal("goal-1", "inspect", ())


def test_goal_rejects_non_action_specs():
    with pytest.raises(TypeError, match="ActionSpec"):
        AutonomousProductionGoal("goal-1", "inspect", (object(),))


def test_goal_is_immutable_and_reports_action_count():
    action = ActionSpec("inspect_scene", {"file_name": "scene.blend"})
    goal = AutonomousProductionGoal("goal-1", "inspect", (action,))
    assert goal.action_count == 1
    with pytest.raises(FrozenInstanceError):
        goal.goal_id = "goal-2"
