"""Conditional Blender object deletion for explicit cleanup candidates."""
from typing import Any, Dict

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition

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
        name="delete_object",
    )


def object_delete_task_definition(file_name: str) -> AtlasTaskDefinition:
    """Return the declarative task contract used by live object deletion."""
    return AtlasTaskDefinition(
        name="object_delete",
        evidence=(
            EvidenceRequest(
                "inspect_scene",
                {"file_name": file_name},
                "inspect_scene",
            ),
        ),
        actions=(object_delete_action(file_name),),
        evaluator=object_delete_target_evaluator(),
        allowed_action_tools={"delete_object"},
        allow_writes=True,
        verify_after_action=True,
        metadata={"domain": "blender", "operation": "delete"},
    )


def object_delete_target_satisfied(evidence: Dict[str, Any]) -> bool:
    return object_delete_target_evaluator().evaluate(evidence).satisfied
