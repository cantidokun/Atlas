"""Strict boundary between model reasoning and Blender task planning.

The model may describe observations, diagnosis, confidence, proposed actions,
and verification criteria, but it never supplies executable Python or bypasses
BlenderTaskPlanner. Atlas converts only the normalized action proposals into a
BlenderTaskIntent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Tuple

from planning.action_plan import ActionSpec
from planning.blender_task_planner import BlenderTaskIntent


class BlenderReasoningContractError(ValueError):
    """Raised when model output cannot be safely normalized."""


@dataclass(frozen=True)
class BlenderReasoning:
    task_id: str
    objective: str
    observations: Tuple[Dict[str, Any], ...]
    diagnosis: str
    confidence: float
    proposed_actions: Tuple[ActionSpec, ...]
    success_criteria: Tuple[str, ...]

    def to_intent(self) -> BlenderTaskIntent:
        if not self.task_id.strip():
            raise BlenderReasoningContractError("task_id must be non-empty")
        if not self.objective.strip():
            raise BlenderReasoningContractError("objective must be non-empty")
        if not self.diagnosis.strip():
            raise BlenderReasoningContractError("diagnosis must be non-empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise BlenderReasoningContractError("confidence must be between 0 and 1")
        if not self.proposed_actions:
            raise BlenderReasoningContractError("at least one proposed action is required")
        if not self.success_criteria:
            raise BlenderReasoningContractError("at least one success criterion is required")
        return BlenderTaskIntent(
            task_id=self.task_id,
            objective=self.objective,
            actions=self.proposed_actions,
        )


def normalize_model_reasoning(payload: Dict[str, Any]) -> BlenderReasoning:
    """Normalize a plain model payload without granting it execution authority."""
    if not isinstance(payload, dict):
        raise BlenderReasoningContractError("model reasoning must be an object")

    actions_raw = payload.get("proposed_actions")
    if not isinstance(actions_raw, list):
        raise BlenderReasoningContractError("proposed_actions must be a list")

    actions = []
    for item in actions_raw:
        if not isinstance(item, dict):
            raise BlenderReasoningContractError("each proposed action must be an object")
        if "tool" not in item or "arguments" not in item:
            raise BlenderReasoningContractError("each proposed action requires tool and arguments")
        if not isinstance(item["tool"], str) or not item["tool"].strip():
            raise BlenderReasoningContractError("action tool must be non-empty")
        if not isinstance(item["arguments"], dict):
            raise BlenderReasoningContractError("action arguments must be an object")
        actions.append(ActionSpec(tool=item["tool"], arguments=dict(item["arguments"]), name=item.get("name")))

    observations = payload.get("observations", [])
    criteria = payload.get("success_criteria", [])
    if not isinstance(observations, list) or not all(isinstance(item, dict) for item in observations):
        raise BlenderReasoningContractError("observations must be a list of objects")
    if not isinstance(criteria, list) or not all(isinstance(item, str) and item.strip() for item in criteria):
        raise BlenderReasoningContractError("success_criteria must be a list of non-empty strings")

    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise BlenderReasoningContractError("confidence must be numeric")

    return BlenderReasoning(
        task_id=payload.get("task_id", ""),
        objective=payload.get("objective", ""),
        observations=tuple(dict(item) for item in observations),
        diagnosis=payload.get("diagnosis", ""),
        confidence=float(confidence),
        proposed_actions=tuple(actions),
        success_criteria=tuple(criteria),
    )
