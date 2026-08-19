import pytest

from action_plan import ActionSpec
from evidence_plan import EvidenceRequest
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition


def make_task():
    return AtlasTaskDefinition(
        "immutable",
        (EvidenceRequest("inspect_scene", {"file_name": "x.blend"}, "scene"),),
        (ActionSpec("move_object", {"object_name": "x", "location": [0, 0, 0]}, "move"),),
        TargetStateEvaluator([StateInvariant("ready", lambda evidence: True)]),
        {"move_object"},
        allow_writes=True,
        metadata={"nested": {"mode": "safe"}},
    )


def test_task_definition_is_frozen_at_top_level():
    task = make_task()
    with pytest.raises((AttributeError, TypeError)):
        task.name = "changed"


def test_snapshot_is_independent_of_mutable_metadata():
    task = make_task()
    snapshot = task.snapshot()
    snapshot["metadata"]["nested"]["mode"] = "changed"
    assert task.metadata["nested"]["mode"] == "safe"


def test_snapshot_is_independent_of_action_and_evidence_arguments():
    task = make_task()
    snapshot = task.snapshot()
    snapshot["actions"][0]["arguments"]["location"][0] = 99
    snapshot["evidence"][0]["arguments"]["file_name"] = "changed.blend"
    assert task.actions[0].arguments["location"][0] == 0
    assert task.evidence[0].arguments["file_name"] == "x.blend"
