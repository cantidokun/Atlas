"""Explicit production-goal boundary for Atlas autonomous orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from planning.action_plan import ActionSpec


@dataclass(frozen=True)
class AutonomousProductionGoal:
    """A normalized production objective plus the exact proposed actions.

    The goal is planning data only. It cannot authorize or execute Blender work.
    """

    goal_id: str
    objective: str
    actions: Tuple[ActionSpec, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.goal_id, str) or not self.goal_id.strip():
            raise ValueError("goal_id must be a non-empty string")
        if not isinstance(self.objective, str) or not self.objective.strip():
            raise ValueError("objective must be a non-empty string")
        if not self.actions:
            raise ValueError("actions must contain at least one proposed action")
        if any(not isinstance(action, ActionSpec) for action in self.actions):
            raise TypeError("actions must contain only ActionSpec objects")

    @property
    def action_count(self) -> int:
        return len(self.actions)
