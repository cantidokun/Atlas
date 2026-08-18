"""End-to-end test for the Atlas Development Controller.

Uses a temporary Git repository and fake executables to prove the full
controller lifecycle without touching real Aider, real tests, or any
existing Atlas/Unreal/Blender files.

Coverage targets:
- Task loading from a real JSON file.
- Fake Aider execution via the controller's command runner.
- Post-Aider scope enforcement against real Git working-tree changes.
- Approved test command execution.
- Success detection and log production.
- Fail-closed when fake Aider creates an out-of-scope file.
- read_only_files passed to Aider via --read.
- --no-gitignore present, --no-git absent (Git stays available).
- Overlap between read_only_files and allowed_files is rejected.
- read_only_files is optional for backward compatibility.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from atlas_dev_controller.runner import build_aider_command, run_task
from atlas_dev_controller.task_schema import AtlasTask, TaskValidationError


# ── Helpers ──────────────────────────────────────────────────────────────

def _init_git_repo(repo_dir):
    """Initialize a git repo with a committed allowed file."""
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "e2e@test.com"],
        cwd=repo_dir, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "E2E"],
        cwd=repo_dir, capture_output=True, check=True,
    )
    # Create the allowed file and commit it
    planning = Path(repo_dir) / "planning"
    planning.mkdir()
    allowed = planning / "target_module.py"
    allowed.write_text("# original\n", encoding="utf-8")
    # Create a trivial test script and commit it
    tests_dir = Path(repo_dir) / "tests"
    tests_dir.mkdir()
    test_script = tests_dir / "check_target.py"
    test_script.write_text(
        'import sys, pathlib\n'
        'target = pathlib.Path("planning/target_module.py")\n'
        'sys.exit(0 if "fake aider" in target.read_text() else 1)\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo_dir, capture_output=True, check=True,
    )


def _write_task(repo_dir, task_data):
    """Write and commit a task.json so it is not an untracked change."""
    task_path = Path(repo_dir) / "task.json"
    task_path.write_text(json.dumps(task_data), encoding="utf-8")
    subprocess.run(["git", "add", "task.json"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "add task"],
        cwd=repo_dir, capture_output=True, check=True,
    )
    return str(task_path)


def _fake_aider_script(repo_dir, target_relpath, *, rogue_path=None):
    """Write a Python script that simulates Aider editing files.

    If ``rogue_path`` is given, the script also creates that out-of-scope file.
    """
    script = Path(repo_dir) / "_fake_aider.py"
    lines = [
        "import pathlib, sys",
        f'target = pathlib.Path(r"{repo_dir}") / r"{target_relpath}"',
        'target.write_text("# fake aider was here\\n", encoding="utf-8")',
    ]
    if rogue_path:
        lines.append(
            f'rogue = pathlib.Path(r"{repo_dir}") / r"{rogue_path}"'
        )
        lines.append("rogue.parent.mkdir(parents=True, exist_ok=True)")
        lines.append('rogue.write_text("rogue\\n", encoding="utf-8")')
    lines.append("sys.exit(0)")
    script.write_text("\n".join(lines), encoding="utf-8")
    # Commit the script so it is not detected as an untracked change
    subprocess.run(["git", "add", "_fake_aider.py"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "add fake aider"],
        cwd=repo_dir, capture_output=True, check=True,
    )
    return str(script)


def _make_executor(repo_dir, fake_aider_script):
    """Return a command executor that replaces the Aider invocation with
    the fake script and runs test commands inside the temp repo."""
    call_count = [0]

    def executor(cmd):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call is Aider — run the fake script instead
            result = subprocess.run(
                [sys.executable, fake_aider_script],
                capture_output=True, text=True, timeout=30, cwd=repo_dir,
            )
            return result
        else:
            # Subsequent calls are test commands — run inside the repo
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=30, cwd=repo_dir,
            )
            return result

    return executor


# ── End-to-end: successful run ───────────────────────────────────────────

class TestE2ESuccessfulRun:
    def test_full_lifecycle(self):
        """Prove the complete controller lifecycle in an isolated repo."""
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)

            task_data = {
                "task_id": "e2e-success",
                "message": "modify planning/target_module.py",
                "allowed_files": ["planning/target_module.py"],
                "allowed_test_commands": [
                    f"{sys.executable} tests/check_target.py"
                ],
            }
            task_path = _write_task(repo, task_data)

            fake_script = _fake_aider_script(
                repo, "planning/target_module.py"
            )
            executor = _make_executor(repo, fake_script)

            # Patch detect_changed_files to use the temp repo
            import atlas_dev_controller.scope_guard as guard_mod
            original_detect = guard_mod.detect_changed_files

            def patched_detect(repo_dir=None):
                return original_detect(repo)

            guard_mod.detect_changed_files = patched_detect
            try:
                result = run_task(task_path, execute_command=executor)
            finally:
                guard_mod.detect_changed_files = original_detect

            # ── Assertions ───────────────────────────────────────────
            assert result.success is True, f"expected success, got error: {result.error}"
            assert result.task_id == "e2e-success"
            assert result.aider_exit_code == 0

            # Test command ran and passed
            assert len(result.test_results) == 1
            assert result.test_results[0]["success"] is True

            # Log file was produced
            assert result.log_path is not None
            log_content = Path(result.log_path).read_text(encoding="utf-8")
            assert "e2e-success" in log_content
            assert "overall_success: True" in log_content
            assert "post_aider_changed_files" in log_content

            # The allowed file was actually modified by the fake Aider
            target = Path(repo) / "planning" / "target_module.py"
            assert "fake aider" in target.read_text(encoding="utf-8")


# ── End-to-end: out-of-scope fail-closed ─────────────────────────────────

class TestE2EOutOfScopeFailClosed:
    def test_rogue_file_detected(self):
        """Prove the controller fails closed when Aider creates a rogue file."""
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)

            task_data = {
                "task_id": "e2e-rogue",
                "message": "modify planning/target_module.py",
                "allowed_files": ["planning/target_module.py"],
                "allowed_test_commands": [
                    f"{sys.executable} tests/check_target.py"
                ],
            }
            task_path = _write_task(repo, task_data)

            fake_script = _fake_aider_script(
                repo,
                "planning/target_module.py",
                rogue_path="tools/rogue.py",
            )
            executor = _make_executor(repo, fake_script)

            import atlas_dev_controller.scope_guard as guard_mod
            original_detect = guard_mod.detect_changed_files

            def patched_detect(repo_dir=None):
                return original_detect(repo)

            guard_mod.detect_changed_files = patched_detect
            try:
                result = run_task(task_path, execute_command=executor)
            finally:
                guard_mod.detect_changed_files = original_detect

            # ── Assertions ───────────────────────────────────────────
            assert result.success is False
            assert result.aider_exit_code == 0  # Aider itself succeeded
            assert "outside the approved scope" in result.error
            assert "rogue" in result.error or "tools" in result.error

            # No test commands should have run
            assert len(result.test_results) == 0

            # Log records the scope violation
            assert result.log_path is not None
            log_content = Path(result.log_path).read_text(encoding="utf-8")
            assert "post-aider scope violation" in log_content


# ── End-to-end: test command failure ─────────────────────────────────────

class TestE2ETestCommandFailure:
    def test_failing_test_detected(self):
        """Prove the controller fails closed when the test command fails."""
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)

            # Write a test script that always fails
            fail_script = Path(repo) / "tests" / "always_fail.py"
            fail_script.write_text(
                "import sys\nsys.exit(1)\n", encoding="utf-8"
            )
            subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
            subprocess.run(
                ["git", "commit", "-m", "add fail script"],
                cwd=repo, capture_output=True, check=True,
            )

            task_data = {
                "task_id": "e2e-fail-test",
                "message": "modify planning/target_module.py",
                "allowed_files": ["planning/target_module.py"],
                "allowed_test_commands": [
                    f"{sys.executable} tests/always_fail.py"
                ],
            }
            task_path = _write_task(repo, task_data)

            fake_script = _fake_aider_script(
                repo, "planning/target_module.py"
            )
            executor = _make_executor(repo, fake_script)

            import atlas_dev_controller.scope_guard as guard_mod
            original_detect = guard_mod.detect_changed_files

            def patched_detect(repo_dir=None):
                return original_detect(repo)

            guard_mod.detect_changed_files = patched_detect
            try:
                result = run_task(task_path, execute_command=executor)
            finally:
                guard_mod.detect_changed_files = original_detect

            # ── Assertions ───────────────────────────────────────────
            assert result.success is False
            assert result.aider_exit_code == 0
            assert len(result.test_results) == 1
            assert result.test_results[0]["success"] is False

            # Log records the failure
            log_content = Path(result.log_path).read_text(encoding="utf-8")
            assert "FAIL" in log_content


# ── Regression: read_only_files and command flags ────────────────────────

class TestReadOnlyFilesInCommand:
    """Prove read_only_files are passed via --read and editable files via --file."""

    def test_read_only_files_appear_as_read_flag(self):
        task = AtlasTask(
            task_id="ro-cmd",
            message="do something",
            allowed_files=["planning/target_module.py"],
            allowed_test_commands=["python -m pytest tests/"],
            read_only_files=["planning/reference.py", "docs/spec.md"],
        )
        cmd = build_aider_command(task)

        # --read flags for read-only files
        for ro in task.read_only_files:
            idx = cmd.index("--read")
            assert cmd[cmd.index("--read", idx) + 1] == ro or ro in cmd

        # --file flags only for editable files
        file_args = [cmd[i + 1] for i, v in enumerate(cmd) if v == "--file"]
        assert file_args == ["planning/target_module.py"]

        # read-only files must NOT appear after --file
        read_args = [cmd[i + 1] for i, v in enumerate(cmd) if v == "--read"]
        assert set(read_args) == {"planning/reference.py", "docs/spec.md"}

    def test_no_read_flags_when_read_only_empty(self):
        task = AtlasTask(
            task_id="ro-empty",
            message="do something",
            allowed_files=["planning/target_module.py"],
            allowed_test_commands=["python -m pytest tests/"],
            read_only_files=[],
        )
        cmd = build_aider_command(task)
        assert "--read" not in cmd

    def test_backward_compat_no_read_only_field(self):
        """read_only_files defaults to empty list when omitted."""
        task = AtlasTask(
            task_id="ro-compat",
            message="do something",
            allowed_files=["planning/target_module.py"],
            allowed_test_commands=["python -m pytest tests/"],
        )
        assert task.read_only_files == []
        cmd = build_aider_command(task)
        assert "--read" not in cmd


class TestNoGitignoreFlag:
    """Prove --no-gitignore and --no-git are both present."""

    def test_no_gitignore_present(self):
        task = AtlasTask(
            task_id="flag-check",
            message="do something",
            allowed_files=["planning/target_module.py"],
            allowed_test_commands=["python -m pytest tests/"],
        )
        cmd = build_aider_command(task)
        assert "--no-gitignore" in cmd

    def test_no_git_present(self):
        """Aider must never run git commands — --no-git is a safety invariant."""
        task = AtlasTask(
            task_id="flag-check2",
            message="do something",
            allowed_files=["planning/target_module.py"],
            allowed_test_commands=["python -m pytest tests/"],
        )
        cmd = build_aider_command(task)
        assert "--no-git" in cmd

    def test_no_auto_commits_present(self):
        task = AtlasTask(
            task_id="flag-check3",
            message="do something",
            allowed_files=["planning/target_module.py"],
            allowed_test_commands=["python -m pytest tests/"],
        )
        cmd = build_aider_command(task)
        assert "--no-auto-commits" in cmd


class TestReadOnlyAllowedOverlapRejected:
    """Prove that overlapping read_only_files and allowed_files is rejected."""

    def test_overlap_raises(self):
        with pytest.raises(TaskValidationError, match="must not overlap"):
            AtlasTask(
                task_id="overlap",
                message="do something",
                allowed_files=["planning/target_module.py"],
                allowed_test_commands=["python -m pytest tests/"],
                read_only_files=["planning/target_module.py"],
            )

    def test_partial_overlap_raises(self):
        with pytest.raises(TaskValidationError, match="must not overlap"):
            AtlasTask(
                task_id="overlap2",
                message="do something",
                allowed_files=["a.py", "b.py"],
                allowed_test_commands=["python -m pytest tests/"],
                read_only_files=["b.py", "c.py"],
            )

    def test_no_overlap_ok(self):
        task = AtlasTask(
            task_id="no-overlap",
            message="do something",
            allowed_files=["a.py"],
            allowed_test_commands=["python -m pytest tests/"],
            read_only_files=["b.py"],
        )
        assert task.read_only_files == ["b.py"]


class TestReadOnlyFilesValidation:
    """Prove read_only_files validation edge cases."""

    def test_empty_string_rejected(self):
        with pytest.raises(TaskValidationError, match="read_only_files"):
            AtlasTask(
                task_id="ro-bad",
                message="do something",
                allowed_files=["a.py"],
                allowed_test_commands=["python -m pytest tests/"],
                read_only_files=[""],
            )

    def test_non_list_rejected(self):
        with pytest.raises(TaskValidationError, match="read_only_files must be a list"):
            AtlasTask(
                task_id="ro-bad2",
                message="do something",
                allowed_files=["a.py"],
                allowed_test_commands=["python -m pytest tests/"],
                read_only_files="not_a_list",
            )


class TestLoadTaskReadOnlyFiles:
    """Prove load_task handles read_only_files from JSON."""

    def test_load_with_read_only(self, tmp_path):
        from atlas_dev_controller.task_schema import load_task

        task_data = {
            "task_id": "load-ro",
            "message": "do something",
            "allowed_files": ["a.py"],
            "allowed_test_commands": ["python -m pytest"],
            "read_only_files": ["b.py", "c.py"],
        }
        p = tmp_path / "task.json"
        p.write_text(json.dumps(task_data), encoding="utf-8")
        task = load_task(str(p))
        assert task.read_only_files == ["b.py", "c.py"]

    def test_load_without_read_only(self, tmp_path):
        from atlas_dev_controller.task_schema import load_task

        task_data = {
            "task_id": "load-no-ro",
            "message": "do something",
            "allowed_files": ["a.py"],
            "allowed_test_commands": ["python -m pytest"],
        }
        p = tmp_path / "task.json"
        p.write_text(json.dumps(task_data), encoding="utf-8")
        task = load_task(str(p))
        assert task.read_only_files == []


class TestE2EWithReadOnlyFiles:
    """End-to-end: read_only_files are passed to Aider but not editable."""

    def test_read_only_in_full_lifecycle(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)

            # Create a read-only reference file
            ref = Path(repo) / "planning" / "reference.py"
            ref.write_text("# reference\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
            subprocess.run(
                ["git", "commit", "-m", "add reference"],
                cwd=repo, capture_output=True, check=True,
            )

            task_data = {
                "task_id": "e2e-readonly",
                "message": "modify planning/target_module.py",
                "allowed_files": ["planning/target_module.py"],
                "read_only_files": ["planning/reference.py"],
                "allowed_test_commands": [
                    f"{sys.executable} tests/check_target.py"
                ],
            }
            task_path = _write_task(repo, task_data)

            fake_script = _fake_aider_script(
                repo, "planning/target_module.py"
            )

            # Capture the command to verify --read was included
            captured_cmds = []
            real_executor = _make_executor(repo, fake_script)

            def capturing_executor(cmd):
                captured_cmds.append(cmd)
                return real_executor(cmd)

            import atlas_dev_controller.scope_guard as guard_mod
            original_detect = guard_mod.detect_changed_files

            def patched_detect(repo_dir=None):
                return original_detect(repo)

            guard_mod.detect_changed_files = patched_detect
            try:
                result = run_task(task_path, execute_command=capturing_executor)
            finally:
                guard_mod.detect_changed_files = original_detect

            assert result.success is True, f"expected success, got error: {result.error}"

            # The Aider command (first captured) must contain --read
            aider_cmd = captured_cmds[0]
            assert "--read" in aider_cmd
            read_idx = aider_cmd.index("--read")
            assert aider_cmd[read_idx + 1] == "planning/reference.py"

            # --no-gitignore and --no-git both present
            assert "--no-gitignore" in aider_cmd
            assert "--no-git" in aider_cmd

            # Reference file was NOT modified
            assert ref.read_text(encoding="utf-8") == "# reference\n"
