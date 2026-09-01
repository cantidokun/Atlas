"""Execution-free preparation record for autonomous production goals."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from planning.action_authorization import ActionAuthorization
from planning.action_plan import ActionPlan, ActionSpec
from planning.autonomous_production_goal import AutonomousProductionGoal


@dataclass(frozen=True)
class AutonomousProductionGoalPreparation:
    """Bind a goal to its normalized plan and exact authorization receipt."""

    goal_id: str
    objective: str
    authorization: ActionAuthorization
    action_names: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.goal_id, str) or not self.goal_id.strip():
            raise ValueError("goal_id must be a non-empty string")
        if not isinstance(self.objective, str) or not self.objective.strip():
            raise ValueError("objective must be a non-empty string")
        if not isinstance(self.authorization, ActionAuthorization):
            raise TypeError("authorization must be an ActionAuthorization")
        if not self.action_names:
            raise ValueError("action_names must contain at least one action")
        if any(not isinstance(name, str) or not name.strip() for name in self.action_names):
            raise ValueError("action_names must contain non-empty strings")

    @property
    def authorization_id(self) -> str:
        return self.authorization.authorization_id

    @property
    def plan_digest(self) -> str:
        return self.authorization.plan_digest

    @property
    def action_count(self) -> int:
        return len(self.action_names)

    def snapshot(self) -> dict[str, object]:
        return {
            "goal_id": self.goal_id,
            "objective": self.objective,
            "authorization": self.authorization.snapshot(),
            "action_names": list(self.action_names),
            "action_count": self.action_count,
        }

    @classmethod
    def from_compilation(
        cls,
        goal: AutonomousProductionGoal,
        action_plan: ActionPlan,
        authorization: ActionAuthorization,
    ) -> "AutonomousProductionGoalPreparation":
        if not isinstance(goal, AutonomousProductionGoal):
            raise TypeError("goal must be an AutonomousProductionGoal")
        if not isinstance(action_plan, ActionPlan):
            raise TypeError("action_plan must be an ActionPlan")
        if not isinstance(authorization, ActionAuthorization):
            raise TypeError("authorization must be an ActionAuthorization")
        if not action_plan.authorized:
            raise RuntimeError("action_plan must be authorized before preparation is recorded")
        if action_plan.authorization is not authorization:
            raise RuntimeError("preparation authorization must be the plan's installed authorization")
        if not authorization.matches(action_plan.actions):
            raise RuntimeError("preparation authorization does not match the exact action plan")
        if not action_plan.actions:
            raise ValueError("action_plan must contain at least one action")
        names = tuple(action.name or action.tool for action in action_plan.actions)
        return cls(goal.goal_id, goal.objective, authorization, names)
