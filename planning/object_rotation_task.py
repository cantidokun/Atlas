"""Conditional Blender object rotation task."""
from typing import Any, Dict, List

from action_plan import ActionSpec
from planning.target_state import StateInvariant, TargetStateEvaluator

TARGET_OBJECT = "Atlas_Rotation_Candidate"
TARGET_ROTATION = [0.0, 0.0, 90.0]


def _rotation_matches(evidence: Dict[str, Any]) -> bool:
    actual = evidence.get("rotation_degrees")
    if not isinstance(actual, list) or len(actual) != 3:
        return False
    return all(abs(float(got) - wanted) <= 1e-4 for got, wanted in zip(actual, TARGET_ROTATION))


def object_rotation_target_evaluator() -> TargetStateEvaluator:
    return TargetStateEvaluator([
        StateInvariant("target_object_exists", lambda evidence: evidence.get("object_name") == TARGET_OBJECT),
        StateInvariant("target_rotation", _rotation_matches),
    ])


def object_rotation_action(file_name: str) -> ActionSpec:
    return ActionSpec(
        tool="set_object_rotation",
        arguments={"file_name": file_name, "object_name": TARGET_OBJECT, "rotation_degrees": list(TARGET_ROTATION)},
        name=f"rotate {TARGET_OBJECT}",
    )


def object_rotation_target_satisfied(evidence: Dict[str, Any]) -> bool:
    return object_rotation_target_evaluator().evaluate(evidence).satisfied
