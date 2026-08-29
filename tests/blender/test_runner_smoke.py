"""Minimal Windows/self-hosted smoke test for the Atlas Blender runner.

This test deliberately validates runner availability before any scene mutation.
The real Blender fixture tests will build on this gate.
"""

import os
import platform
import shutil
import subprocess


def test_self_hosted_windows_runner_environment():
    assert platform.system() == "Windows"
    assert os.environ.get("GITHUB_ACTIONS") == "true"
    assert os.environ.get("RUNNER_NAME")


def test_blender_executable_is_available():
    blender = shutil.which("blender") or shutil.which("blender.exe")
    assert blender, "Blender executable was not found on the self-hosted runner."
    completed = subprocess.run([blender, "--version"], capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert "Blender" in completed.stdout
