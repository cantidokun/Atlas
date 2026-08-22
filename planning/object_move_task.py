"""Declarative contract for conditional Blender object movement."""
from typing import Any, Dict

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition

TARGET_OBJECT = "Goal_Left_post"
TARGET_LOCATION = [1.0, 2.0, 0.0]


def _location_matches(evidence: Dict[str, Any]) -> bool:
    actual = evidence.get("location")
    if not isinstance(actual, list) or len(actual) != 3:
        return False
    return all(abs(float(got) - wanted) <= 1e-4 for got, wanted in zip(actual, TARGET_LOCATION))


def object_move_target_evaluator() -> TargetStateEvaluator:
    return TargetStateEvaluator([
        StateInvariant("target_object_exists", lambda evidence: evidence.get("object_name") == TARGET_OBJECT),
        StateInvariant("target_location", _location_matches),
    ])


def object_move_action(file_name: str) -> ActionSpec:
    return ActionSpec(
        tool="move_object",
        arguments={"file_name": file_name, "object_name": TARGET_OBJECT, "location": list(TARGET_LOCATION)},
        name="move_object",
    )


def object_move_task_definition(file_name: str) -> AtlasTaskDefinition:
    return AtlasTaskDefinition(
        name="object_move",
        evidence=(
            EvidenceRequest(
                "inspect_object_transform",
                {"file_name": file_name, "object_name": TARGET_OBJECT},
                "inspect_object_transform",
            ),
        ),
        actions=(object_move_action(file_name),),
        evaluator=object_move_target_evaluator(),
        allowed_action_tools={"move_object"},
        allow_writes=True,
        verify_after_action=True,
        metadata={"domain": "blender", "operation": "movement"},
    )
