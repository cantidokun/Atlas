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
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from atlas_dev_controller.runner import run_task


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
