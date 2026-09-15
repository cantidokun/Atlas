"""LIVE Blender gate for Wave 9 object-name normalization."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("object_name_normalization_live_script.py")


def _blender_executable() -> str | None:
    configured = os.environ.get("ATLAS_BLENDER_EXECUTABLE")
    if configured:
        return configured
    return shutil.which("blender")


def test_wave9_live_blender_boundary():
    if os.environ.get("ATLAS_RUN_LIVE_BLENDER") != "1":
        pytest.skip("set ATLAS_RUN_LIVE_BLENDER=1 to run the live Blender gate")
    executable = _blender_executable()
    if not executable:
        pytest.skip("Blender executable not found. Set ATLAS_BLENDER_EXECUTABLE or put blender on PATH.")

    proc = subprocess.run(
        [executable, "--background", "--factory-startup", "--python", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + "\n" + proc.stdout
    marker = next(
        (line for line in proc.stdout.splitlines() if line.startswith("ATLAS_WAVE9_OBJECT_NAME_LIVE_RESULT=")),
        None,
    )
    assert marker is not None, proc.stdout
    payload = json.loads(marker.split("=", 1)[1])
    assert payload["all_checks"] is True, payload
    assert payload["save_attempted"] is False, payload
    assert "ATLAS_WAVE9_OBJECT_NAME_LIVE_PASS" in proc.stdout
