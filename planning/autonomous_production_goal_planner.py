"""Compile production goals through the canonical Blender task planner."""
from __future__ import annotations

from dataclasses import dataclass

from planning.action_plan import ActionPlan
from planning.autonomous_production_goal import AutonomousProductionGoal
from planning.blender_task_planner import BlenderTaskIntent, BlenderTaskPlanner


class AutonomousProductionGoalPlanningError(ValueError):
    """Raised when a production goal cannot be safely compiled."""


@dataclass(frozen=True)
class AutonomousProductionGoalPlanner:
    """Translate a planning-only production goal into a validated ActionPlan."""

    task_planner: BlenderTaskPlanner

    def __post_init__(self) -> None:
        if not isinstance(self.task_planner, BlenderTaskPlanner):
            raise TypeError("task_planner must be a BlenderTaskPlanner")

    def compile(self, goal: AutonomousProductionGoal) -> ActionPlan:
        if not isinstance(goal, AutonomousProductionGoal):
            raise AutonomousProductionGoalPlanningError("goal must be an AutonomousProductionGoal")
        intent = BlenderTaskIntent(
            task_id=goal.goal_id,
            objective=goal.objective,
            actions=goal.actions,
        )
        try:
            return self.task_planner.plan(intent)
        except (TypeError, ValueError) as exc:
            raise AutonomousProductionGoalPlanningError(str(exc)) from exc
