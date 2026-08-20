"""Bounded subprocess client for local Aider model turns.

This module is deliberately narrower than a general command runner.  It
starts one configured Aider executable with a supplied message, captures its
output, and enforces a caller-provided deadline.  The controller remains the
owner of task state and authorization; this client is only the model-process
boundary.

Aider is run with automatic commits disabled by default.  The controller must
retain ownership of the repository's commit boundary rather than allowing a
model turn to silently create or rewrite Git history.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import subprocess
from typing import Callable, Mapping, Sequence


ProcessFactory = Callable[..., subprocess.Popen]


@dataclass(frozen=True)
class AiderTurnResult:
    """Result of one bounded Aider invocation."""

    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool


class AiderModelClient:
    """Run Aider as an explicitly configured, non-shell subprocess."""

    def __init__(
        self,
        *,
        executable: str = "aider",
        working_directory: str | Path,
        extra_args: Sequence[str] = (),
        environment: Mapping[str, str] | None = None,
        allow_auto_commits: bool = False,
        process_factory: ProcessFactory = subprocess.Popen,
    ) -> None:
        if not executable:
            raise ValueError("executable must be non-empty")
        if not isinstance(allow_auto_commits, bool):
            raise ValueError("allow_auto_commits must be a boolean")

        configured_args = tuple(extra_args)
        if not allow_auto_commits and any(
            arg in {"--auto-commits", "--dirty-commits"}
            for arg in configured_args
        ):
            raise ValueError(
                "Aider automatic commits are disabled by controller policy"
            )

        self._executable = executable
        self._working_directory = str(Path(working_directory))
        self._extra_args = configured_args
        self._environment = None if environment is None else dict(environment)
        self._allow_auto_commits = allow_auto_commits
        self._process_factory = process_factory

    def run_turn(self, message: str, timeout_seconds: float) -> AiderTurnResult:
        """Execute one Aider message without shell interpretation.

        ``--message`` makes each invocation a bounded model turn.  Additional
        Aider flags are supplied at construction time so policy is explicit at
        the host boundary rather than hidden inside the controller.
        """
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be a non-empty string")
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not math.isfinite(float(timeout_seconds))
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be a finite positive number")

        command = [self._executable, *self._extra_args]
        if not self._allow_auto_commits:
            command.extend(("--no-auto-commits", "--no-dirty-commits"))
        command.extend(("--message", message))
        process = self._process_factory(
            command,
            cwd=self._working_directory,
            env=self._environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
        )

        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=1.0)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()

            partial_stdout = _text_or_empty(exc.stdout)
            partial_stderr = _text_or_empty(exc.stderr)
            if partial_stdout and stdout:
                stdout = partial_stdout + stdout
            elif partial_stdout:
                stdout = partial_stdout
            if partial_stderr and stderr:
                stderr = partial_stderr + stderr
            elif partial_stderr:
                stderr = partial_stderr

            return AiderTurnResult(
                returncode=process.returncode,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
            )

        return AiderTurnResult(
            returncode=process.returncode,
            stdout=stdout,
            stderr=stderr,
            timed_out=False,
        )


def _text_or_empty(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value
