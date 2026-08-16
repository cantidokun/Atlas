import pytest

from action_plan import ActionSpec
from planning.future_generator import DeterministicFutureGenerator
from planning.target_state import StateInvariant, TargetStateEvaluator


def _generator():
    return DeterministicFutureGenerator(
        TargetStateEvaluator([StateInvariant("ready", lambda evidence: evidence["ready"] is True)])
    )


def _actions():
    return [
        ActionSpec("move_object", {"object_name": "A", "location": [1, 2, 3]}, "move A"),
        ActionSpec("move_object", {"object_name": "B", "location": [4, 5, 6]}, "move B"),
    ]


def test_already_satisfied_future_contains_no_writes():
    steps = _generator().generate(True, _actions())
    assert [step.phase for step in steps] == ["EVIDENCE", "TARGET", "SKIP_WRITES", "VERIFICATION", "COMPLETE"]
    assert all(step.action is None for step in steps)


def test_unsatisfied_future_preserves_authorized_action_order():
    steps = _generator().generate(False, _actions())
    assert [step.phase for step in steps] == ["EVIDENCE", "TARGET", "ACTION", "ACTION", "VERIFICATION", "COMPLETE"]
    assert steps[2].action["index"] == 0
    assert steps[3].action["index"] == 1
    assert steps[2].action["tool"] == "move_object"
    assert steps[3].action["tool"] == "move_object"


def test_future_step_ids_are_stable():
    generator = _generator()
    first = generator.snapshot(generator.generate(False, _actions()))
    second = generator.snapshot(generator.generate(False, _actions()))
    assert first == second
    assert [step["step_id"] for step in first] == [
        "evidence.authoritative",
        "target.evaluated",
        "action.0",
        "action.1",
        "verification.pending",
        "complete",
    ]


def test_future_generation_requires_resolved_boolean_target():
    with pytest.raises(ValueError):
        _generator().generate(None, _actions())
    with pytest.raises(TypeError):
        _generator().generate("false", _actions())


def test_future_generation_rejects_non_action_specs():
    with pytest.raises(TypeError):
        _generator().generate(False, [{"tool": "move_object"}])
