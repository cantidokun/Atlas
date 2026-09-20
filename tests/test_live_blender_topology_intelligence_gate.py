"""Executable gate for the disposable Wave 5 + Read-Only Non-Manifold Blender probe."""
import json
import os
import shutil
import subprocess
from pathlib import Path
import pytest

EXPECTED_BLENDER=(4,4,3)
MARKER="ATLAS_READONLY_NON_MANIFOLD_V1_LIVE"

def _blender_executable():
    return os.environ.get("ATLAS_BLENDER_EXECUTABLE") or shutil.which("blender")

@pytest.mark.skipif(os.environ.get("ATLAS_RUN_LIVE_BLENDER")!="1",reason="set ATLAS_RUN_LIVE_BLENDER=1 to run the live Blender gate")
def test_live_blender_topology_gate():
    executable=_blender_executable()
    if not executable: pytest.fail("Blender executable not found; set ATLAS_BLENDER_EXECUTABLE")
    script=Path(__file__).with_name("topology_intelligence_live_script.py")
    completed=subprocess.run([executable,"--background","--python",str(script)],capture_output=True,text=True,check=False)
    assert completed.returncode==0, completed.stdout+completed.stderr
    payload=None
    for line in completed.stdout.splitlines():
        line=line.strip()
        if line.startswith("{") and '"marker"' in line: payload=json.loads(line)
    assert payload is not None, completed.stdout
    assert tuple(payload["blender_version"])==EXPECTED_BLENDER
    assert payload["failed"]==[]
    assert payload["required_assertions"] >= 17
    assert payload["passed"] == payload["required_assertions"]
    assert payload["save_attempted"] is False
    assert payload["opened_frozen_asset"] is False
    assert f"{MARKER}_PASS" in completed.stdout
