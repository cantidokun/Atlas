"""Audit-oriented result for an autonomous production goal run."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple

from planning.action_authorization import ActionAuthorization
from planning.autonomous_production_goal import AutonomousProductionGoal
from planning.autonomous_task_sequence import AutonomousTaskSequenceResult
from planning.production_operation_lifecycle import ProductionOperationState


@dataclass(frozen=True)
class AutonomousProductionGoalRun:
    """Bind a production goal to its authorized sequence outcome."""

    goal_id: str
    objective: str
    authorization: ActionAuthorization
    sequence: AutonomousTaskSequenceResult

    def __post_init__(self) -> None:
        if not isinstance(self.goal_id, str) or not self.goal_id.strip():
            raise ValueError("goal_id must be a non-empty string")
        if not isinstance(self.objective, str) or not self.objective.strip():
            raise ValueError("objective must be a non-empty string")
        if not isinstance(self.authorization, ActionAuthorization):
            raise TypeError("authorization must be an ActionAuthorization")
        if not isinstance(self.sequence, AutonomousTaskSequenceResult):
            raise TypeError("sequence must be an AutonomousTaskSequenceResult")

    @property
    def state(self) -> ProductionOperationState:
        return self.sequence.state

    @property
    def completed(self) -> bool:
        return self.sequence.completed

    @property
    def completed_steps(self) -> Tuple[str, ...]:
        return self.sequence.completed_steps

    @property
    def reason(self) -> str:
        return self.sequence.reason

    def snapshot(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "objective": self.objective,
            "authorization": self.authorization.snapshot(),
            "sequence": {
                "state": self.sequence.state.value,
                "completed_steps": list(self.sequence.completed_steps),
                "next_step_index": self.sequence.next_step_index,
                "reason": self.sequence.reason,
            },
        }

    @classmethod
    def from_goal(
        cls,
        goal: AutonomousProductionGoal,
        authorization: ActionAuthorization,
        sequence: AutonomousTaskSequenceResult,
    ) -> "AutonomousProductionGoalRun":
        if not isinstance(goal, AutonomousProductionGoal):
            raise TypeError("goal must be an AutonomousProductionGoal")
        if not authorization.matches(goal.actions):
            raise RuntimeError("authorization does not match the goal's exact actions")
        return cls(goal.goal_id, goal.objective, authorization, sequence)
