"""Deterministic future-state generation for Atlas planning.

This module deliberately performs no model reasoning and no tool execution.
Given an already-authorized action plan and explicit target-state requirements,
it produces the only execution future that Python can safely derive: ordered
state checkpoints with stable identifiers.

The purpose is to make the next state explicit before execution rather than
letting an LLM implicitly invent the continuation of a task.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from action_plan import ActionSpec
from planning.target_state import TargetStateEvaluator


@dataclass(frozen=True)
class FutureStep:
    """One deterministic checkpoint in a future execution path."""

    sequence: int
    step_id: str
    phase: str
    description: str
    action: Optional[Dict[str, Any]] = None

    def snapshot(self) -> Dict[str, Any]:
        result = {
            "sequence": self.sequence,
            "step_id": self.step_id,
            "phase": self.phase,
            "description": self.description,
        }
        if self.action is not None:
            result["action"] = dict(self.action)
        return result


class DeterministicFutureGenerator:
    """Generate a stable future execution path from authorized primitives.

    The generator does not choose tools, coordinates, or new actions. It only
    serializes the future implied by the supplied evidence/evaluation/action
    contract. Conditional branches are represented explicitly:

    * target satisfied -> SKIP_WRITES -> VERIFY/COMPLETE
    * target unsatisfied -> each authorized action -> VERIFY -> COMPLETE

    Callers must supply the target decision explicitly. A missing decision is
    rejected so the future cannot silently assume that writes are necessary.
    """

    def __init__(self, evaluator: TargetStateEvaluator):
        self.evaluator = evaluator

    @staticmethod
    def _action_payload(index: int, action: ActionSpec) -> Dict[str, Any]:
        return {
            "index": index,
            "name": action.name or action.tool,
            "tool": action.tool,
            "arguments": dict(action.arguments),
        }

    def generate(self, target_satisfied: Optional[bool], actions: List[ActionSpec]) -> List[FutureStep]:
        if target_satisfied is None:
            raise ValueError("target_satisfied must be resolved before generating a future.")
        if not isinstance(target_satisfied, bool):
            raise TypeError("target_satisfied must be a boolean.")
        if not isinstance(actions, list):
            raise TypeError("actions must be a list of ActionSpec objects.")
        if any(not isinstance(action, ActionSpec) for action in actions):
            raise TypeError("actions must contain only ActionSpec objects.")

        steps: List[FutureStep] = [
            FutureStep(0, "evidence.authoritative", "EVIDENCE", "Use authoritative evidence already acquired."),
            FutureStep(1, "target.evaluated", "TARGET", "Use the resolved target-state decision."),
        ]

        if target_satisfied:
            steps.extend([
                FutureStep(2, "writes.skipped", "SKIP_WRITES", "Target is already satisfied; execute no write actions."),
                FutureStep(3, "verification.pending", "VERIFICATION", "Perform independent postcondition verification."),
                FutureStep(4, "complete", "COMPLETE", "Declare completion only after verification succeeds."),
            ])
            return steps

        for index, action in enumerate(actions):
            steps.append(
                FutureStep(
                    sequence=2 + index,
                    step_id=f"action.{index}",
                    phase="ACTION",
                    description=f"Execute authorized action {index + 1} only after all prior required steps succeed.",
                    action=self._action_payload(index, action),
                )
            )

        verification_sequence = 2 + len(actions)
        steps.extend([
            FutureStep(verification_sequence, "verification.pending", "VERIFICATION", "Perform independent postcondition verification."),
            FutureStep(verification_sequence + 1, "complete", "COMPLETE", "Declare completion only after verification succeeds."),
        ])
        return steps

    def generate_from_result(self, target_result: Any, actions: List[ActionSpec]) -> List[FutureStep]:
        """Generate from a TargetStateResult-like object after validation."""
        if not hasattr(target_result, "satisfied"):
            raise TypeError("target_result must expose a boolean 'satisfied' value.")
        return self.generate(target_result.satisfied, actions)

    @staticmethod
    def snapshot(steps: List[FutureStep]) -> List[Dict[str, Any]]:
        return [step.snapshot() for step in steps]
