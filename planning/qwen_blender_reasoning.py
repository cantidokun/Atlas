"""Strict boundary between Qwen reasoning output and Blender planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from planning.action_plan import ActionSpec
from planning.blender_task_planner import BlenderTaskIntent


class QwenReasoningError(ValueError):
    """Raised when model output cannot safely become Blender intent."""


@dataclass(frozen=True)
class QwenReasoning:
    task_id: str
    objective: str
    observation: str
    confidence: float
    actions: tuple[ActionSpec, ...]
    success_evidence: tuple[str, ...]


def parse_qwen_reasoning(payload: Mapping[str, Any]) -> QwenReasoning:
    """Parse only the structured fields Atlas permits from Qwen output."""
    if not isinstance(payload, Mapping):
        raise QwenReasoningError("reasoning output must be an object")

    required = ("task_id", "objective", "observation", "confidence", "actions", "success_evidence")
    missing = [key for key in required if key not in payload]
    if missing:
        raise QwenReasoningError(f"missing reasoning fields: {', '.join(missing)}")

    task_id = payload["task_id"]
    objective = payload["objective"]
    observation = payload["observation"]
    confidence = payload["confidence"]
    actions = payload["actions"]
    success_evidence = payload["success_evidence"]

    if not all(isinstance(value, str) and value.strip() for value in (task_id, objective, observation)):
        raise QwenReasoningError("task_id, objective, and observation must be non-empty strings")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise QwenReasoningError("confidence must be a number between 0 and 1")
    if not isinstance(actions, Sequence) or isinstance(actions, (str, bytes)) or not actions:
        raise QwenReasoningError("actions must be a non-empty array")
    if not isinstance(success_evidence, Sequence) or isinstance(success_evidence, (str, bytes)) or not success_evidence:
        raise QwenReasoningError("success_evidence must be a non-empty array")

    normalized_actions = []
    for item in actions:
        if not isinstance(item, Mapping):
            raise QwenReasoningError("each action must be an object")
        tool = item.get("tool")
        arguments = item.get("arguments")
        if not isinstance(tool, str) or not tool.strip():
            raise QwenReasoningError("action tool must be a non-empty string")
        if not isinstance(arguments, Mapping):
            raise QwenReasoningError("action arguments must be an object")
        normalized_actions.append(ActionSpec(tool=tool.strip(), arguments=dict(arguments)))

    if not all(isinstance(item, str) and item.strip() for item in success_evidence):
        raise QwenReasoningError("success_evidence entries must be non-empty strings")

    return QwenReasoning(
        task_id=task_id.strip(),
        objective=objective.strip(),
        observation=observation.strip(),
        confidence=float(confidence),
        actions=tuple(normalized_actions),
        success_evidence=tuple(item.strip() for item in success_evidence),
    )


def reasoning_to_intent(reasoning: QwenReasoning) -> BlenderTaskIntent:
    """Convert parsed model reasoning into the only intent type the planner accepts."""
    return BlenderTaskIntent(
        task_id=reasoning.task_id,
        objective=reasoning.objective,
        actions=reasoning.actions,
    )
