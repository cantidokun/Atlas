"""Smoke tests for the Windows/self-hosted Blender environment."""

import os
import platform
import shutil
import subprocess

import pytest

from tools.blender import BLENDER


@pytest.mark.blender
def test_self_hosted_windows_runner_environment():
    assert platform.system() == "Windows"
    assert os.environ.get("GITHUB_ACTIONS") == "true"
    assert os.environ.get("RUNNER_NAME")


@pytest.mark.blender
def test_blender_executable_is_available():
    """Validate the executable Atlas already uses for controlled Blender calls."""
    blender = shutil.which("blender") or shutil.which("blender.exe") or BLENDER
    assert blender, "Blender executable was not configured for the self-hosted runner."
    assert os.path.isfile(blender), f"Configured Blender executable was not found: {blender}"
    completed = subprocess.run([blender, "--version"], capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert "Blender" in completed.stdout
