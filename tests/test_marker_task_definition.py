import pytest

from planning.marker_task import MARKER_COLLECTION, MARKER_OBJECT, marker_task_definition


def test_marker_task_definition_is_declarative_and_write_verified():
    task = marker_task_definition("marker.blend")
    assert task.name == "marker_creation"
    assert len(task.evidence) == 1
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
    task = marker_task_definition("marker.blend")
    assert task.evidence[0].tool == "inspect_scene"
    assert task.evidence[0].arguments == {"file_name": "marker.blend"}
    assert task.metadata == {"domain": "blender", "operation": "marker_creation"}


def test_marker_task_definition_runtime_rejects_no_verification():
    from planning.task_definition import AtlasTaskDefinition
    from planning.evidence_plan import EvidenceRequest
    from planning.task_runtime import prepare_task_runtime
    from planning.target_state import TargetStateEvaluator
    from action_plan import ActionSpec

    malformed = AtlasTaskDefinition(
        name="bad",
        evidence=(EvidenceRequest("inspect_scene", {"file_name": "x.blend"}, "inspect_scene"),),
        actions=(ActionSpec("create_empty_marker", {"file_name": "x.blend", "collection_name": "Atlas_Test", "object_name": "Atlas_Marker"}, "create Atlas_Marker"),),
        evaluator=TargetStateEvaluator([]),
        allowed_action_tools={"create_empty_marker"},
        allow_writes=False,
        verify_after_action=True,
    )
    assert prepare_task_runtime(malformed).next_phase() == "EVIDENCE"
