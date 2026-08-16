"""Deterministic execution controller for Atlas future plans.

The future generator describes an authorized path; this controller enforces that
path. It never selects a new action and never treats a write response as proof
of the target state. Every transition is explicit and monotonic.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from planning.action_plan import ActionSpec
from planning.future_generator import DeterministicFutureGenerator, FutureStep


class FutureExecutionError(RuntimeError):
    """Raised when an execution transition violates the generated future."""


@dataclass
class FutureExecutionController:
    """Own the cursor through a previously generated deterministic future."""

    steps: List[FutureStep]
    cursor: int = 0
    blocked: bool = False
    failure: Optional[Dict[str, Any]] = None
    verification_satisfied: bool = False

    @classmethod
    def from_target_decision(
        cls,
        generator: DeterministicFutureGenerator,
        target_satisfied: bool,
        actions: List[ActionSpec],
    ) -> "FutureExecutionController":
        return cls(generator.generate(target_satisfied, actions))

    @property
    def complete(self) -> bool:
        return not self.blocked and self.cursor >= len(self.steps) - 1 and self.steps[-1].phase == "COMPLETE" and self.verification_satisfied

    @property
    def current_step(self) -> FutureStep:
        if self.blocked:
            raise FutureExecutionError("Future execution is blocked.")
        if self.cursor >= len(self.steps):
            raise FutureExecutionError("Future execution is exhausted.")
        return self.steps[self.cursor]

    def _require_phase(self, phase: str) -> FutureStep:
        step = self.current_step
        if step.phase != phase:
            raise FutureExecutionError(f"Expected phase {phase}, current phase is {step.phase}.")
        return step

    def advance_evidence(self) -> FutureStep:
        self._require_phase("EVIDENCE")
        self.cursor += 1
        return self.current_step

    def resolve_target(self, target_satisfied: bool) -> FutureStep:
        self._require_phase("TARGET")
        if not isinstance(target_satisfied, bool):
            raise TypeError("target_satisfied must be a boolean.")
        expected_skip = any(step.phase == "SKIP_WRITES" for step in self.steps)
        if target_satisfied != expected_skip:
            self._block("target decision conflicts with generated future")
        self.cursor += 1
        return self.current_step

    def skip_writes(self) -> FutureStep:
        self._require_phase("SKIP_WRITES")
        self.cursor += 1
        return self.current_step

    def execute_current_action(self, tool: str, arguments: Dict[str, Any], result: Dict[str, Any], success: bool) -> FutureStep:
        step = self._require_phase("ACTION")
        expected = step.action or {}
        if tool != expected.get("tool") or arguments != expected.get("arguments"):
            self._block("attempted action does not match the generated future")
        if not success:
            self._block("authorized action failed")
        self.cursor += 1
        return self.current_step

    def verify(self, satisfied: bool) -> FutureStep:
        self._require_phase("VERIFICATION")
        if not isinstance(satisfied, bool):
            raise TypeError("verification result must be a boolean.")
        if not satisfied:
            self._block("independent verification failed")
        self.verification_satisfied = True
        self.cursor += 1
        return self.current_step

    def complete_future(self) -> None:
        self._require_phase("COMPLETE")
        if not self.verification_satisfied:
            raise FutureExecutionError("Completion requires successful independent verification.")
        self.cursor += 1

    def _block(self, reason: str) -> None:
        self.blocked = True
        self.failure = {"reason": reason, "cursor": self.cursor, "step_id": self.steps[self.cursor].step_id}
        raise FutureExecutionError(reason)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "cursor": self.cursor,
            "blocked": self.blocked,
            "complete": self.complete,
            "verification_satisfied": self.verification_satisfied,
            "current_step": self.steps[self.cursor].snapshot() if self.cursor < len(self.steps) else None,
            "failure": self.failure,
        }
