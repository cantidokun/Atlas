"""Deterministic conditional action planning for Atlas.

A conditional action plan uses authoritative evidence to decide whether the
requested target state is already satisfied. The decision is made by Python,
not by the reasoning model, and it never grants write authorization.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

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
    """A deterministic predicate over authoritative evidence.

    The original path/expected form remains the default for simple equality
    checks. For more complex soccer-field tasks, callers can provide a Python
    predicate. The predicate is still owned and executed by Python; Qwen
    cannot supply or execute it.
    """

    path: Sequence[str] = field(default_factory=tuple)
    expected: Any = None
    predicate: Optional[Callable[[Dict[str, Any]], bool]] = None
    name: str = "path_equals"

    def matches(self, evidence: Dict[str, Any]) -> bool:
        """Return whether authoritative evidence satisfies the target."""
        if not isinstance(evidence, dict):
            raise ConditionalActionError("Authoritative evidence must be an object.")

        if self.predicate is not None:
            try:
                return bool(self.predicate(evidence))
            except (KeyError, TypeError, ValueError) as exc:
                raise ConditionalActionError(
                    f"Target predicate could not evaluate evidence: {exc}"
                ) from exc

        if not self.path:
            raise ConditionalActionError(
                "Target condition requires a path/expected pair or a predicate."
            )
        actual = _read_path(evidence, self.path)
        return actual == self.expected

    def snapshot(self) -> Dict[str, Any]:
        """Return a serializable description without serializing executable code."""
        return {
            "name": self.name,
            "path": list(self.path),
            "expected": self.expected,
            "predicate_configured": self.predicate is not None,
        }


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
                "condition": self.condition.snapshot(),
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
            "condition": self.condition.snapshot(),
            "evidence": self.evidence,
            "history": list(self.history),
            "action_plan": self.action_plan.snapshot(),
        }
