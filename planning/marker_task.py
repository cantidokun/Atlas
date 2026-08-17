"""Second Blender task definition: conditionally create the Atlas marker.

This module intentionally contains only task-specific data and invariants. It reuses
Atlas's generic evidence, action, conditional, verification, and authorization layers.
"""
from typing import Any, Dict

from action_plan import ActionSpec
from planning.target_state import StateInvariant, TargetStateEvaluator

MARKER_COLLECTION = "Atlas_Test"
MARKER_OBJECT = "Atlas_Marker"


def marker_target_evaluator() -> TargetStateEvaluator:
    return TargetStateEvaluator([
        StateInvariant(
            "marker_exists",
            lambda evidence: any(
                obj.get("name") == MARKER_OBJECT
                for obj in evidence.get("objects", [])
            ),
        ),
        StateInvariant(
            "marker_type_empty",
            lambda evidence: any(
                obj.get("name") == MARKER_OBJECT and obj.get("type") == "EMPTY"
                for obj in evidence.get("objects", [])
            ),
        ),
    ])


def marker_create_action(file_name: str) -> ActionSpec:
    return ActionSpec(
        tool="create_empty_marker",
        arguments={
            "file_name": file_name,
            "collection_name": MARKER_COLLECTION,
            "object_name": MARKER_OBJECT,
        },
        name="create Atlas_Marker",
    )


def marker_target_satisfied(scene: Dict[str, Any]) -> bool:
    return marker_target_evaluator().evaluate(scene).satisfied
