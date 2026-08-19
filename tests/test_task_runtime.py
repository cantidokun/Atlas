import pytest

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
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


def _invalid_runtime_definition(*, allow_writes, verify, action_tool="move_object"):
    """Build an intentionally invalid definition without invoking task invariants."""
    definition = object.__new__(AtlasTaskDefinition)
    evaluator = TargetStateEvaluator([StateInvariant("ready", lambda evidence: True)])
    object.__setattr__(definition, "name", "runtime-invalid")
    object.__setattr__(definition, "evidence", (EvidenceRequest("inspect_scene", {}, "scene"),))
    object.__setattr__(definition, "actions", (ActionSpec(action_tool, {}, action_tool),))
    object.__setattr__(definition, "evaluator", evaluator)
    object.__setattr__(definition, "allowed_action_tools", {"move_object"})
    object.__setattr__(definition, "allow_writes", allow_writes)
    object.__setattr__(definition, "verify_after_action", verify)
    object.__setattr__(definition, "metadata", None)
    return definition


def test_prepare_runtime_preserves_task_contract():
    runtime = prepare_task_runtime(task())
    assert runtime.evidence_plan.next_request.tool == "inspect_scene"
    assert runtime.conditional_plan.next_action is None
    assert runtime.next_phase() == "EVIDENCE"


def test_runtime_rejects_write_without_verification():
    definition = _invalid_runtime_definition(allow_writes=True, verify=False)
    assert validate_task_runtime(definition) == ("write-capable task requires verification",)
    with pytest.raises(ValueError, match="requires verification"):
        prepare_task_runtime(definition)


def test_runtime_rejects_unauthorized_action_tool():
    definition = _invalid_runtime_definition(allow_writes=False, verify=True, action_tool="delete_object")
    assert validate_task_runtime(definition)[0].startswith("unauthorized action tools")
    with pytest.raises(ValueError, match="unauthorized action tools"):
        prepare_task_runtime(definition)
