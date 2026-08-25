import pytest

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.marker_task import MARKER_COLLECTION, MARKER_OBJECT, marker_task_definition
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition
from planning.task_runtime import prepare_task_runtime


def test_marker_task_definition_is_declarative_and_write_verified():
    task = marker_task_definition("marker.blend")
    assert task.name == "marker_creation"
    assert len(task.evidence) == 2
    assert len(task.actions) == 1
    assert task.allowed_action_tools == {"create_empty_marker"}
    assert task.allow_writes is True
    assert task.verify_after_action is True
    assert task.actions[0].tool == "create_empty_marker"
    assert task.actions[0].arguments == {
        "file_name": "marker.blend",
        "collection_name": MARKER_COLLECTION,
        "object_name": MARKER_OBJECT,
    }


def test_marker_task_definition_carries_only_task_specific_data():
    assert marker_task_definition("marker.blend").evidence[0].tool == "inspect_scene"
    assert marker_task_definition("marker.blend").evidence[0].arguments == {"file_name": "marker.blend"}
    assert marker_task_definition("marker.blend").evidence[1].tool == "inspect_object_collections"
    assert marker_task_definition("marker.blend").evidence[1].arguments == {
        "file_name": "marker.blend",
        "object_name": MARKER_OBJECT,
    }
    assert marker_task_definition("marker.blend").metadata == {"domain": "blender", "operation": "marker_creation"}


def test_marker_task_definition_runtime_rejects_write_without_verification():
    malformed = AtlasTaskDefinition(
        name="bad",
        evidence=(
            EvidenceRequest(
                "inspect_scene",
                {"file_name": "x.blend"},
                "inspect_scene",
            ),
        ),
        actions=(
            ActionSpec(
                "create_empty_marker",
                {
                    "file_name": "x.blend",
                    "collection_name": MARKER_COLLECTION,
                    "object_name": MARKER_OBJECT,
                },
                "create Atlas_Marker",
            ),
        ),
        evaluator=TargetStateEvaluator([
            StateInvariant("marker_exists", lambda evidence: True),
        ]),
        allowed_action_tools={"create_empty_marker"},
        allow_writes=True,
        verify_after_action=False,
    )

    with pytest.raises(ValueError, match="requires verification"):
        prepare_task_runtime(malformed)
