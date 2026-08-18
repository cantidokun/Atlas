import pytest

from action_plan import ActionSpec
from evidence_plan import EvidenceRequest
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition
from planning.task_runtime import prepare_task_runtime, validate_task_runtime


def task(allow_writes=True, verify=True):
    evaluator = TargetStateEvaluator([StateInvariant("ready", lambda evidence: bool(evidence.get("ready")))])
    return AtlasTaskDefinition(
        "runtime-test",
        (EvidenceRequest("inspect_scene", {"file_name": "x.blend"}, "scene"),),
        (ActionSpec("move_object", {"file_name": "x.blend"}, "move"),),
        evaluator,
        {"move_object"},
        allow_writes=allow_writes,
        verify_after_action=verify,
    )


def test_prepare_runtime_preserves_task_contract():
    runtime = prepare_task_runtime(task())
    assert runtime.evidence_plan.next_request.tool == "inspect_scene"
    assert runtime.conditional_plan.next_action.tool == "move_object"
    assert runtime.next_phase() == "EVIDENCE"


def test_runtime_rejects_write_without_verification():
    definition = task(allow_writes=True, verify=False)
    assert validate_task_runtime(definition) == ("write-capable task requires verification",)
    with pytest.raises(ValueError, match="requires verification"):
        prepare_task_runtime(definition)


def test_runtime_rejects_unauthorized_action_tool():
    definition = AtlasTaskDefinition(
        "bad",
        (EvidenceRequest("inspect_scene", {}, "scene"),),
        (ActionSpec("delete_object", {}, "delete"),),
        task().evaluator,
        {"move_object"},
    )
    assert validate_task_runtime(definition)[0].startswith("unauthorized action tools")
    with pytest.raises(ValueError, match="unauthorized action tools"):
        prepare_task_runtime(definition)
