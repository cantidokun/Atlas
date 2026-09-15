"""Pytest gate for the disposable Wave-12 Blender boundary probe."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tests" / "parent_cycle_live_script.py"


def _blender_executable() -> str | None:
    configured = os.environ.get("ATLAS_BLENDER_EXECUTABLE")
    if configured:
        return configured
    return shutil.which("blender")


def _run_blender() -> subprocess.CompletedProcess[str]:
    executable = _blender_executable()
    if not executable:
        pytest.skip("Blender executable not found. Set ATLAS_BLENDER_EXECUTABLE or put blender on PATH.")
    return subprocess.run(
        [executable, "--background", "--python", str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )


def test_wave12_live_script_is_static_safe() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "atlas_transform_validation.blend" not in text
    assert "bpy.ops.wm.open_mainfile" not in text
    assert "bpy.ops.wm.save" not in text
    assert "bpy.ops.wm.save_as_mainfile" not in text
    assert "save_attempted': False" in text
    assert "opened_frozen_asset': False" in text


@pytest.mark.skipif(
    os.environ.get("ATLAS_RUN_LIVE_BLENDER") != "1",
    reason="Set ATLAS_RUN_LIVE_BLENDER=1 to run the Blender process.",
)
def test_wave12_live_blender_boundary_gate() -> None:
    result = _run_blender()
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined
    payload_lines = [line for line in result.stdout.splitlines() if line.startswith('{"blender_version"')]
    assert payload_lines, combined
    payload = json.loads(payload_lines[-1])

    assert payload["marker"] == "ATLAS_WAVE12_PARENT_CYCLE_LIVE"
    assert tuple(payload["blender_version"]) == (4, 4, 3)
    assert payload["failed"] == []
    assert payload["save_attempted"] is False
    assert payload["opened_frozen_asset"] is False
    assert payload["checks"]["parent_cleared"] is True
    assert payload["checks"]["world_matrix_preserved"] is True
    assert payload["checks"]["object_identity_preserved"] is True
    assert payload["checks"]["mesh_identity_preserved"] is True
    assert payload["checks"]["objects_preserved"] is True
    assert payload["checks"]["no_file_path_before"] is True
    assert payload["checks"]["no_file_path_after"] is True
    assert "ATLAS_WAVE12_PARENT_CYCLE_LIVE_PASS" in result.stdout
