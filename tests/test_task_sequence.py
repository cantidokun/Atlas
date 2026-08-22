import pytest

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition
from planning.task_runtime import EvidenceReducer
from planning.task_sequence import TaskSequenceDefinition, TaskSequenceSession


def _task(name, tool, key, target):
    evidence = (EvidenceRequest("inspect_state", {"key": key}, "inspect state"),)
    action = ActionSpec(tool, {"key": key, "value": target}, f"set {key}")
    evaluator = TargetStateEvaluator([
        StateInvariant(f"{key}_target", lambda state, target=target: state.get("value") == target)
    ])
    return AtlasTaskDefinition(
        name=name,
        evidence=evidence,
        actions=(action,),
        evaluator=evaluator,
        allowed_action_tools=frozenset({tool}),
        allow_writes=True,
        verify_after_action=True,
    )


def test_sequence_runs_two_tasks_only_after_each_task_verifies():
    state = {"rotation": 0, "marker": 0}
    calls = []

    def execute(tool, arguments):
        calls.append((tool, dict(arguments)))
        key = arguments["key"]
        if tool == "inspect_state":
            return {"key": key, "value": state[key]}
        state[key] = arguments["value"]
        return {"status": "ok", "key": key, "value": state[key]}

    definition = TaskSequenceDefinition((
        _task("rotation", "set_rotation", "rotation", 90),
        _task("marker", "create_marker", "marker", 1),
    ))
    reducer: EvidenceReducer = lambda evidence: evidence[0]
    sequence = TaskSequenceSession(definition, execute, (reducer, reducer))

    checkpoint = sequence.run_current(authorization_id="seq:rotation")
    assert checkpoint["next_task_index"] == 1
    assert sequence.current_task.name == "marker"
    assert calls.count(("set_rotation", {"key": "rotation", "value": 90})) == 1
    assert state["rotation"] == 90

    sequence.run_current(authorization_id="seq:marker")
    assert sequence.complete
    assert state == {"rotation": 90, "marker": 1}


def test_sequence_resume_reconstructs_only_at_a_completed_task_boundary():
    state = {"first": 0, "second": 0}

    def execute(tool, arguments):
        key = arguments["key"]
        if tool == "inspect_state":
            return {"key": key, "value": state[key]}
        state[key] = arguments["value"]
        return {"status": "ok", "key": key, "value": state[key]}

    definition = TaskSequenceDefinition((
        _task("first", "set_first", "first", 1),
        _task("second", "set_second", "second", 2),
    ))
    reducer = lambda evidence: evidence[0]
    original = TaskSequenceSession(definition, execute, (reducer, reducer))
    checkpoint = original.run_current(authorization_id="seq:first")
    assert checkpoint["next_task_index"] == 1

    resumed = TaskSequenceSession.resume_from_checkpoint(
        definition, execute, (reducer, reducer), checkpoint
    )
    assert resumed.index == 1
    assert resumed.current_task.name == "second"
    resumed.run_current(authorization_id="seq:second")
    assert resumed.complete
    assert state == {"first": 1, "second": 2}

    tampered = dict(checkpoint)
    tampered["sequence"] = {"tasks": []}
    with pytest.raises(ValueError, match="does not match"):
        TaskSequenceSession.resume_from_checkpoint(
            definition, execute, (reducer, reducer), tampered
        )


def test_sequence_cannot_advance_before_current_task_is_complete():
    definition = TaskSequenceDefinition((_task("first", "set_first", "first", 1),))
    reducer = lambda evidence: evidence[0]
    sequence = TaskSequenceSession(definition, lambda tool, args: {"value": 0}, (reducer,))
    sequence.start_current()
    with pytest.raises(RuntimeError, match="before task completion"):
        sequence.advance_after_completion()
