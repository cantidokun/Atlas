"""Offline tests for the autonomous controller core."""

import pytest

from controller.autonomous_runtime import (
    AutonomousController,
    ControllerPolicy,
    ModelTurn,
    ToolCall,
)


READ_ONLY = {"inspect"}
WRITES = {"modify"}


def make_controller(**overrides):
    values = {
        "read_only_tools": READ_ONLY,
        "write_tools": WRITES,
        "authorized_write_tools": {"modify"},
    }
    values.update(overrides)
    return AutonomousController(ControllerPolicy(**values))


def test_controller_owns_entire_model_tool_loop():
    controller = make_controller()
    calls = []
    turns = iter(
        [
            ModelTurn(tool_calls=(ToolCall("inspect", {"target": "scene"}, "1"),)),
            ModelTurn(tool_calls=(ToolCall("modify", {"target": "scene"}, "2"),)),
            ModelTurn(content="finished", done=True),
        ]
    )

    result = controller.run(
        [{"role": "user", "content": "task"}],
        lambda messages: next(turns),
        lambda name, arguments: calls.append((name, arguments)) or {"ok": True},
    )

    assert result.status == "complete"
    assert calls == [
        ("inspect", {"target": "scene"}),
        ("modify", {"target": "scene"}),
    ]
    assert result.turns == 3


def test_write_requires_python_authorization():
    controller = make_controller(authorized_write_tools=set())

    result = controller.run(
        [{"role": "user", "content": "task"}],
        lambda messages: ModelTurn(
            tool_calls=(ToolCall("modify", {"target": "scene"}),)
        ),
        lambda name, arguments: pytest.fail("write executor must not be reached"),
    )

    assert result.status == "blocked"
    assert result.reason == "write_not_authorized"


def test_unknown_tool_fails_closed():
    controller = make_controller()

    result = controller.run(
        [{"role": "user", "content": "task"}],
        lambda messages: ModelTurn(
            tool_calls=(ToolCall("delete_everything", {}),)
        ),
        lambda name, arguments: pytest.fail("unknown tool must not execute"),
    )

    assert result.status == "blocked"
    assert result.reason == "tool_not_authorized"


def test_multiple_tool_calls_fail_closed():
    controller = make_controller()

    result = controller.run(
        [{"role": "user", "content": "task"}],
        lambda messages: ModelTurn(
            tool_calls=(
                ToolCall("inspect", {}),
                ToolCall("inspect", {"target": "other"}),
            )
        ),
        lambda name, arguments: pytest.fail("multiple calls must not execute"),
    )

    assert result.status == "blocked"
    assert result.reason == "multiple_tool_calls_not_permitted"


def test_repeated_identical_call_has_a_finite_failure_boundary():
    controller = make_controller(max_identical_tool_calls=1)

    def ask(messages):
        return ModelTurn(tool_calls=(ToolCall("inspect", {"target": "scene"}),))

    executions = []
    result = controller.run(
        [{"role": "user", "content": "task"}],
        ask,
        lambda name, arguments: executions.append(arguments) or {"ok": True},
    )

    assert result.status == "blocked"
    assert result.reason == "repeated_identical_tool_call"
    assert len(executions) == 1


def test_model_failure_blocks_without_executing_a_tool():
    controller = make_controller()

    result = controller.run(
        [{"role": "user", "content": "task"}],
        lambda messages: (_ for _ in ()).throw(TimeoutError("stuck thinking")),
        lambda name, arguments: pytest.fail("tool must not execute after model failure"),
    )

    assert result.status == "blocked"
    assert result.reason == "model_call_failed: TimeoutError"


def test_tool_failure_blocks_and_preserves_history():
    controller = make_controller()

    result = controller.run(
        [{"role": "user", "content": "task"}],
        lambda messages: ModelTurn(
            tool_calls=(ToolCall("modify", {"target": "scene"}, "1"),)
        ),
        lambda name, arguments: (_ for _ in ()).throw(RuntimeError("executor down")),
    )

    assert result.status == "blocked"
    assert result.reason == "tool_execution_failed: RuntimeError"
    assert result.tool_history == []
