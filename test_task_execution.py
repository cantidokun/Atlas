import pytest

from action_plan import ActionSpec
from task_execution import TaskExecutionError, TaskExecutionRuntime
from task_planner import TaskPlanProposal


def make_runtime():
    proposal = TaskPlanProposal(
        evidence=[],
        actions=[
            ActionSpec(tool="inspect", arguments={"id": 1}, name="Inspect"),
            ActionSpec(tool="write", arguments={"value": 2}, name="Write"),
        ],
    )
    return TaskExecutionRuntime(
        proposal,
        evidence_complete=True,
        allowed_action_tools={"inspect", "write"},
        allow_writes=True,
    )


def test_execution_requires_explicit_authorization():
    runtime = make_runtime()

    with pytest.raises(TaskExecutionError, match="not been authorized"):
        runtime.execute_next(lambda tool, args: {"success": True})


def test_runtime_executes_one_action_at_a_time_and_verifies():
    runtime = make_runtime()
    runtime.authorize()
    calls = []

    def executor(tool, arguments):
        calls.append((tool, arguments))
        return {"success": True, "tool": tool}

    first = runtime.execute_next(executor)
    assert first["tool"] == "inspect"
    assert runtime.action_plan.current_index == 1
    assert calls == [("inspect", {"id": 1})]

    second = runtime.execute_next(executor)
    assert second["tool"] == "write"
    assert runtime.action_plan.complete

    runtime.mark_verified({"success": True, "verified": "independently"})
    assert runtime.verification_complete
    assert runtime.final_result["verified"] == "independently"


def test_verification_requires_all_actions_to_complete():
    runtime = make_runtime()
    runtime.authorize()

    with pytest.raises(TaskExecutionError, match="before all actions complete"):
        runtime.mark_verified({"success": True})


def test_failed_action_blocks_runtime():
    runtime = make_runtime()
    runtime.authorize()

    with pytest.raises(TaskExecutionError, match="Action failed"):
        runtime.execute_next(lambda tool, args: {"success": False})

    assert runtime.action_plan.blocked
    assert runtime.snapshot()["verification_complete"] is False


def test_write_authorization_is_not_implicit():
    runtime = TaskExecutionRuntime(
        TaskPlanProposal(evidence=[], actions=[ActionSpec("write", {})]),
        evidence_complete=True,
        allowed_action_tools={"write"},
        allow_writes=False,
    )

    with pytest.raises(TaskExecutionError, match="Write authorization"):
        runtime.authorize()
