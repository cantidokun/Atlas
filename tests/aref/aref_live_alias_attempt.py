"""A-REF aliased-merge ATTEMPT (R4F 16.6(4): "source inspection plus a live attempt ... record the
result" for C3/C4). This is a RECORDED ATTEMPT, not a registered conformance case: the aliased
merge scene has TWO target scopes, and the merge pass refuses more than one scope rather than
aggregating it, so no single-correction aliased merge plan exists to reduce through the real
planner. The attempt records exactly that, live.

Blender-only module (imports bpy via the builder).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict

import bpy

from planning.blender.bpy_extraction import extract_scene
from planning.blender.extraction_payload import payload_to_scene_model
from planning.blender.kernel import run_scene_health, soccer_field_profile_default

from tests.aref import aref_plan
from tests.aref.aref_live_builder import build_scene_from_spec

#: The pinned merge fixture geometry (merge_vertex_live_script.py:353-355), shared by BOTH objects.
B1_VERTS = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [7.0, 0.0, 0.0],
            [3.0, 3.0, 0.0], [3.0, 3.0, 0.0], [4.0, 0.0, 5.0]]
B1_FACES = [[0, 2, 3], [5, 2, 3]]

ALIASED_SPEC = SimpleNamespace(
    scene={"scene_id": "r4f-aref-scene", "unit_system": "METERS"},
    datablocks=[{"db_key": "DB1", "db_name": "atlas-target",
                 "vertices": B1_VERTS, "faces": B1_FACES}],
    objects=[{"object_id": "atlas-target", "datablock_key": "DB1", "type": "MESH"},
             {"object_id": "atlas-unrelated", "datablock_key": "DB1", "type": "MESH"}],
    expected={},
)


def run_attempt() -> Dict[str, Any]:
    build_scene_from_spec(ALIASED_SPEC)
    payload = extract_scene(bpy)
    scene = payload_to_scene_model(payload)
    report = run_scene_health(scene, soccer_field_profile_default())
    outcome = aref_plan.real_merge_plan(report, payload)
    merge_findings = [f for f in report.findings if f.code.value == "MESH_DUPLICATE_VERTEX"]
    scopes = sorted({(f.object_id, f.mesh_id) for f in merge_findings})
    return {
        "status": "ATTEMPTED",
        "stage": "ALIASED-MERGE-ATTEMPT",
        "scene": {"objects": ["atlas-target", "atlas-unrelated"],
                  "shared_datablock": "atlas-target",
                  "duplicate_vertex_findings": len(merge_findings),
                  "scopes": [list(s) for s in scopes]},
        "merge_pass": {"refusal_code": outcome.refusal_code,
                       "refusal_detail": outcome.refusal_detail,
                       "corrections": len(outcome.plan.corrections),
                       "plan_state": outcome.plan.state},
        "conclusion": ("more than one target scope is refused by the planner rather than "
                       "aggregated, so no aliased single-correction merge plan exists; the C4 "
                       "aliasing question is answered by source (MQ-6) + this live attempt"),
    }
