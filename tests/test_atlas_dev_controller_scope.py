"""Regression tests for post-Aider filesystem scope enforcement.

Coverage targets:
- detect_changed_files finds modified, added, deleted, renamed files.
- validate_post_aider_scope passes when all changes are in scope.
- validate_post_aider_scope fails closed on out-of-scope changes.
- Runner integration: Aider run that produces out-of-scope changes fails closed.
- Git command failures are fail-closed (not silently ignored).
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from atlas_dev_controller.scope_guard import (
    ScopeViolationError,
    detect_changed_files,
    validate_post_aider_scope,
)
from atlas_dev_controller.runner import run_task


# ── Helpers ──────────────────────────────────────────────────────────────

def _init_git_repo(repo_dir):
    """Initialize a git repo with one committed file."""
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, capture_output=True, check=True)
    # Create and commit an initial file so HEAD exists
    initial = Path(repo_dir) / "initial.txt"
    initial.write_text("initial", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, capture_output=True, check=True)


def _write_task_file(tmp_dir, data):
    path = os.path.join(tmp_dir, "task.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


# ── detect_changed_files ─────────────────────────────────────────────────

class TestDetectChangedFiles:
    def test_no_changes(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            changed = detect_changed_files(repo)
            assert changed == []

    def test_modified_file_detected(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            (Path(repo) / "initial.txt").write_text("modified", encoding="utf-8")
            changed = detect_changed_files(repo)
            assert any("initial.txt" in f for f in changed)

    def test_new_untracked_file_detected(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            (Path(repo) / "new_file.py").write_text("new", encoding="utf-8")
            changed = detect_changed_files(repo)
            assert any("new_file.py" in f for f in changed)

    def test_deleted_file_detected(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            (Path(repo) / "initial.txt").unlink()
            changed = detect_changed_files(repo)
            assert any("initial.txt" in f for f in changed)

    def test_multiple_changes_detected(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            (Path(repo) / "initial.txt").write_text("modified", encoding="utf-8")
            (Path(repo) / "added.py").write_text("new", encoding="utf-8")
            changed = detect_changed_files(repo)
            assert len(changed) >= 2

    def test_subdirectory_file_detected(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            subdir = Path(repo) / "planning"
            subdir.mkdir()
            (subdir / "new_module.py").write_text("code", encoding="utf-8")
            changed = detect_changed_files(repo)
            assert any("planning/new_module.py" in f.replace("\\", "/") for f in changed)

    def test_no_duplicates(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            # Stage and then modify again — should appear once
            target = Path(repo) / "initial.txt"
            target.write_text("staged", encoding="utf-8")
            subprocess.run(["git", "add", "initial.txt"], cwd=repo, capture_output=True)
            target.write_text("modified again", encoding="utf-8")
            changed = detect_changed_files(repo)
            normalized = [f.replace("\\", "/").lower() for f in changed]
            assert len(normalized) == len(set(normalized))


# ── validate_post_aider_scope ────────────────────────────────────────────

class TestValidatePostAiderScope:
    def test_all_changes_in_scope(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            (Path(repo) / "initial.txt").write_text("modified", encoding="utf-8")
            changed = validate_post_aider_scope(["initial.txt"], repo)
            assert len(changed) == 1

    def test_out_of_scope_change_rejected(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            (Path(repo) / "initial.txt").write_text("modified", encoding="utf-8")
            (Path(repo) / "unauthorized.py").write_text("bad", encoding="utf-8")
            with pytest.raises(ScopeViolationError, match="outside the approved scope"):
                validate_post_aider_scope(["initial.txt"], repo)

    def test_new_file_out_of_scope_rejected(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            (Path(repo) / "rogue.py").write_text("rogue", encoding="utf-8")
            with pytest.raises(ScopeViolationError, match="outside the approved scope"):
                validate_post_aider_scope(["initial.txt"], repo)

    def test_no_changes_passes(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            changed = validate_post_aider_scope(["initial.txt"], repo)
            assert changed == []

    def test_subdirectory_in_scope(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            subdir = Path(repo) / "planning"
            subdir.mkdir()
            (subdir / "module.py").write_text("code", encoding="utf-8")
            changed = validate_post_aider_scope(["planning/module.py"], repo)
            assert len(changed) == 1

    def test_subdirectory_out_of_scope_rejected(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            subdir = Path(repo) / "tools"
            subdir.mkdir()
            (subdir / "blender.py").write_text("bad", encoding="utf-8")
            with pytest.raises(ScopeViolationError, match="outside the approved scope"):
                validate_post_aider_scope(["planning/module.py"], repo)


# ── Runner integration with post-Aider scope ────────────────────────────

class TestRunnerPostAiderScope:
    def test_runner_detects_out_of_scope_aider_change(self):
        """Simulate Aider creating an out-of-scope file, verify fail-closed."""
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)

            # Write task file
            task_data = {
                "task_id": "scope-test",
                "message": "test",
                "allowed_files": ["planning/allowed.py"],
                "allowed_test_commands": ["python -m pytest tests/ -v"],
            }
            task_path = _write_task_file(repo, task_data)

            call_count = [0]

            def aider_creates_rogue_file(cmd):
                call_count[0] += 1
                if call_count[0] == 1:
                    # Simulate Aider creating an out-of-scope file
                    rogue = Path(repo) / "tools" / "rogue.py"
                    rogue.parent.mkdir(exist_ok=True)
                    rogue.write_text("rogue code", encoding="utf-8")
                    return subprocess.CompletedProcess(cmd, 0, "aider ok", "")
                return subprocess.CompletedProcess(cmd, 0, "test ok", "")

            # Monkey-patch detect_changed_files to use our temp repo
            import atlas_dev_controller.runner as runner_mod
            import atlas_dev_controller.scope_guard as guard_mod
            original_detect = guard_mod.detect_changed_files

            def patched_detect(repo_dir=None):
                return original_detect(repo)

            guard_mod.detect_changed_files = patched_detect
            try:
                result = run_task(task_path, execute_command=aider_creates_rogue_file)
                assert result.success is False
                assert "outside the approved scope" in result.error
                assert result.aider_exit_code == 0  # Aider succeeded but scope failed
            finally:
                guard_mod.detect_changed_files = original_detect

    def test_runner_passes_when_changes_in_scope(self):
        """Simulate Aider modifying only in-scope files."""
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)

            # Create the allowed file in the committed state
            planning_dir = Path(repo) / "planning"
            planning_dir.mkdir()
            allowed_file = planning_dir / "allowed.py"
            allowed_file.write_text("original", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "add allowed"], cwd=repo, capture_output=True, check=True)

            task_data = {
                "task_id": "scope-ok",
                "message": "test",
                "allowed_files": ["planning/allowed.py"],
                "allowed_test_commands": ["python -m pytest tests/ -v"],
            }
            task_path = _write_task_file(repo, task_data)

            call_count = [0]

            def aider_modifies_allowed(cmd):
                call_count[0] += 1
                if call_count[0] == 1:
                    # Simulate Aider modifying the allowed file
                    allowed_file.write_text("modified by aider", encoding="utf-8")
                    return subprocess.CompletedProcess(cmd, 0, "aider ok", "")
                return subprocess.CompletedProcess(cmd, 0, "test ok", "")

            import atlas_dev_controller.scope_guard as guard_mod
            original_detect = guard_mod.detect_changed_files

            def patched_detect(repo_dir=None):
                return original_detect(repo)

            guard_mod.detect_changed_files = patched_detect
            try:
                result = run_task(task_path, execute_command=aider_modifies_allowed)
                assert result.success is True
            finally:
                guard_mod.detect_changed_files = original_detect


# ── Git failure is fail-closed ───────────────────────────────────────────

class TestGitFailureBehavior:
    def test_non_git_directory_fails_closed(self):
        with tempfile.TemporaryDirectory() as non_repo:
            with pytest.raises(ScopeViolationError):
                detect_changed_files(non_repo)
