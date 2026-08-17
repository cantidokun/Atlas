"""Third Blender task definition: conditionally parent Atlas_Marker to the goalpost."""
from typing import Any, Dict

from action_plan import ActionSpec
from planning.target_state import StateInvariant, TargetStateEvaluator

MARKER_OBJECT = "Atlas_Marker"
PARENT_OBJECT = "Goal_Left_post"


def parent_target_evaluator() -> TargetStateEvaluator:
    return TargetStateEvaluator([
        StateInvariant(
            "marker_exists",
            lambda evidence: evidence.get("object_name") == MARKER_OBJECT,
        ),
        StateInvariant(
            "marker_parent_is_goalpost",
            lambda evidence: evidence.get("parent_name") == PARENT_OBJECT,
        ),
    ])


def parent_marker_action(file_name: str) -> ActionSpec:
    return ActionSpec(
        tool="parent_object",
        arguments={
            "file_name": file_name,
            "child_name": MARKER_OBJECT,
            "parent_name": PARENT_OBJECT,
        },
        name="parent Atlas_Marker to Goal_Left_post",
    )


def parent_target_satisfied(evidence: Dict[str, Any]) -> bool:
    return parent_target_evaluator().evaluate(evidence).satisfied
