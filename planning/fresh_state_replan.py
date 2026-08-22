"""Fail-closed bridge for replanning from freshly observed world state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List

from action_plan import ActionSpec
from planning.replan_authorization import ReplanAuthorization


@dataclass(frozen=True)
class FreshStateReplan:
    """A replacement plan bound to the exact evidence that produced it."""

    evidence: Any
    actions: List[ActionSpec]
    authorization: ReplanAuthorization

    @classmethod
    def create(
        cls,
        evidence_supplier: Callable[[], Any],
        planner: Callable[[Any], List[ActionSpec]],
        authorization_id: str,
    ) -> "FreshStateReplan":
        evidence = evidence_supplier()
        if evidence is None:
            raise RuntimeError("fresh evidence is required before replanning")
        actions = planner(evidence)
        if not isinstance(actions, list):
            raise TypeError("replanner must return a list of ActionSpec objects")
        if not all(isinstance(action, ActionSpec) for action in actions):
            raise TypeError("replanner must return only ActionSpec objects")
        authorization = ReplanAuthorization.issue(evidence, actions, authorization_id)
        return cls(evidence=evidence, actions=list(actions), authorization=authorization)

    def validate_before_execution(self, evidence: Any, actions: List[ActionSpec]) -> None:
        if not isinstance(actions, list) or not all(isinstance(action, ActionSpec) for action in actions):
            raise TypeError("replacement actions must be a list of ActionSpec objects")
        if not self.authorization.matches(evidence, actions):
            raise RuntimeError("replacement plan is stale or authorization-bound evidence changed")

    def snapshot(self) -> dict:
        return {
            "evidence": self.evidence,
            "actions": [
                {
                    "tool": action.tool,
                    "arguments": dict(action.arguments),
                    "name": action.name,
                    "requires_success": action.requires_success,
                }
                for action in self.actions
            ],
            "authorization": self.authorization.snapshot(),
        }
