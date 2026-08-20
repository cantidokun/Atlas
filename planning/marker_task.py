"""Declarative Blender task definition for conditionally creating the Atlas marker."""
from typing import Any, Dict

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition

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


def marker_task_definition(file_name: str) -> AtlasTaskDefinition:
    """Return the declarative task contract for marker creation."""
    return AtlasTaskDefinition(
        name="marker_creation",
        evidence=(
            EvidenceRequest(
                "inspect_scene",
                {"file_name": file_name},
                "inspect_scene",
            ),
        ),
        actions=(marker_create_action(file_name),),
        evaluator=marker_target_evaluator(),
        allowed_action_tools={"create_empty_marker"},
        allow_writes=True,
        verify_after_action=True,
        metadata={"domain": "blender", "operation": "marker_creation"},
    )


def marker_target_satisfied(scene: Dict[str, Any]) -> bool:
    return marker_target_evaluator().evaluate(scene).satisfied
