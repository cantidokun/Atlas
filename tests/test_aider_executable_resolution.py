"""Focused tests for aider executable resolution and command building.

These tests verify that the Atlas development controller:
- Resolves the installed ``aider`` CLI executable deterministically.
- Fails closed with ``ControllerError`` when the executable is missing.
- Builds a command that starts with the resolved executable (never ``python -m``).
"""

import os
import sys
import textwrap
from unittest import mock

import pytest

from atlas_dev_controller.runner import (
    ControllerError,
    build_aider_command,
    resolve_aider_executable,
)
from atlas_dev_controller.task_schema import AtlasTask


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(**overrides) -> AtlasTask:
    """Return a minimal valid AtlasTask for testing."""
    defaults = dict(
        task_id="test-001",
        message="do something",
        allowed_files=["foo.py"],
        allowed_test_commands=["pytest tests/"],
        model="gpt-4",
    )
    defaults.update(overrides)
    return AtlasTask(**defaults)


# ---------------------------------------------------------------------------
# resolve_aider_executable
# ---------------------------------------------------------------------------

class TestResolveAiderExecutable:
    """Tests for ``resolve_aider_executable``."""

    def test_found_on_path(self, tmp_path):
        """When ``shutil.which`` finds aider, return its absolute path."""
        fake_aider = tmp_path / "aider"
        fake_aider.write_text("fake")
        with mock.patch("atlas_dev_controller.runner.shutil.which", return_value=str(fake_aider)):
            result = resolve_aider_executable()
        assert os.path.isabs(result)
        assert result == os.path.abspath(str(fake_aider))

    def test_found_in_venv_scripts_windows(self, tmp_path):
        """Fallback to <prefix>/Scripts/aider.exe on Windows when PATH misses it."""
        scripts = tmp_path / "Scripts"
        scripts.mkdir()
        fake_exe = scripts / "aider.exe"
        fake_exe.write_text("fake")

        with mock.patch("atlas_dev_controller.runner.shutil.which", return_value=None), \
             mock.patch("atlas_dev_controller.runner.sys") as mock_sys:
            mock_sys.platform = "win32"
            mock_sys.prefix = str(tmp_path)
            result = resolve_aider_executable()

        assert os.path.isabs(result)
        assert "aider" in os.path.basename(result).lower()

    def test_found_in_venv_bin_unix(self, tmp_path):
        """Fallback to <prefix>/bin/aider on Unix when PATH misses it."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        fake_exe = bin_dir / "aider"
        fake_exe.write_text("fake")

        with mock.patch("atlas_dev_controller.runner.shutil.which", return_value=None), \
             mock.patch("atlas_dev_controller.runner.sys") as mock_sys:
            mock_sys.platform = "linux"
            mock_sys.prefix = str(tmp_path)
            result = resolve_aider_executable()

        assert os.path.isabs(result)
        assert result == os.path.abspath(str(fake_exe))

    def test_fail_closed_when_not_found(self, tmp_path):
        """Must raise ControllerError when aider is nowhere to be found."""
        with mock.patch("atlas_dev_controller.runner.shutil.which", return_value=None), \
             mock.patch("atlas_dev_controller.runner.sys") as mock_sys:
            mock_sys.platform = "win32"
            mock_sys.prefix = str(tmp_path)  # empty dir, no Scripts/
            with pytest.raises(ControllerError, match="Cannot locate.*aider"):
                resolve_aider_executable()

    def test_fail_closed_message_includes_prefix(self, tmp_path):
        """Error message should mention the active environment prefix."""
        with mock.patch("atlas_dev_controller.runner.shutil.which", return_value=None), \
             mock.patch("atlas_dev_controller.runner.sys") as mock_sys:
            mock_sys.platform = "linux"
            mock_sys.prefix = str(tmp_path)
            with pytest.raises(ControllerError) as exc_info:
                resolve_aider_executable()
            assert str(tmp_path) in str(exc_info.value)


# ---------------------------------------------------------------------------
# build_aider_command
# ---------------------------------------------------------------------------

class TestBuildAiderCommand:
    """Tests for ``build_aider_command`` with resolved executable."""

    def test_command_uses_resolved_executable(self, tmp_path):
        """The first element must be the resolved aider executable, not python -m."""
        fake_aider = str(tmp_path / "aider")
        task = _make_task()
        with mock.patch(
            "atlas_dev_controller.runner.resolve_aider_executable",
            return_value=fake_aider,
        ):
            cmd = build_aider_command(task)

        assert cmd[0] == fake_aider
        # Must NOT contain python -m aider anywhere
        assert "-m" not in cmd
        assert sys.executable not in cmd

    def test_command_preserves_safety_flags(self, tmp_path):
        """Safety flags must always be present regardless of task content."""
        fake_aider = str(tmp_path / "aider")
        task = _make_task()
        with mock.patch(
            "atlas_dev_controller.runner.resolve_aider_executable",
            return_value=fake_aider,
        ):
            cmd = build_aider_command(task)

        assert "--no-auto-commits" in cmd
        assert "--no-git" in cmd
        assert "--yes" in cmd

    def test_command_includes_model_and_message(self, tmp_path):
        """Model and message from the task must appear in the command."""
        fake_aider = str(tmp_path / "aider")
        task = _make_task(model="gpt-4o", message="fix the bug")
        with mock.patch(
            "atlas_dev_controller.runner.resolve_aider_executable",
            return_value=fake_aider,
        ):
            cmd = build_aider_command(task)

        model_idx = cmd.index("--model")
        assert cmd[model_idx + 1] == "gpt-4o"
        msg_idx = cmd.index("--message")
        assert cmd[msg_idx + 1] == "fix the bug"

    def test_command_includes_all_allowed_files(self, tmp_path):
        """Every allowed file must be passed via --file."""
        fake_aider = str(tmp_path / "aider")
        files = ["a.py", "b.py", "c.py"]
        task = _make_task(allowed_files=files)
        with mock.patch(
            "atlas_dev_controller.runner.resolve_aider_executable",
            return_value=fake_aider,
        ):
            cmd = build_aider_command(task)

        file_args = [cmd[i + 1] for i, v in enumerate(cmd) if v == "--file"]
        assert file_args == files

    def test_build_fails_closed_when_executable_missing(self):
        """build_aider_command must propagate ControllerError from resolution."""
        task = _make_task()
        with mock.patch(
            "atlas_dev_controller.runner.resolve_aider_executable",
            side_effect=ControllerError("not found"),
        ):
            with pytest.raises(ControllerError):
                build_aider_command(task)
