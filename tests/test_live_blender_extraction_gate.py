"""LIVE-Blender-runtime integration test (operator-gated; NOT run in deterministic CI).

This is the single live integration test for the thin extraction adapter. It:
- runs only when explicitly gated by the environment (``ATLAS_RUN_LIVE_BLENDER=1``),
- requires a real Blender executable (the configured ``BLENDER`` path),
- builds a minimal deterministic scene via a small read-only ``bpy`` snippet,
- extracts the canonical payload, runs it through the deterministic kernel, and asserts key
  SceneReport properties / finding codes,
- does NOT modify the scene, does NOT save/overwrite any asset.

It is clearly labeled a live/Blender-runtime integration test. It must NOT run during ordinary
``pytest -m "not integration"`` / CI.

To run explicitly (authorized live run only)::
    ATLAS_RUN_LIVE_BLENDER=1 python -m pytest tests/test_live_blender_extraction_gate.py -s
"""

import os
import subprocess
import sys

import pytest


def _live_enabled() -> bool:
    return os.environ.get("ATLAS_RUN_LIVE_BLENDER", "") == "1"


live = _live_enabled()

pytestmark = [pytest.mark.skipif(not live, reason="live Blender gate off")]


def _blender_command():
    import tools.blender as tb

    return tb.BLENDER  # configured path, e.g. C:\\Program Files\\...\\blender.exe


# A read-only bpy script: it builds a tiny deterministic, in-memory mesh scene and emits the
# canonical payload (never saving to disk, never touching production assets).
_LIVE_SCRIPT = r'''
import bpy, json, os, sys

# Blender's embedded Python does not reliably honor PYTHONPATH on all installations.
# Bootstrap the repository root explicitly through an environment variable so the live gate
# can import the canonical Atlas packages without depending on shell-specific path behavior.
sys.path.insert(0, os.environ["ATLAS_REPO_ROOT"])

# Build a minimal deterministic, in-memory soccer-ish scene (read-only; nothing saved).
if "Pitch" not in bpy.data.meshes:
    me = bpy.data.meshes.new("Pitch")
    verts = [(0.0,0.0,0.0),(1.0,0.0,0.0),(0.0,1.0,0.0),(1.0,1.0,0.0)]
    faces = [(0,1,2),(1,3,2)]
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new("pitch", me)
    bpy.context.scene.collection.objects.link(obj)

for role in ("goal_left", "goal_right"):
    if role not in bpy.data.objects:
        mt = bpy.data.objects.new(role, None)
        bpy.context.scene.collection.objects.link(mt)

# Extract the canonical payload (the same shape the deterministic bpy_extraction emits).
from planning.blender.bpy_extraction import run_live_blender_extraction
payload = run_live_blender_extraction(bpy)

# Run the deterministic kernel.
from planning.blender.kernel import run_scene_health, soccer_field_profile_default
scene = __import__("planning.blender.extraction_payload", fromlist=["payload_to_scene_model"]).payload_to_scene_model(payload)
report = run_scene_health(scene, soccer_field_profile_default())

out = {
    "scene_id": report.scene_id,
    "state": report.validation_state,
    "finding_codes": sorted({f.code.value for f in report.findings}),
    "digest": report.digest(),
}
print("ATLAS_LIVE_START")
print(json.dumps(out))
print("ATLAS_LIVE_END")
'''


def test_live_blender_extraction_to_report():
    """Live: read-only bpy extraction -> payload -> deterministic SceneReport."""
    cmd = [
        _blender_command(),
        "--background",
        "--python-expr",
        _LIVE_SCRIPT,
    ]
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = repo if not existing else repo + os.pathsep + existing
    env["ATLAS_REPO_ROOT"] = repo
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=180, cwd=repo, env=env,
    )
    if proc.returncode != 0:
        raise AssertionError(f"Blender live extraction failed rc={proc.returncode}: {proc.stderr[-2000:]}")
    start = proc.stdout.find("ATLAS_LIVE_START")
    end = proc.stdout.find("ATLAS_LIVE_END")
    assert start != -1 and end != -1, "live payload markers missing"
    import json as _json
    result = _json.loads(proc.stdout[start + len("ATLAS_LIVE_START"):end].strip())
    assert result["scene_id"] == "Scene" or result["scene_id"]
    assert isinstance(result["digest"], str) and len(result["digest"]) == 64
    # Soccer roles present -> READY or ANALYZED; must not contain an index error.
    assert result["state"] in ("production_ready", "analyzed")
    assert "MESH_INVALID_INDEX" not in result["finding_codes"]
