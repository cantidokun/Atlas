"""Deterministic execution gate for Atlas future plans.

The future generator describes a legal path. This module makes that path
executable without allowing callers to skip, reorder, invent, or mutate steps.
Python owns the cursor; external/model code can only supply results for the
currently permitted checkpoint.
"""

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Callable, Dict, List, Optional

from planning.future_generator import FutureStep

ToolExecutor = Callable[[str, Dict[str, Any]], Dict[str, Any]]


def _canonical_steps(steps: List[FutureStep]) -> str:
    return json.dumps([step.snapshot() for step in steps], sort_keys=True, separators=(",", ":"), default=str)


@dataclass
class FutureExecutionController:
    """Execute one pre-generated future path in strict sequence."""

    steps: List[FutureStep]
    current_index: int = 0
    history: List[Dict[str, Any]] = field(default_factory=list)
    failed: Optional[Dict[str, Any]] = None
    _plan_digest: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.steps, list) or not self.steps:
            raise ValueError("At least one future step is required.")
        if any(not isinstance(step, FutureStep) for step in self.steps):
            raise TypeError("steps must contain only FutureStep objects.")
        sequences = [step.sequence for step in self.steps]
        if sequences != list(range(len(self.steps))):
            raise ValueError("Future step sequences must be contiguous and zero-based.")
        ids = [step.step_id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Future step IDs must be unique.")
        self._plan_digest = self._compute_plan_digest()

    def _compute_plan_digest(self) -> str:
        return hashlib.sha256(_canonical_steps(self.steps).encode("utf-8")).hexdigest()

    def _ensure_integrity(self) -> None:
        if self._compute_plan_digest() == self._plan_digest:
            return
        if self.failed is None:
            step = self.steps[self.current_index] if 0 <= self.current_index < len(self.steps) else None
            self.failed = {
                "sequence": step.sequence if step else self.current_index,
                "step_id": step.step_id if step else None,
                "phase": step.phase if step else "UNKNOWN",
                "error": "Future plan integrity check failed; the authorized future was mutated.",
                "exception_type": "FuturePlanIntegrityError",
            }
            if step is not None:
                self._record(step, "failed", self.failed)
        raise RuntimeError("Future plan integrity check failed; the authorized future was mutated.")

    @property
    def plan_digest(self) -> str:
        return self._plan_digest

    @property
    def complete(self) -> bool:
        return self.failed is None and self.current_index >= len(self.steps)

    @property
    def blocked(self) -> bool:
        return self.failed is not None

    @property
    def current_step(self) -> Optional[FutureStep]:
        if self.complete or self.blocked:
            return None
        return self.steps[self.current_index]

    @property
    def next_action(self) -> Optional[Dict[str, Any]]:
        step = self.current_step
        if step is None or step.phase != "ACTION" or step.action is None:
            return None
        return dict(step.action)

    def _record(self, step: FutureStep, status: str, result: Any = None) -> None:
        entry: Dict[str, Any] = {
            "sequence": step.sequence,
            "step_id": step.step_id,
            "phase": step.phase,
            "status": status,
        }
        if result is not None:
            entry["result"] = result
        self.history.append(entry)

    def acknowledge(self, result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Advance a non-action checkpoint only after an explicit acknowledgement."""
        self._ensure_integrity()
        step = self.current_step
        if step is None:
            raise RuntimeError("Future execution is already resolved.")
        if step.phase == "ACTION":
            raise RuntimeError("Current step is an ACTION; execute it instead of acknowledging it.")
        if step.phase == "VERIFICATION":
            raise RuntimeError("Verification requires an explicit verification result.")
        if step.phase == "COMPLETE":
            raise RuntimeError("Completion is controlled by successful verification.")
        self._record(step, "acknowledged", result)
        self.current_index += 1
        return step.snapshot()

    def execute_current(self, execute: ToolExecutor) -> Dict[str, Any]:
        """Execute exactly the currently authorized action and advance on success."""
        self._ensure_integrity()
        step = self.current_step
        if step is None:
            raise RuntimeError("Future execution is already resolved.")
        if step.phase != "ACTION" or step.action is None:
            raise RuntimeError("Current future step is not an executable ACTION.")
        try:
            result = execute(step.action["tool"], dict(step.action["arguments"]))
        except Exception as exc:
            failure = {
                "sequence": step.sequence,
                "step_id": step.step_id,
                "phase": step.phase,
                "error": str(exc),
                "exception_type": type(exc).__name__,
            }
            self.failed = failure
            self._record(step, "failed", failure)
            raise
        success = "error" not in result
        self._record(step, "succeeded" if success else "failed", result)
        if not success:
            self.failed = {
                "sequence": step.sequence,
                "step_id": step.step_id,
                "phase": step.phase,
                "result": result,
            }
            return result
        self.current_index += 1
        return result

    def verify(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve the verification checkpoint; only a positive result can continue."""
        self._ensure_integrity()
        step = self.current_step
        if step is None:
            raise RuntimeError("Future execution is already resolved.")
        if step.phase != "VERIFICATION":
            raise RuntimeError("Verification is not the current future step.")
        if not isinstance(result, dict):
            raise TypeError("Verification result must be a dictionary.")
        self._record(step, "succeeded" if result.get("satisfied") is True else "failed", result)
        if result.get("satisfied") is not True:
            self.failed = {
                "sequence": step.sequence,
                "step_id": step.step_id,
                "phase": step.phase,
                "result": result,
            }
            return result
        self.current_index += 1
        return result

    def finalize(self) -> Dict[str, Any]:
        """Consume the terminal COMPLETE checkpoint after successful verification."""
        self._ensure_integrity()
        step = self.current_step
        if step is None:
            if self.complete:
                return {"complete": True, "history": list(self.history), "plan_digest": self._plan_digest}
            raise RuntimeError("Future execution is blocked.")
        if step.phase != "COMPLETE":
            raise RuntimeError("Future cannot be finalized before reaching COMPLETE.")
        self._record(step, "completed")
        self.current_index += 1
        return {"complete": True, "history": list(self.history), "plan_digest": self._plan_digest}

    def snapshot(self) -> Dict[str, Any]:
        step = self.current_step
        return {
            "current_index": self.current_index,
            "total_steps": len(self.steps),
            "complete": self.complete,
            "blocked": self.blocked,
            "current_step": step.snapshot() if step is not None else None,
            "next_action": self.next_action,
            "failure": self.failed,
            "history": list(self.history),
            "plan_digest": self._plan_digest,
        }
