"""Task-specific contract for conditional Blender object renaming."""
from typing import Any, Dict

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition

TARGET_OBJECT = "Goal_Left_post"
TARGET_NAME = "Goal_Left_Post"


def object_rename_target_evaluator() -> TargetStateEvaluator:
    return TargetStateEvaluator([
        StateInvariant("target_name_exists", lambda evidence: TARGET_NAME in evidence.get("object_names", [])),
        StateInvariant("source_name_absent", lambda evidence: TARGET_OBJECT not in evidence.get("object_names", [])),
        StateInvariant(
            "no_name_conflict",
            lambda evidence: not (
                TARGET_OBJECT in evidence.get("object_names", [])
                and TARGET_NAME in evidence.get("object_names", [])
            ),
        ),
    ])


def rename_object_action(file_name: str) -> ActionSpec:
    return ActionSpec(
        tool="rename_object",
        arguments={"file_name": file_name, "object_name": TARGET_OBJECT, "new_name": TARGET_NAME},
        name="rename_object",
    )


def object_rename_task_definition(file_name: str) -> AtlasTaskDefinition:
    """Return the declarative task contract used by live object renaming."""
    return AtlasTaskDefinition(
        name="object_rename",
        evidence=(
            EvidenceRequest(
                "inspect_scene",
                {"file_name": file_name},
                "inspect_scene",
            ),
        ),
        actions=(rename_object_action(file_name),),
        evaluator=object_rename_target_evaluator(),
        allowed_action_tools={"rename_object"},
        allow_writes=True,
        verify_after_action=True,
        metadata={"domain": "blender", "operation": "rename"},
    )
