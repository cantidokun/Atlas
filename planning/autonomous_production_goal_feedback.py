"""Immutable feedback context for evidence-driven autonomous goal replanning."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from planning.autonomous_production_goal import AutonomousProductionGoal
from planning.autonomous_production_goal_run import AutonomousProductionGoalRun


@dataclass(frozen=True)
class AutonomousProductionGoalFeedback:
    """Bind authoritative outcome evidence to a prior goal run.

    This record is planning context only. It does not contain an execution
    mechanism, authorization capability, or dispatch instruction.
    """

    goal_id: str
    objective: str
    state: str
    completed_steps: tuple[str, ...]
    next_step_index: int
    authorization_id: str
    plan_digest: str
    reason: str | None
    evidence: Any

    def __post_init__(self) -> None:
        if not isinstance(self.goal_id, str) or not self.goal_id.strip():
            raise ValueError("goal_id must be a non-empty string")
        if not isinstance(self.objective, str) or not self.objective.strip():
            raise ValueError("objective must be a non-empty string")
        if not isinstance(self.state, str) or not self.state.strip():
            raise ValueError("state must be a non-empty string")
        if not isinstance(self.completed_steps, tuple) or any(
            not isinstance(step, str) or not step.strip() for step in self.completed_steps
        ):
            raise TypeError("completed_steps must be a tuple of non-empty strings")
        if not isinstance(self.next_step_index, int) or self.next_step_index < 0:
            raise ValueError("next_step_index must be a non-negative integer")
        if not isinstance(self.authorization_id, str) or not self.authorization_id.strip():
            raise ValueError("authorization_id must be a non-empty string")
        if not isinstance(self.plan_digest, str) or not self.plan_digest.strip():
            raise ValueError("plan_digest must be a non-empty string")
        if self.reason is not None and not isinstance(self.reason, str):
            raise TypeError("reason must be a string or None")

    @classmethod
    def from_run(
        cls,
        run: AutonomousProductionGoalRun,
        evidence: Any,
    ) -> "AutonomousProductionGoalFeedback":
        if not isinstance(run, AutonomousProductionGoalRun):
            raise TypeError("run must be an AutonomousProductionGoalRun")
        if not run.requires_follow_up:
            raise RuntimeError("completed goal runs do not require corrective feedback")
        return cls(
            goal_id=run.goal_id,
            objective=run.objective,
            state=run.state.value,
            completed_steps=run.completed_steps,
            next_step_index=run.next_step_index,
            authorization_id=run.authorization_id,
            plan_digest=run.plan_digest,
            reason=run.follow_up_reason,
            evidence=evidence,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "objective": self.objective,
            "state": self.state,
            "completed_steps": list(self.completed_steps),
            "next_step_index": self.next_step_index,
            "authorization_id": self.authorization_id,
            "plan_digest": self.plan_digest,
            "reason": self.reason,
            "evidence": self.evidence,
        }


ProposeReplacementGoal = Callable[[AutonomousProductionGoalFeedback], AutonomousProductionGoal]
