import pytest

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition
from planning.task_runtime import prepare_task_runtime


def evaluator():
    return TargetStateEvaluator([StateInvariant("ready", lambda evidence: bool(evidence.get("ready")))])


def test_task_definition_requires_evidence_actions_and_authorized_tools():
    with pytest.raises(ValueError):
        AtlasTaskDefinition("", (), (), evaluator(), {"move_object"})
    with pytest.raises(ValueError):
        AtlasTaskDefinition("x", (EvidenceRequest("inspect_scene", {}, "inspect_scene"),), (), evaluator(), {"move_object"})
    with pytest.raises(ValueError):
        AtlasTaskDefinition(
            "x",
            (EvidenceRequest("inspect_scene", {}, "inspect_scene"),),
            (ActionSpec("create_collection", {}, "create_collection"),),
            evaluator(),
            {"move_object"},
        )


def test_write_task_requires_verification_at_runtime():
    task = AtlasTaskDefinition(
        "write",
        (EvidenceRequest("inspect_scene", {}, "inspect_scene"),),
        (ActionSpec("move_object", {}, "move_object"),),
        evaluator(),
        {"move_object"},
        allow_writes=True,
        verify_after_action=False,
    )

    with pytest.raises(ValueError, match="requires verification"):
        prepare_task_runtime(task)


def test_task_definition_authorization_surface_is_immutable_after_construction():
    allowed = {"move_object"}
    task = AtlasTaskDefinition(
        "immutable",
        (EvidenceRequest("inspect_scene", {}, "inspect_scene"),),
        (ActionSpec("move_object", {}, "move_object"),),
        evaluator(),
        allowed,
    )

    allowed.add("delete_object")

    assert task.allowed_action_tools == frozenset({"move_object"})
    with pytest.raises(AttributeError):
        task.allowed_action_tools.add("delete_object")


def test_task_definition_snapshot_is_serializable_and_task_specific():
    task = AtlasTaskDefinition(
        "marker",
        (EvidenceRequest("inspect_scene", {"file_name": "x.blend"}, "inspect_scene"),),
        (ActionSpec("create_empty_marker", {"file_name": "x.blend"}, "create_empty_marker"),),
        evaluator(),
        {"create_empty_marker"},
        allow_writes=True,
        metadata={"domain": "blender"},
    )
    snap = task.snapshot()
    assert snap["name"] == "marker"
    assert snap["allow_writes"] is True
    assert snap["verify_after_action"] is True
    assert snap["evidence"][0]["name"] == "inspect_scene"
    assert snap["actions"][0]["tool"] == "create_empty_marker"
    assert snap["actions"][0]["name"] == "create_empty_marker"
    assert snap["metadata"]["domain"] == "blender"
