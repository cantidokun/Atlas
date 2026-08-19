"""Task-specific contract for conditional Blender object rotation."""
from typing import Any, Dict

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition

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
        name="set_object_rotation",
    )


def object_rotation_task_definition(file_name: str) -> AtlasTaskDefinition:
    """Return the declarative task contract used by live object rotation."""
    return AtlasTaskDefinition(
        name="object_rotation",
        evidence=(
            EvidenceRequest(
                "inspect_object_transform",
                {"file_name": file_name, "object_name": TARGET_OBJECT},
                "inspect_object_transform",
            ),
        ),
        actions=(object_rotation_action(file_name),),
        evaluator=object_rotation_target_evaluator(),
        allowed_action_tools={"set_object_rotation"},
        allow_writes=True,
        verify_after_action=True,
        metadata={"domain": "blender", "operation": "rotation"},
    )
