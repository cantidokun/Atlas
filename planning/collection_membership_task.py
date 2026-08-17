"""Third Blender task definition: conditionally place an object in Atlas_Test."""
from typing import Any, Dict

from action_plan import ActionSpec
from planning.target_state import StateInvariant, TargetStateEvaluator

TARGET_COLLECTION = "Atlas_Test"
TARGET_OBJECT = "Atlas_Marker"


def collection_membership_target_evaluator() -> TargetStateEvaluator:
    return TargetStateEvaluator([
        StateInvariant(
            "target_object_exists",
            lambda evidence: evidence.get("object_name") == TARGET_OBJECT,
        ),
        StateInvariant(
            "target_collection_membership",
            lambda evidence: evidence.get("collections") == [TARGET_COLLECTION],
        ),
    ])


def collection_membership_action(file_name: str) -> ActionSpec:
    return ActionSpec(
        tool="move_object_to_collection",
        arguments={
            "file_name": file_name,
            "object_name": TARGET_OBJECT,
            "collection_name": TARGET_COLLECTION,
        },
        name="move Atlas_Marker to Atlas_Test",
    )


def collection_membership_target_satisfied(evidence: Dict[str, Any]) -> bool:
    return collection_membership_target_evaluator().evaluate(evidence).satisfied
