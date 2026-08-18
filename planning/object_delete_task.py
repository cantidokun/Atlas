"""Conditional Blender object deletion for explicit cleanup candidates."""
from typing import Any, Dict

from action_plan import ActionSpec
from planning.target_state import StateInvariant, TargetStateEvaluator

TARGET_OBJECT = "Atlas_Delete_Candidate"


def object_delete_target_evaluator() -> TargetStateEvaluator:
    return TargetStateEvaluator([
        StateInvariant(
            "target_object_absent",
            lambda evidence: TARGET_OBJECT not in evidence.get("object_names", []),
        ),
    ])


def object_delete_action(file_name: str) -> ActionSpec:
    return ActionSpec(
        tool="delete_object",
        arguments={"file_name": file_name, "object_name": TARGET_OBJECT},
        name=f"delete {TARGET_OBJECT}",
    )


def object_delete_target_satisfied(evidence: Dict[str, Any]) -> bool:
    return object_delete_target_evaluator().evaluate(evidence).satisfied
