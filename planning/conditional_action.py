"""Deterministic conditional action planning for Atlas.

A conditional action plan uses authoritative evidence to decide whether the
requested target state is already satisfied. The decision is made by Python,
not by the reasoning model, and it never grants write authorization.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from action_plan import ActionPlan, ActionSpec


class ConditionalActionError(ValueError):
    """Raised when conditional action evaluation cannot be completed safely."""


def _read_path(value: Dict[str, Any], path: Sequence[str]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, dict) or key not in current:
            raise ConditionalActionError(
                f"Evidence field is missing: {'.'.join(path)}"
            )
        current = current[key]
    return current


@dataclass(frozen=True)
class TargetCondition:
    """A small, serializable predicate over authoritative evidence."""

    path: Sequence[str]
    expected: Any

    def matches(self, evidence: Dict[str, Any]) -> bool:
        """Return whether the authoritative evidence satisfies the target."""
        if not isinstance(evidence, dict):
            raise ConditionalActionError("Authoritative evidence must be an object.")
        actual = _read_path(evidence, self.path)
        return actual == self.expected


@dataclass
class ConditionalActionPlan:
    """Gate an existing action plan on an evidence-backed target condition."""

    action_plan: ActionPlan
    condition: TargetCondition
    evaluated: bool = False
    target_satisfied: Optional[bool] = None
    decision: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None
    history: List[Dict[str, Any]] = field(default_factory=list)

    def evaluate(self, evidence: Dict[str, Any]) -> bool:
        """Evaluate the target and decide whether writes should be skipped."""
        if self.evaluated:
            raise ConditionalActionError("Conditional action plan is already evaluated.")

        satisfied = self.condition.matches(evidence)
        self.evidence = evidence
        self.evaluated = True
        self.target_satisfied = satisfied
        self.decision = "SKIP_WRITES" if satisfied else "EXECUTE_ACTIONS"
        self.history.append(
            {
                "decision": self.decision,
                "target_satisfied": satisfied,
                "condition_path": list(self.condition.path),
                "expected": self.condition.expected,
            }
        )
        return satisfied

    @property
    def complete(self) -> bool:
        if not self.evaluated:
            return False
        if self.target_satisfied:
            return True
        return self.action_plan.complete

    @property
    def blocked(self) -> bool:
        return self.action_plan.blocked

    @property
    def next_action(self) -> Optional[ActionSpec]:
        if not self.evaluated:
            return None
        if self.target_satisfied:
            return None
        return self.action_plan.next_action

    def snapshot(self) -> Dict[str, Any]:
        return {
            "evaluated": self.evaluated,
            "target_satisfied": self.target_satisfied,
            "decision": self.decision,
            "complete": self.complete,
            "blocked": self.blocked,
            "condition": {
                "path": list(self.condition.path),
                "expected": self.condition.expected,
            },
            "evidence": self.evidence,
            "history": list(self.history),
            "action_plan": self.action_plan.snapshot(),
        }
