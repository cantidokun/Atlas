"""Fail-closed continuation state for resumable corrective work."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence, Tuple

from action_plan import ActionSpec
from planning.replan_authorization import ReplanAuthorization


@dataclass(frozen=True)
class ContinuationState:
    """Persist only the receipt-bound progress needed to resume safely."""
    task_id: str
    completed_actions: Tuple[ActionSpec, ...]
    last_evidence: Any
    authorization_id: str

    @classmethod
    def create(cls, task_id: str, completed_actions: Sequence[ActionSpec], last_evidence: Any, authorization_id: str):
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("continuation task_id must be a non-empty string")
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise ValueError("continuation authorization_id must be a non-empty string")
        actions = tuple(completed_actions)
        if any(not isinstance(action, ActionSpec) for action in actions):
            raise TypeError("continuation completed_actions must contain ActionSpec values")
        return cls(task_id, actions, last_evidence, authorization_id)

    def authorize_remaining(self, current_evidence: Any, actions: Sequence[ActionSpec]) -> ReplanAuthorization:
        """Issue a new authorization from current evidence; never reuse the saved one."""
        if current_evidence == self.last_evidence:
            raise RuntimeError("continuation requires fresh evidence before resume")
        remaining = list(actions)
        if not remaining:
            raise ValueError("continuation requires at least one remaining action")
        return ReplanAuthorization.issue(current_evidence, remaining, self.authorization_id)
