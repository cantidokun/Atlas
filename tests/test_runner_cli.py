"""Focused CLI tests for atlas_dev_controller.runner.main()."""

import json
import os
import subprocess
import textwrap
from pathlib import Path
from typing import Optional
from unittest import mock

import pytest

from atlas_dev_controller.runner import RunResult, main, run_task


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_task(tmp_path: Path, overrides: Optional[dict] = None) -> str:
    """Write a minimal valid task JSON and return its path."""
    task = {
        "task_id": "cli-test-001",
        "message": "do nothing",
        "allowed_files": [],
        "allowed_test_commands": [],
        "model": "gpt-4",
    }
    if overrides:
        task.update(overrides)
    p = tmp_path / "task.json"
    p.write_text(json.dumps(task), encoding="utf-8")
    return str(p)


def _fake_run_task(result: RunResult):
    """Return a mock that replaces ``run_task`` with a canned result."""
    return mock.patch("atlas_dev_controller.runner.run_task", return_value=result)


# ---------------------------------------------------------------------------
# Usage / argument errors  (exit 2)
# ---------------------------------------------------------------------------

class TestCLIUsageErrors:
    def test_no_arguments_exits_2(self, capsys):
        """No positional arg → argparse exits with code 2."""
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 2

    def test_extra_arguments_exits_2(self, tmp_path):
        task_file = _write_task(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            main([task_file, "unexpected"])
        assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# File-not-found  (exit 1)
# ---------------------------------------------------------------------------

class TestCLIFileNotFound:
    def test_missing_file_exits_1(self, capsys):
        code = main(["nonexistent_task_file.json"])
        assert code == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err.lower()


# ---------------------------------------------------------------------------
# Successful run  (exit 0)
# ---------------------------------------------------------------------------

class TestCLISuccess:
    def test_successful_run_exits_0(self, tmp_path, capsys):
        task_file = _write_task(tmp_path)
        result = RunResult(
            task_id="cli-test-001",
            success=True,
            aider_exit_code=0,
            log_path="/fake/log.log",
        )
        with _fake_run_task(result):
            code = main([task_file])
        assert code == 0
        out = capsys.readouterr().out
        assert "success: True" in out
        assert "cli-test-001" in out

    def test_stdout_contains_log_path(self, tmp_path, capsys):
        task_file = _write_task(tmp_path)
        result = RunResult(
            task_id="t1", success=True, aider_exit_code=0, log_path="/x/y.log",
        )
        with _fake_run_task(result):
            main([task_file])
        assert "/x/y.log" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Failed run  (exit 1)
# ---------------------------------------------------------------------------

class TestCLIFailure:
    def test_failed_run_exits_1(self, tmp_path, capsys):
        task_file = _write_task(tmp_path)
        result = RunResult(
            task_id="cli-test-001",
            success=False,
            aider_exit_code=0,
            test_results=[{"command": "pytest tests/", "exit_code": 1, "success": False}],
            error="one or more test commands failed",
            log_path="/fake/log.log",
        )
        with _fake_run_task(result):
            code = main([task_file])
        assert code == 1
        captured = capsys.readouterr()
        assert "success: False" in captured.out
        assert "FAIL" in captured.out
        assert "one or more test commands failed" in captured.err

    def test_aider_failure_exits_1(self, tmp_path, capsys):
        task_file = _write_task(tmp_path)
        result = RunResult(
            task_id="cli-test-001",
            success=False,
            aider_exit_code=1,
            error="aider exited with code 1",
            log_path="/fake/log.log",
        )
        with _fake_run_task(result):
            code = main([task_file])
        assert code == 1
        captured = capsys.readouterr()
        assert "aider_exit_code: 1" in captured.out


# ---------------------------------------------------------------------------
# Module invocation smoke test
# ---------------------------------------------------------------------------

class TestModuleInvocation:
    def test_runner_module_flag(self):
        """``python -m atlas_dev_controller.runner --help`` exits 0."""
        proc = subprocess.run(
            ["python", "-m", "atlas_dev_controller.runner", "--help"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "task_file" in proc.stdout.lower()

    def test_package_module_flag(self):
        """``python -m atlas_dev_controller --help`` exits 0."""
        proc = subprocess.run(
            ["python", "-m", "atlas_dev_controller", "--help"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "task_file" in proc.stdout.lower()
