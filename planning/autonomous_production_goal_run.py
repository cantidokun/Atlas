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
    """Bind a production goal to the authorization and sequence outcome."""

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
    def next_step_index(self) -> int:
        return self.sequence.next_step_index

    @property
    def reason(self) -> str:
        return self.sequence.reason

    @property
    def authorization_id(self) -> str:
        return self.authorization.authorization_id

    @property
    def plan_digest(self) -> str:
        return self.authorization.plan_digest

    @property
    def requires_follow_up(self) -> bool:
        return not self.completed

    @property
    def follow_up_reason(self) -> str | None:
        """Return a stable machine-readable reason when another planning pass is needed."""
        if self.completed:
            return None
        if self.state is ProductionOperationState.BLOCKED:
            return self.reason
        return "autonomous production goal did not reach a terminal completed state"

    def follow_up_request(self) -> dict[str, Any] | None:
        """Return planning-only context for a future evidence/replan decision.

        This structure deliberately contains no executable tool call, capability,
        authorization, or dispatch instruction.
        """
        if not self.requires_follow_up:
            return None
        return {
            "goal_id": self.goal_id,
            "objective": self.objective,
            "state": self.state.value,
            "completed_steps": list(self.completed_steps),
            "next_step_index": self.next_step_index,
            "authorization_id": self.authorization_id,
            "plan_digest": self.plan_digest,
            "reason": self.follow_up_reason,
            "decision_required": True,
        }

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
            "requires_follow_up": self.requires_follow_up,
            "follow_up_reason": self.follow_up_reason,
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
        if not isinstance(authorization, ActionAuthorization):
            raise TypeError("authorization must be an ActionAuthorization")
        if not isinstance(sequence, AutonomousTaskSequenceResult):
            raise TypeError("sequence must be an AutonomousTaskSequenceResult")
        return cls(goal.goal_id, goal.objective, authorization, sequence)
