from action_plan import ActionSpec
from planning.continuation_resume import ContinuationState
from planning.resumable_corrective_task import ResumableCorrectiveTask


def _action(value):
    return ActionSpec(tool="set_value", arguments={"value": value})


def test_resume_fails_closed_before_executor_on_stale_evidence():
    state = {"value": 1}
    calls = []
    checkpoint = ContinuationState.create("task:resume", [_action(1)], dict(state), "auth:resume")

    task = ResumableCorrectiveTask(
        checkpoint,
        lambda: dict(state),
        lambda evidence: [_action(2)],
        "auth:resume",
        executor=lambda tool, arguments: calls.append((tool, arguments)) or {"ok": True, "state": "applied", "details": arguments},
    )

    try:
        task.resume(max_steps=1)
    except RuntimeError as exc:
        assert "fresh evidence" in str(exc)
    else:
        raise AssertionError("resume accepted stale evidence")
    assert calls == []


def test_resume_reenters_corrective_runtime_from_fresh_evidence():
    state = {"value": 1}
    calls = []
    checkpoint = ContinuationState.create("task:resume", [_action(1)], dict(state), "auth:resume")

    def observe():
        return dict(state)

    def plan(evidence):
        return [] if evidence["value"] == 2 else [_action(2)]

    def execute(tool, arguments):
        calls.append((tool, arguments))
        state.update(arguments)
        return {"ok": True, "state": "applied", "details": arguments}

    state["value"] = 9
    task = ResumableCorrectiveTask(checkpoint, observe, plan, "auth:resume", executor=execute)
    result = task.resume(max_steps=1)

    assert result.converged is True
    assert len(calls) == 1
    assert calls[0][0] == "set_value"
    assert state["value"] == 2
