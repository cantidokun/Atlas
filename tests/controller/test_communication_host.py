"""Offline tests for the standalone communication host."""

import sys
import types

import pytest

from controller import communication_host
from controller.communication_runtime import DEFAULT_MAX_MODEL_TURN_SECONDS


def test_load_tool_executor_imports_explicit_callable(monkeypatch):
    module = types.ModuleType("fake_tool_module")

    def execute(tool, arguments):
        return {"tool": tool, "arguments": arguments}

    module.execute = execute
    monkeypatch.setitem(sys.modules, "fake_tool_module", module)

    loaded = communication_host.load_tool_executor("fake_tool_module:execute")

    assert loaded is execute


def test_load_tool_executor_rejects_malformed_spec():
    with pytest.raises(ValueError, match="module:function"):
        communication_host.load_tool_executor("fake_tool_module")


def test_load_tool_executor_rejects_non_callable(monkeypatch):
    module = types.ModuleType("fake_tool_module")
    module.value = object()
    monkeypatch.setitem(sys.modules, "fake_tool_module", module)

    with pytest.raises(TypeError, match="not callable"):
        communication_host.load_tool_executor("fake_tool_module:value")


def test_parser_keeps_local_execution_configuration_explicit():
    args = communication_host.build_parser().parse_args(
        [
            "--working-directory",
            "C:/Atlas/controller",
            "--tool-executor",
            "host_tools:execute",
            "--aider-executable",
            "C:/Tools/aider.exe",
            "--aider-arg=--yes-always",
            "--aider-arg=--no-auto-commits",
            "--allow-aider-commits",
            "--max-model-turn-seconds=120",
        ]
    )

    assert args.working_directory == "C:/Atlas/controller"
    assert args.tool_executor == "host_tools:execute"
    assert args.aider_executable == "C:/Tools/aider.exe"
    assert args.aider_arg == ["--yes-always", "--no-auto-commits"]
    assert args.allow_aider_commits is True
    assert args.max_model_turn_seconds == 120.0


def test_parser_uses_safe_model_and_commit_defaults():
    args = communication_host.build_parser().parse_args(
        [
            "--working-directory",
            "C:/Atlas/controller",
            "--tool-executor",
            "host_tools:execute",
        ]
    )

    assert args.max_model_turn_seconds == DEFAULT_MAX_MODEL_TURN_SECONDS
    assert args.allow_aider_commits is False


def test_main_loads_executor_and_composes_safe_aider_host(monkeypatch):
    executor = lambda tool, arguments: {"tool": tool, "arguments": arguments}
    captured = {}

    monkeypatch.setattr(communication_host, "load_tool_executor", lambda spec: executor)

    def fake_run(execute_tool, working_directory, **kwargs):
        captured["execute_tool"] = execute_tool
        captured["working_directory"] = working_directory
        captured["kwargs"] = kwargs

    monkeypatch.setattr(communication_host, "run_aider_controller_stdio", fake_run)

    result = communication_host.main(
        [
            "--working-directory",
            "C:/Atlas/controller",
            "--tool-executor",
            "host_tools:execute",
            "--aider-executable",
            "aider.exe",
            "--aider-arg=--yes-always",
            "--max-model-turn-seconds=120",
        ]
    )

    assert result == 0
    assert captured["execute_tool"] is executor
    assert captured["working_directory"] == "C:/Atlas/controller"
    assert captured["kwargs"] == {
        "executable": "aider.exe",
        "extra_args": ("--yes-always",),
        "allow_aider_commits": False,
        "max_model_turn_seconds": 120.0,
    }
