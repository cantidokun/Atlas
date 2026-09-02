"""Task-specific contract for conditional Blender object rotation."""
from typing import Any, Dict, List, Optional

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition

TARGET_OBJECT = "Atlas_Rotation_Candidate"
TARGET_ROTATION = [0.0, 0.0, 90.0]


def _rotation_matches(evidence: Dict[str, Any], target_rotation: List[float]) -> bool:
    actual = evidence.get("rotation_degrees")
    if not isinstance(actual, list) or len(actual) != 3:
        return False
    return all(abs(float(got) - wanted) <= 1e-4 for got, wanted in zip(actual, target_rotation))


def object_rotation_target_evaluator(
    target_object: str = TARGET_OBJECT,
    target_rotation: Optional[List[float]] = None,
) -> TargetStateEvaluator:
    rotation = list(TARGET_ROTATION if target_rotation is None else target_rotation)
    return TargetStateEvaluator([
        StateInvariant("target_object_exists", lambda evidence: evidence.get("object_name") == target_object),
        StateInvariant("target_rotation", lambda evidence: _rotation_matches(evidence, rotation)),
    ])


def object_rotation_action(
    file_name: str,
    target_object: str = TARGET_OBJECT,
    target_rotation: Optional[List[float]] = None,
) -> ActionSpec:
    rotation = list(TARGET_ROTATION if target_rotation is None else target_rotation)
    return ActionSpec(
        tool="set_object_rotation",
        arguments={"file_name": file_name, "object_name": target_object, "rotation_degrees": rotation},
        name="set_object_rotation",
    )


def object_rotation_task_definition(
    file_name: str,
    target_object: str = TARGET_OBJECT,
    target_rotation: Optional[List[float]] = None,
) -> AtlasTaskDefinition:
    """Return the declarative task contract used by live object rotation."""
    rotation = list(TARGET_ROTATION if target_rotation is None else target_rotation)
    return AtlasTaskDefinition(
        name="object_rotation",
        evidence=(
            EvidenceRequest(
                "inspect_object_transform",
                {"file_name": file_name, "object_name": target_object},
                "inspect_object_transform",
            ),
        ),
        actions=(object_rotation_action(file_name, target_object, rotation),),
        evaluator=object_rotation_target_evaluator(target_object, rotation),
        allowed_action_tools={"set_object_rotation"},
        allow_writes=True,
        verify_after_action=True,
        metadata={"domain": "blender", "operation": "rotation"},
    )
