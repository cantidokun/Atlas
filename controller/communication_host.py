"""Executable local host for the controller communication bridge.

The host is the final composition layer between the transport-neutral
controller runtime and a real local process.  It deliberately does not know
which production tool is being controlled: the local tool executor is supplied
as an explicit ``module:function`` import target.

A typical process topology is:

    remote controller client
            |
            | newline-delimited JSON
            v
    communication_host.py
       |             |
       v             v
    local tool      Aider
    executor        model process

The remote side never selects the executor module or executable.  Those are
local host configuration, and Aider is launched without shell interpretation.
The host also enforces a maximum model-turn duration so a remote request
cannot silently remove the stall protection demonstrated by the controller's
model supervision layer.

Aider automatic commits are disabled by default.  Repository history remains
a controller/developer concern, not a side effect of a remote model turn.
"""

from __future__ import annotations

import argparse
import importlib
from typing import Any, Callable, Sequence

from controller.communication_runtime import DEFAULT_MAX_MODEL_TURN_SECONDS
from controller.communication_stdio import run_aider_controller_stdio


ToolExecutor = Callable[[str, dict[str, Any]], dict[str, Any]]


def load_tool_executor(spec: str) -> ToolExecutor:
    """Load a local tool executor from ``module:function`` configuration."""
    if not isinstance(spec, str) or not spec.strip():
        raise ValueError("tool executor must be a non-empty module:function spec")

    module_name, separator, function_name = spec.partition(":")
    if not separator or not module_name or not function_name:
        raise ValueError("tool executor must use module:function syntax")

    module = importlib.import_module(module_name)
    executor = getattr(module, function_name, None)
    if not callable(executor):
        raise TypeError(f"tool executor is not callable: {spec}")
    return executor


def build_parser() -> argparse.ArgumentParser:
    """Build the standalone host command-line parser."""
    parser = argparse.ArgumentParser(
        description="Run the Atlas controller communication bridge over stdio."
    )
    parser.add_argument(
        "--working-directory",
        required=True,
        help="Local repository/workspace passed to Aider as its working directory.",
    )
    parser.add_argument(
        "--tool-executor",
        required=True,
        help="Local executor import target in module:function form.",
    )
    parser.add_argument(
        "--aider-executable",
        default="aider",
        help="Aider executable name or absolute path.",
    )
    parser.add_argument(
        "--aider-arg",
        action="append",
        default=[],
        help="Additional Aider argument. Repeat for multiple arguments.",
    )
    parser.add_argument(
        "--allow-aider-commits",
        action="store_true",
        help=(
            "Explicitly allow Aider to create automatic Git commits. "
            "Disabled by default so the controller retains commit ownership."
        ),
    )
    parser.add_argument(
        "--max-model-turn-seconds",
        type=float,
        default=DEFAULT_MAX_MODEL_TURN_SECONDS,
        help=(
            "Hard upper bound for any remote model turn in seconds. "
            f"Default: {DEFAULT_MAX_MODEL_TURN_SECONDS:g}."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Start the configured local controller host."""
    args = build_parser().parse_args(argv)
    execute_tool = load_tool_executor(args.tool_executor)

    run_aider_controller_stdio(
        execute_tool,
        args.working_directory,
        executable=args.aider_executable,
        extra_args=tuple(args.aider_arg),
        allow_aider_commits=args.allow_aider_commits,
        max_model_turn_seconds=args.max_model_turn_seconds,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by process startup
    raise SystemExit(main())
