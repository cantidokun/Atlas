"""Executable gate for the disposable Wave 5 Blender topology probe."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


EXPECTED_BLENDER = (4, 4, 3)
MARKER = "ATLAS_WAVE5_TOPOLOGY_LIVE_PASS"


def _blender_executable():
    configured = os.environ.get("ATLAS_BLENDER_EXECUTABLE")
    if configured:
        return configured
    return shutil.which("blender")


@pytest.mark.skipif(
    os.environ.get("ATLAS_RUN_LIVE_BLENDER") != "1",
    reason="set ATLAS_RUN_LIVE_BLENDER=1 to run the live Blender gate",
)
def test_live_blender_topology_gate():
    executable = _blender_executable()
    if not executable:
        pytest.fail("Blender executable not found; set ATLAS_BLENDER_EXECUTABLE")

    script = Path(__file__).with_name("topology_intelligence_live_script.py")
    completed = subprocess.run(
        [executable, "--background", "--python", str(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    payload = None
    for line in completed.stdout.splitlines():
        line = line.strip()
        if line.startswith("{") and '"marker"' in line:
            payload = json.loads(line)
    assert payload is not None, completed.stdout
    assert tuple(payload["blender_version"]) == EXPECTED_BLENDER
    assert payload["failed"] == []
    assert payload["source_vertex_count"] == 5
    assert payload["source_face_count"] == 4
    assert payload["source_edge_count"] == 6
    assert payload["source_edge_valence_histogram"] == [[2, 6]]
    assert payload["save_attempted"] is False
    assert payload["opened_frozen_asset"] is False
    assert MARKER in completed.stdout
