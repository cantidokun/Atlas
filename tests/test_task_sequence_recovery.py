"""Recovery coverage for mutations that happen before a checkpoint."""

from planning.task_sequence import TaskSequenceDefinition, TaskSequenceSession
from planning.task_definition import AtlasTaskDefinition
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.evidence_plan import EvidenceRequest
from action_plan import ActionSpec


def _task(name="move", state_key="moved"):
    def reducer(evidence):
        return evidence[-1]

    return AtlasTaskDefinition(
        name=name,
        evidence=(EvidenceRequest("inspect", {}, "inspect"),),
        actions=(ActionSpec("move", {}, "move"),),
        evaluator=TargetStateEvaluator([
            StateInvariant(state_key, lambda evidence, key=state_key: evidence.get(key) is True),
        ]),
        allowed_action_tools={"move"},
        allow_writes=True,
        verify_after_action=True,
    ), reducer


def test_resume_after_mutation_before_checkpoint_does_not_repeat_write():
    task, reducer = _task()
    definition = TaskSequenceDefinition((task,))
    state = {"moved": False, "writes": 0, "crash": True}

    def execute(tool, arguments):
        if tool == "inspect":
            return {"moved": state["moved"]}
        state["moved"] = True
        state["writes"] += 1
        if state["crash"]:
            state["crash"] = False
            raise RuntimeError("simulated process interruption after mutation")
        return {"status": "moved"}

    session = TaskSequenceSession(definition, execute, (reducer,))
    try:
        session.run_current(authorization_id="recovery-test")
    except RuntimeError as exc:
        assert "interruption" in str(exc)

    checkpoint = TaskSequenceSession(definition, execute, (reducer,)).checkpoint()
    resumed = TaskSequenceSession.resume_from_checkpoint(definition, execute, (reducer,), checkpoint)
    resumed.recover_current()

    assert state["writes"] == 1
    assert resumed.complete is True


def test_second_task_failure_recovers_from_last_completed_boundary_without_duplicate_write():
    first, first_reducer = _task("move", "moved")
    second, second_reducer = _task("marker", "marked")
    definition = TaskSequenceDefinition((first, second))
    state = {"moved": False, "marked": False, "writes": 0, "crash_marker": True}

    def execute(tool, arguments):
        if tool == "inspect":
            return {"moved": state["moved"], "marked": state["marked"]}
        state["writes"] += 1
        if state["writes"] == 1:
            state["moved"] = True
            return {"status": "mutated"}
        state["marked"] = True
        if state["crash_marker"]:
            state["crash_marker"] = False
            raise RuntimeError("simulated second-task interruption after mutation")
        return {"status": "mutated"}

    session = TaskSequenceSession(definition, execute, (first_reducer, second_reducer))
    first_checkpoint = session.run_current(authorization_id="first-task")
    resumed = TaskSequenceSession.resume_from_checkpoint(
        definition, execute, (first_reducer, second_reducer), first_checkpoint
    )
    try:
        resumed.run_current(authorization_id="second-task")
    except RuntimeError as exc:
        assert "second-task interruption" in str(exc)

    recovered = TaskSequenceSession.resume_from_checkpoint(
        definition, execute, (first_reducer, second_reducer), first_checkpoint
    )
    recovered.index = 1
    recovered.recover_current()

    assert state["writes"] == 2
    assert state["marked"] is True
    assert recovered.complete is True
