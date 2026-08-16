"""Generic target-state evaluation for conditional Atlas actions."""
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List


class TargetStateEvaluationError(RuntimeError):
    """Raised when target-state evaluation cannot safely produce a decision."""


@dataclass(frozen=True)
class StateInvariant:
    """A named, deterministic predicate over authoritative evidence."""

    name: str
    predicate: Callable[[Any], bool]

    def evaluate(self, evidence: Any) -> bool:
        try:
            result = self.predicate(evidence)
        except Exception as exc:
            raise TargetStateEvaluationError(
                f"Invariant '{self.name}' could not be evaluated: {exc}"
            ) from exc
        if not isinstance(result, bool):
            raise TargetStateEvaluationError(
                f"Invariant '{self.name}' must return bool, got {type(result).__name__}."
            )
        return result


@dataclass(frozen=True)
class TargetStateResult:
    """Immutable result of evaluating all required state invariants."""

    satisfied: bool
    invariants: Dict[str, bool]

    @property
    def failed(self) -> List[str]:
        return [name for name, passed in self.invariants.items() if not passed]

    def snapshot(self) -> Dict[str, Any]:
        return {
            "satisfied": self.satisfied,
            "invariants": dict(self.invariants),
            "failed": list(self.failed),
        }


class TargetStateEvaluator:
    """Evaluate a target state from authoritative evidence only.

    All invariants are evaluated every time. The target is satisfied only when
    every required invariant passes. A single failed or unevaluable invariant
    therefore fails closed and prevents conditional execution from assuming
    that the requested state already exists.
    """

    def __init__(self, invariants: Iterable[StateInvariant]):
        self.invariants = tuple(invariants)
        if not self.invariants:
            raise ValueError("At least one target-state invariant is required.")
        names = [invariant.name for invariant in self.invariants]
        if any(not name for name in names):
            raise ValueError("Target-state invariant names must be non-empty.")
        if len(names) != len(set(names)):
            raise ValueError("Target-state invariant names must be unique.")

    def evaluate(self, evidence: Any) -> TargetStateResult:
        results = {
            invariant.name: invariant.evaluate(evidence)
            for invariant in self.invariants
        }
        return TargetStateResult(
            satisfied=all(results.values()),
            invariants=results,
        )
