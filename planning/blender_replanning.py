"""Evidence-driven replanning for the Blender Agent.

Replanning never mutates an existing authorized plan. A new intent must be
constructed and passed through the normal planner/authorization boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from planning.blender_agent_state import BlenderAgentState, BlenderObservation
from planning.blender_task_planner import BlenderTaskIntent


class BlenderReplanningError(RuntimeError):
    """Raised when a replanning decision cannot be safely produced."""


@dataclass(frozen=True)
class ReplanDecision:
    satisfied: bool
    next_intent: Optional[BlenderTaskIntent]
    reason: str


Reasoner = Callable[[BlenderAgentState], Optional[BlenderTaskIntent]]


class BlenderReplanner:
    """Ask a reasoning adapter for a new intent using only verified state."""

    def __init__(self, reasoner: Reasoner):
        self._reasoner = reasoner

    def decide(self, state: BlenderAgentState, observation: BlenderObservation) -> ReplanDecision:
        if not observation.verified:
            raise BlenderReplanningError("replanning requires verified observation")

        state.record_observation(observation)

        if state.objective_satisfied:
            return ReplanDecision(True, None, "objective already satisfied")

        next_intent = self._reasoner(state)
        if next_intent is None:
            return ReplanDecision(False, None, "reasoner could not determine a safe next action")
        if not isinstance(next_intent, BlenderTaskIntent):
            raise BlenderReplanningError("reasoner must return BlenderTaskIntent or None")

        return ReplanDecision(False, next_intent, "objective remains unresolved")
