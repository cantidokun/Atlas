"""Fail-closed coordinator for dependent corrective actions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Sequence

from action_plan import ActionSpec
from planning.replan_authorization import ReplanAuthorization


@dataclass(frozen=True)
class CorrectiveStep:
    """One corrective mutation plus the evidence that authorized it."""
    evidence: Any
    action: ActionSpec
    authorization: ReplanAuthorization


class MultiStepCorrectiveRecovery:
    """Build and execute dependent corrective steps one fresh state at a time."""

    def __init__(self, observe: Callable[[], Any], plan: Callable[[Any], Sequence[ActionSpec]], authorization_id: str):
        self.observe = observe
        self.plan = plan
        self.authorization_id = authorization_id

    def prepare(self) -> List[CorrectiveStep]:
        evidence = self.observe()
        actions = list(self.plan(evidence))
        if not actions:
            return []
        return [CorrectiveStep(
            evidence=evidence,
            action=action,
            authorization=ReplanAuthorization.issue(evidence, [action], self.authorization_id),
        ) for action in actions]

    def validate_step(self, step: CorrectiveStep, fresh_evidence: Any) -> None:
        if not step.authorization.matches(fresh_evidence, [step.action]):
            raise RuntimeError("corrective step authorization is stale; re-observation required")

    def next_step(self) -> CorrectiveStep | None:
        steps = self.prepare()
        return steps[0] if steps else None
