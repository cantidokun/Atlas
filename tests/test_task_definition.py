import pytest

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition


def evaluator():
    return TargetStateEvaluator([StateInvariant("ready", lambda evidence: bool(evidence.get("ready")))])


def test_task_definition_requires_evidence_actions_and_authorized_tools():
    with pytest.raises(ValueError):
        AtlasTaskDefinition("", (), (), evaluator(), {"move_object"})
    with pytest.raises(ValueError):
        AtlasTaskDefinition("x", (EvidenceRequest("inspect_scene", {}, "scene"),), (), evaluator(), {"move_object"})
    with pytest.raises(ValueError):
        AtlasTaskDefinition(
            "x",
            (EvidenceRequest("inspect_scene", {}, "scene"),),
            (ActionSpec("create_collection", {}, "create"),),
            evaluator(),
            {"move_object"},
        )


def test_write_task_requires_verification():
    with pytest.raises(ValueError):
        AtlasTaskDefinition(
            "write",
            (EvidenceRequest("inspect_scene", {}, "scene"),),
            (ActionSpec("move_object", {}, "move"),),
            evaluator(),
            {"move_object"},
            allow_writes=True,
            verify_after_action=False,
        )


def test_task_definition_snapshot_is_serializable_and_task_specific():
    task = AtlasTaskDefinition(
        "marker",
        (EvidenceRequest("inspect_scene", {"file_name": "x.blend"}, "scene"),),
        (ActionSpec("create_empty_marker", {"file_name": "x.blend"}, "marker"),),
        evaluator(),
        {"create_empty_marker"},
        allow_writes=True,
        metadata={"domain": "blender"},
    )
    snap = task.snapshot()
    assert snap["name"] == "marker"
    assert snap["allow_writes"] is True
    assert snap["verify_after_action"] is True
    assert snap["actions"][0]["tool"] == "create_empty_marker"
    assert snap["metadata"]["domain"] == "blender"
