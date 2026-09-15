from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(os.environ.get("ATLAS_RUN_LIVE_BLENDER") != "1", reason="live Blender gate disabled")
def test_live_blender_isolated_vertex_removal_gate():
    executable = os.environ.get("ATLAS_BLENDER_EXECUTABLE") or shutil.which("blender")
    if not executable:
        pytest.fail("Blender executable not found; set ATLAS_BLENDER_EXECUTABLE")
    script = Path(__file__).with_name("isolated_vertex_removal_live_script.py")
    completed = subprocess.run(
        [executable, "--background", "--factory-startup", "--python", str(script)],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    output = completed.stdout + "\n" + completed.stderr
    assert completed.returncode == 0, output
    assert "ATLAS_WAVE6_ISOLATED_VERTEX_LIVE_PASS" in output, output
    marker = next((line for line in output.splitlines() if line.startswith('{"checks"')), None)
    assert marker is not None, output
    evidence = json.loads(marker)
    assert all(evidence["checks"].values()), evidence
    assert evidence["save_attempted"] is False
