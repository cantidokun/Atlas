"""Generic post-action verification state for Atlas.

Verification is intentionally separate from action execution. A write result is
never treated as proof that the requested state was reached; fresh authoritative
evidence must be evaluated against an explicit postcondition.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional

from planning.target_state import TargetStateEvaluationError, TargetStateEvaluator, TargetStateResult


@dataclass
class VerificationPlan:
    """Require independent post-action evidence before declaring completion."""

    evaluator: TargetStateEvaluator
    required: bool = True
    result: Optional[TargetStateResult] = None
    error: Optional[str] = None

    @property
    def complete(self) -> bool:
        return (not self.required) or (self.result is not None and self.result.satisfied)

    @property
    def blocked(self) -> bool:
        return self.error is not None or (self.result is not None and not self.result.satisfied)

    @property
    def pending(self) -> bool:
        return self.required and self.result is None and self.error is None

    def verify(self, evidence: Any) -> TargetStateResult:
        if not self.required:
            raise RuntimeError("Verification is not required for this plan.")
        if self.result is not None or self.error is not None:
            raise RuntimeError("Verification has already been resolved.")
        try:
            result = self.evaluator.evaluate(evidence)
        except TargetStateEvaluationError as exc:
            self.error = str(exc)
            raise
        self.result = result
        return result

    def snapshot(self) -> Dict[str, Any]:
        return {
            "required": self.required,
            "pending": self.pending,
            "complete": self.complete,
            "blocked": self.blocked,
            "result": self.result.snapshot() if self.result is not None else None,
            "error": self.error,
        }
