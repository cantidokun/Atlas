"""Regression tests for the Atlas Development Controller.

Coverage targets:
- Task file loading and validation (valid, missing keys, bad JSON, empty fields).
- Scope guard: file scope, command scope, git push/commit rejection.
- Aider command builder invariants (no-auto-commits, no-git, yes, message).
- Runner: successful run, aider failure, test failure, scope violation.
- Controller never includes git push or commit in any command.
- Fail-closed on every invalid input.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from atlas_dev_controller.task_schema import (
    AtlasTask,
    TaskValidationError,
    load_task,
)
from atlas_dev_controller.scope_guard import (
    ScopeViolationError,
    normalize_path,
    validate_command_scope,
    validate_file_scope,
)
from atlas_dev_controller.runner import (
    RunResult,
    build_aider_command,
    run_task,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _write_task_file(tmp_dir, data):
    path = os.path.join(tmp_dir, "task.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


def _valid_task_data(**overrides):
    defaults = {
        "task_id": "test-001",
        "message": "implement feature X",
        "allowed_files": ["planning/unreal_transport_contract.py"],
        "allowed_test_commands": [
            "python -m pytest tests/test_unreal_transport_contract.py -v"
        ],
    }
    defaults.update(overrides)
    return defaults


def _mock_executor(returncode=0, stdout="", stderr=""):
    """Return a callable that simulates subprocess.run."""
    def executor(cmd):
        result = subprocess.CompletedProcess(cmd, returncode, stdout, stderr)
        return result
    return executor


# ── Task schema validation ───────────────────────────────────────────────

class TestAtlasTask:
    def test_valid_construction(self):
        task = AtlasTask(
            task_id="t1",
            message="do something",
            allowed_files=["a.py"],
            allowed_test_commands=["python -m pytest tests/ -v"],
        )
        assert task.task_id == "t1"

    def test_empty_task_id_rejected(self):
        with pytest.raises(TaskValidationError, match="task_id"):
            AtlasTask(
                task_id="",
                message="msg",
                allowed_files=["a.py"],
                allowed_test_commands=["python -m pytest"],
            )

    def test_empty_message_rejected(self):
        with pytest.raises(TaskValidationError, match="message"):
            AtlasTask(
                task_id="t1",
                message="",
                allowed_files=["a.py"],
                allowed_test_commands=["python -m pytest"],
            )

    def test_empty_allowed_files_rejected(self):
        with pytest.raises(TaskValidationError, match="allowed_files"):
            AtlasTask(
                task_id="t1",
                message="msg",
                allowed_files=[],
                allowed_test_commands=["python -m pytest"],
            )

    def test_empty_test_commands_rejected(self):
        with pytest.raises(TaskValidationError, match="allowed_test_commands"):
            AtlasTask(
                task_id="t1",
                message="msg",
                allowed_files=["a.py"],
                allowed_test_commands=[],
            )

    def test_git_push_in_test_commands_rejected(self):
        with pytest.raises(TaskValidationError, match="git push"):
            AtlasTask(
                task_id="t1",
                message="msg",
                allowed_files=["a.py"],
                allowed_test_commands=["git push origin main"],
            )

    def test_git_commit_in_test_commands_rejected(self):
        with pytest.raises(TaskValidationError, match="git commit"):
            AtlasTask(
                task_id="t1",
                message="msg",
                allowed_files=["a.py"],
                allowed_test_commands=["git commit -m 'test'"],
            )

    def test_empty_string_in_allowed_files_rejected(self):
        with pytest.raises(TaskValidationError, match="allowed_files"):
            AtlasTask(
                task_id="t1",
                message="msg",
                allowed_files=["a.py", ""],
                allowed_test_commands=["python -m pytest"],
            )


# ── Task file loading ────────────────────────────────────────────────────

class TestLoadTask:
    def test_load_valid_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_task_file(tmp, _valid_task_data())
            task = load_task(path)
            assert task.task_id == "test-001"
            assert len(task.allowed_files) == 1

    def test_missing_file_rejected(self):
        with pytest.raises(TaskValidationError, match="does not exist"):
            load_task("/nonexistent/task.json")

    def test_invalid_json_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "task.json")
            with open(path, "w") as f:
                f.write("{bad json")
            with pytest.raises(TaskValidationError, match="not valid JSON"):
                load_task(path)

    def test_missing_keys_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_task_file(tmp, {"task_id": "t1"})
            with pytest.raises(TaskValidationError, match="missing required keys"):
                load_task(path)

    def test_non_object_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "task.json")
            with open(path, "w") as f:
                f.write("[]")
            with pytest.raises(TaskValidationError, match="JSON object"):
                load_task(path)

    def test_optional_model_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = _valid_task_data(model="claude-sonnet-4-20250514")
            path = _write_task_file(tmp, data)
            task = load_task(path)
            assert task.model == "claude-sonnet-4-20250514"


# ── Scope guard ──────────────────────────────────────────────────────────

class TestScopeGuard:
    def test_valid_file_scope(self):
        validate_file_scope(
            ["planning/a.py"],
            ["planning/a.py", "planning/b.py"],
        )

    def test_file_outside_scope_rejected(self):
        with pytest.raises(ScopeViolationError, match="outside the approved scope"):
            validate_file_scope(
                ["planning/a.py", "tools/blender.py"],
                ["planning/a.py"],
            )

    def test_path_normalization(self):
        assert normalize_path("planning\\a.py") == normalize_path("planning/a.py")

    def test_valid_command_scope(self):
        validate_command_scope(
            "python -m pytest tests/ -v",
            ["python -m pytest tests/ -v"],
        )

    def test_command_outside_scope_rejected(self):
        with pytest.raises(ScopeViolationError, match="not in the approved set"):
            validate_command_scope(
                "rm -rf /",
                ["python -m pytest tests/ -v"],
            )

    def test_git_push_always_rejected(self):
        with pytest.raises(ScopeViolationError, match="git push"):
            validate_command_scope(
                "git push origin main",
                ["git push origin main"],  # even if "approved"
            )

    def test_git_commit_always_rejected(self):
        with pytest.raises(ScopeViolationError, match="git commit"):
            validate_command_scope(
                "git commit -m test",
                ["git commit -m test"],  # even if "approved"
            )


# ── Aider command builder ────────────────────────────────────────────────

class TestBuildAiderCommand:
    def test_contains_no_auto_commits(self):
        task = AtlasTask(
            task_id="t1",
            message="msg",
            allowed_files=["a.py"],
            allowed_test_commands=["python -m pytest"],
        )
        cmd = build_aider_command(task)
        assert "--no-auto-commits" in cmd

    def test_contains_no_git(self):
        task = AtlasTask(
            task_id="t1",
            message="msg",
            allowed_files=["a.py"],
            allowed_test_commands=["python -m pytest"],
        )
        cmd = build_aider_command(task)
        assert "--no-git" in cmd

    def test_contains_yes(self):
        task = AtlasTask(
            task_id="t1",
            message="msg",
            allowed_files=["a.py"],
            allowed_test_commands=["python -m pytest"],
        )
        cmd = build_aider_command(task)
        assert "--yes" in cmd

    def test_contains_message(self):
        task = AtlasTask(
            task_id="t1",
            message="implement feature X",
            allowed_files=["a.py"],
            allowed_test_commands=["python -m pytest"],
        )
        cmd = build_aider_command(task)
        idx = cmd.index("--message")
        assert cmd[idx + 1] == "implement feature X"

    def test_contains_file_flags(self):
        task = AtlasTask(
            task_id="t1",
            message="msg",
            allowed_files=["a.py", "b.py"],
            allowed_test_commands=["python -m pytest"],
        )
        cmd = build_aider_command(task)
        file_indices = [i for i, v in enumerate(cmd) if v == "--file"]
        assert len(file_indices) == 2
        assert cmd[file_indices[0] + 1] == "a.py"
        assert cmd[file_indices[1] + 1] == "b.py"

    def test_never_contains_push(self):
        task = AtlasTask(
            task_id="t1",
            message="msg",
            allowed_files=["a.py"],
            allowed_test_commands=["python -m pytest"],
        )
        cmd = build_aider_command(task)
        joined = " ".join(cmd).lower()
        assert "push" not in joined

    def test_never_contains_commit_flag(self):
        task = AtlasTask(
            task_id="t1",
            message="msg",
            allowed_files=["a.py"],
            allowed_test_commands=["python -m pytest"],
        )
        cmd = build_aider_command(task)
        # --no-auto-commits is present but no bare --commit
        assert "--commit" not in cmd


# ── Runner integration ───────────────────────────────────────────────────

class TestRunner:
    def test_successful_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_task_file(tmp, _valid_task_data())
            result = run_task(path, execute_command=_mock_executor(0, "ok"))
            assert result.success is True
            assert result.task_id == "test-001"
            assert result.aider_exit_code == 0
            assert len(result.test_results) == 1
            assert result.test_results[0]["success"] is True
            assert result.log_path is not None

    def test_aider_failure_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_task_file(tmp, _valid_task_data())
            result = run_task(path, execute_command=_mock_executor(1, "", "error"))
            assert result.success is False
            assert result.aider_exit_code == 1
            assert "exit" in result.error.lower() or "code" in result.error.lower()

    def test_test_failure_fails_closed(self):
        call_count = [0]

        def alternating_executor(cmd):
            call_count[0] += 1
            if call_count[0] == 1:
                # Aider succeeds
                return subprocess.CompletedProcess(cmd, 0, "aider ok", "")
            else:
                # Test fails
                return subprocess.CompletedProcess(cmd, 1, "", "test failed")

        with tempfile.TemporaryDirectory() as tmp:
            path = _write_task_file(tmp, _valid_task_data())
            result = run_task(path, execute_command=alternating_executor)
            assert result.success is False
            assert result.aider_exit_code == 0
            assert len(result.test_results) == 1
            assert result.test_results[0]["success"] is False

    def test_invalid_task_file_fails_closed(self):
        result = run_task("/nonexistent/task.json", execute_command=_mock_executor())
        assert result.success is False
        assert result.task_id == "invalid"
        assert "does not exist" in result.error

    def test_log_file_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_task_file(tmp, _valid_task_data())
            result = run_task(path, execute_command=_mock_executor(0))
            assert result.log_path is not None
            assert Path(result.log_path).is_file()
            content = Path(result.log_path).read_text(encoding="utf-8")
            assert "test-001" in content
            assert "overall_success: True" in content

    def test_multiple_test_commands(self):
        data = _valid_task_data(
            allowed_test_commands=[
                "python -m pytest tests/test_a.py -v",
                "python -m pytest tests/test_b.py -v",
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_task_file(tmp, data)
            result = run_task(path, execute_command=_mock_executor(0))
            assert result.success is True
            assert len(result.test_results) == 2

    def test_second_test_failure_stops_execution(self):
        call_count = [0]

        def sequential_executor(cmd):
            call_count[0] += 1
            if call_count[0] <= 2:
                # Aider + first test succeed
                return subprocess.CompletedProcess(cmd, 0, "ok", "")
            else:
                # Second test fails
                return subprocess.CompletedProcess(cmd, 1, "", "fail")

        data = _valid_task_data(
            allowed_test_commands=[
                "python -m pytest tests/test_a.py -v",
                "python -m pytest tests/test_b.py -v",
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_task_file(tmp, data)
            result = run_task(path, execute_command=sequential_executor)
            assert result.success is False
            # Should have stopped after second test failure
            assert len(result.test_results) == 2
            assert result.test_results[0]["success"] is True
            assert result.test_results[1]["success"] is False
