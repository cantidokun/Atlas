"""Atlas Development Controller — non-interactive Aider runner.

This module orchestrates a single controlled Aider run:
1. Load and validate the task file.
2. Validate file scope.
3. Build the Aider command (non-interactive, no commits, no git).
4. Execute Aider.
5. Execute approved test commands.
6. Log the complete run.
7. Fail closed on any error.

The controller NEVER commits or pushes.
"""

import datetime
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from atlas_dev_controller.scope_guard import (
    ScopeViolationError,
    validate_command_scope,
    validate_file_scope,
    validate_post_aider_scope,
)
from atlas_dev_controller.task_schema import AtlasTask, TaskValidationError, load_task


class ControllerError(RuntimeError):
    """Raised when the controller cannot complete a run."""


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry-point for ``python -m atlas_dev_controller.runner TASK_FILE``.

    Returns
    -------
    int
        0 on success, 1 on task failure, 2 on usage error.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="atlas_dev_controller.runner",
        description="Run a single Atlas development task through the controller.",
    )
    parser.add_argument("task_file", help="Path to the JSON task file.")
    args = parser.parse_args(argv)

    task_file: str = args.task_file
    if not os.path.isfile(task_file):
        print(f"ERROR: task file not found: {task_file}", file=sys.stderr)
        return 1

    result = run_task(task_file)

    # Summary on stdout
    print(f"task_id: {result.task_id}")
    print(f"success: {result.success}")
    if result.aider_exit_code is not None:
        print(f"aider_exit_code: {result.aider_exit_code}")
    if result.test_results:
        for tr in result.test_results:
            status = "PASS" if tr.get("success") else "FAIL"
            print(f"  test {status}: {tr.get('command')}")
    if result.error:
        print(f"error: {result.error}", file=sys.stderr)
    if result.log_path:
        print(f"log: {result.log_path}")

    return 0 if result.success else 1


@dataclass
class RunResult:
    """Immutable record of one controller run."""

    task_id: str
    success: bool
    aider_exit_code: Optional[int] = None
    test_results: List[Dict[str, object]] = field(default_factory=list)
    error: Optional[str] = None
    log_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Executable resolution
# ---------------------------------------------------------------------------

def resolve_aider_executable() -> str:
    """Return the absolute path to the installed ``aider`` CLI executable.

    Resolution order:
    1. ``shutil.which("aider")`` — finds the executable on ``PATH``.
    2. Fall back to ``<sys.prefix>/Scripts/aider.exe`` (Windows venv) or
       ``<sys.prefix>/bin/aider`` (Unix venv).

    Raises
    ------
    ControllerError
        If the executable cannot be located.  The controller fails closed.
    """
    found = shutil.which("aider")
    if found is not None:
        return os.path.abspath(found)

    # Deterministic venv fallback
    if sys.platform == "win32":
        candidate = os.path.join(sys.prefix, "Scripts", "aider.exe")
    else:
        candidate = os.path.join(sys.prefix, "bin", "aider")

    if os.path.isfile(candidate):
        return os.path.abspath(candidate)

    raise ControllerError(
        f"Cannot locate the 'aider' executable on PATH or in the active "
        f"environment ({sys.prefix}).  Install aider-chat and ensure the "
        f"'aider' entry-point is available."
    )


# ---------------------------------------------------------------------------
# Command builder
# ---------------------------------------------------------------------------

def build_aider_command(task: AtlasTask) -> List[str]:
    """Build the Aider CLI invocation for a validated task.

    Invariants enforced:
    - Uses the installed ``aider`` CLI executable (never ``python -m``).
    - ``--no-auto-commits`` — Aider never commits.
    - ``--no-git`` — Aider does not interact with git.
    - ``--yes`` — non-interactive, no user prompts.
    - ``--message`` — the task prompt, not stdin.
    - Only approved files are passed.

    Raises
    ------
    ControllerError
        If the ``aider`` executable cannot be resolved.
    """
    aider_exe = resolve_aider_executable()
    cmd = [
        aider_exe,
        "--no-auto-commits",
        "--no-git",
        "--yes",
        "--model", task.model,
        "--message", task.message,
    ]
    for f in task.allowed_files:
        cmd.extend(["--file", f])
    return cmd


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

def _log_dir() -> Path:
    d = Path("atlas_dev_controller_logs")
    d.mkdir(exist_ok=True)
    return d


def _write_log(task_id: str, lines: List[str]) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = _log_dir() / f"run_{task_id}_{ts}.log"
    log_path.write_text("\n".join(lines), encoding="utf-8")
    return str(log_path)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_task(
    task_path: str,
    *,
    execute_command: Optional[Callable[[List[str]], subprocess.CompletedProcess]] = None,
) -> RunResult:
    """Execute one controlled development task.

    Parameters
    ----------
    task_path : str
        Path to the JSON task file.
    execute_command : callable, optional
        Injected command executor for testing. Defaults to ``subprocess.run``.

    Returns
    -------
    RunResult
        Complete record of the run, including success/failure and log path.
    """
    log_lines: List[str] = []
    log_lines.append(f"=== Atlas Dev Controller Run ===")
    log_lines.append(f"timestamp: {datetime.datetime.now().isoformat()}")
    log_lines.append(f"task_file: {task_path}")

    if execute_command is None:
        def execute_command(cmd):
            return subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    # 1. Load task
    try:
        task = load_task(task_path)
    except TaskValidationError as exc:
        log_lines.append(f"FAIL: task validation: {exc}")
        log_path = _write_log("invalid", log_lines)
        return RunResult(task_id="invalid", success=False, error=str(exc), log_path=log_path)

    log_lines.append(f"task_id: {task.task_id}")
    log_lines.append(f"allowed_files: {task.allowed_files}")
    log_lines.append(f"allowed_test_commands: {task.allowed_test_commands}")
    log_lines.append(f"model: {task.model}")

    # 2. Validate file scope
    try:
        validate_file_scope(task.allowed_files, task.allowed_files)
    except ScopeViolationError as exc:
        log_lines.append(f"FAIL: scope validation: {exc}")
        log_path = _write_log(task.task_id, log_lines)
        return RunResult(task_id=task.task_id, success=False, error=str(exc), log_path=log_path)

    # 3. Build and execute Aider
    aider_cmd = build_aider_command(task)
    log_lines.append(f"aider_command: {aider_cmd}")

    try:
        aider_result = execute_command(aider_cmd)
        aider_exit = aider_result.returncode
        log_lines.append(f"aider_exit_code: {aider_exit}")
        if aider_result.stdout:
            log_lines.append(f"aider_stdout:\n{aider_result.stdout}")
        if aider_result.stderr:
            log_lines.append(f"aider_stderr:\n{aider_result.stderr}")
    except Exception as exc:
        log_lines.append(f"FAIL: aider execution: {exc}")
        log_path = _write_log(task.task_id, log_lines)
        return RunResult(task_id=task.task_id, success=False, error=str(exc), log_path=log_path)

    if aider_exit != 0:
        log_lines.append("FAIL: aider returned non-zero exit code")
        log_path = _write_log(task.task_id, log_lines)
        return RunResult(
            task_id=task.task_id, success=False,
            aider_exit_code=aider_exit,
            error=f"aider exited with code {aider_exit}",
            log_path=log_path,
        )

    # 3b. Validate post-Aider file scope against actual working-tree changes
    try:
        changed_files = validate_post_aider_scope(task.allowed_files)
        if changed_files:
            log_lines.append(f"post_aider_changed_files: {changed_files}")
        else:
            log_lines.append("post_aider_changed_files: none detected")
    except ScopeViolationError as exc:
        log_lines.append(f"FAIL: post-aider scope violation: {exc}")
        log_path = _write_log(task.task_id, log_lines)
        return RunResult(
            task_id=task.task_id, success=False,
            aider_exit_code=aider_exit,
            error=str(exc),
            log_path=log_path,
        )

    # 4. Execute approved test commands
    test_results = []
    all_tests_passed = True

    for test_cmd_str in task.allowed_test_commands:
        try:
            validate_command_scope(test_cmd_str, task.allowed_test_commands)
        except ScopeViolationError as exc:
            log_lines.append(f"FAIL: command scope: {exc}")
            log_path = _write_log(task.task_id, log_lines)
            return RunResult(
                task_id=task.task_id, success=False,
                aider_exit_code=aider_exit,
                test_results=test_results,
                error=str(exc),
                log_path=log_path,
            )

        # Split for subprocess
        cmd_parts = test_cmd_str.split()
        log_lines.append(f"test_command: {test_cmd_str}")

        try:
            test_result = execute_command(cmd_parts)
            test_exit = test_result.returncode
            log_lines.append(f"test_exit_code: {test_exit}")
            if test_result.stdout:
                log_lines.append(f"test_stdout:\n{test_result.stdout}")
            if test_result.stderr:
                log_lines.append(f"test_stderr:\n{test_result.stderr}")
            entry = {
                "command": test_cmd_str,
                "exit_code": test_exit,
                "success": test_exit == 0,
            }
            test_results.append(entry)
            if test_exit != 0:
                all_tests_passed = False
                log_lines.append(f"FAIL: test command failed: {test_cmd_str}")
                # Fail closed — stop on first failure
                break
        except Exception as exc:
            log_lines.append(f"FAIL: test execution: {exc}")
            test_results.append({
                "command": test_cmd_str,
                "exit_code": None,
                "success": False,
                "error": str(exc),
            })
            all_tests_passed = False
            break

    success = aider_exit == 0 and all_tests_passed
    log_lines.append(f"overall_success: {success}")
    log_path = _write_log(task.task_id, log_lines)

    return RunResult(
        task_id=task.task_id,
        success=success,
        aider_exit_code=aider_exit,
        test_results=test_results,
        log_path=log_path,
        error=None if success else "one or more test commands failed",
    )


if __name__ == "__main__":
    sys.exit(main())
