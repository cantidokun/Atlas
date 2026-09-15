"""Explicit live Blender gate for Wave 11 zero-face extraction.

Run only with ATLAS_RUN_LIVE_BLENDER=1 and a real supported Blender executable.
The disposable scene is in-memory only and is never saved.
"""

import json
import os
import subprocess

import pytest


pytestmark = pytest.mark.skipif(os.environ.get("ATLAS_RUN_LIVE_BLENDER", "") != "1", reason="live Blender gate off")


_LIVE_SCRIPT = r'''
import bpy, json, os, sys
sys.path.insert(0, os.environ["ATLAS_REPO_ROOT"])

# Disposable in-memory scene.
for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

mesh = bpy.data.meshes.new("wave11_zero_face")
mesh.from_pydata([(1.25, 2.5, 3.75), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0)], [], [])
mesh.update()
obj = bpy.data.objects.new("wave11_zero_face", mesh)
bpy.context.scene.collection.objects.link(obj)

from planning.blender.bpy_extraction import run_live_blender_extraction
payload = run_live_blender_extraction(bpy)
entry = next(item for item in payload["objects"] if item["object_id"] == "wave11_zero_face")

out = {
    "vertex_count": len(entry["mesh"]["vertices"]),
    "face_count": len(entry["mesh"]["faces"]),
    "vertices": entry["mesh"]["vertices"],
    "faces": entry["mesh"]["faces"],
}
print("ATLAS_WAVE11_ZERO_FACE_START")
print(json.dumps(out, sort_keys=True))
print("ATLAS_WAVE11_ZERO_FACE_END")
'''


def _blender_command():
    import tools.blender as tb
    return tb.BLENDER


def test_live_zero_face_mesh_extracts_truthfully():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ)
    env["ATLAS_REPO_ROOT"] = repo
    pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = repo if not pythonpath else repo + os.pathsep + pythonpath
    proc = subprocess.run(
        [_blender_command(), "--background", "--python-expr", _LIVE_SCRIPT],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=repo,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr[-4000:]
    start = proc.stdout.find("ATLAS_WAVE11_ZERO_FACE_START")
    end = proc.stdout.find("ATLAS_WAVE11_ZERO_FACE_END")
    assert start != -1 and end != -1
    result = json.loads(proc.stdout[start + len("ATLAS_WAVE11_ZERO_FACE_START"):end].strip())
    assert result["vertex_count"] == 3
    assert result["face_count"] == 0
    assert result["vertices"] == [[1.25, 2.5, 3.75], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]
    assert result["faces"] == []
