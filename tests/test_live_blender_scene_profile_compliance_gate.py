"""Operator-gated Blender 4.4.3 scene/profile compliance evidence boundary v1.

Design authority: PR #126, design head b35acec7c962a6e9f7b875fed7e9874402c02694.
This gate is evidence-only. It never saves, repairs, authorizes, retries, or mutates a source asset.
"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

EXPECTED_BLENDER = (4, 4, 3)
MARKER = "ATLAS_SCENE_PROFILE_COMPLIANCE_V1"
REQUIRED_CASES = (
    "A01_clean",
    "A02_collection",
    "A03_name",
    "A04_unit",
    "A05_zero_scale",
    "A06_dangling_parent",
    "A07_upper_exact",
    "A08_upper_ulp",
    "A09_lower_exact",
    "A10_lower_ulp",
    "A11_missing_role",
    "A12_overlap",
    "A13_containment",
    "A14_coincident",
    "A15_x_flush",
    "A16_yz_flush",
    "A17_rotated_aabb",
)


def _live_enabled():
    return os.environ.get("ATLAS_RUN_LIVE_BLENDER", "") == "1"


pytestmark = pytest.mark.skipif(
    not _live_enabled(), reason="set ATLAS_RUN_LIVE_BLENDER=1 to run the live Blender gate"
)


def _blender_executable():
    return os.environ.get("ATLAS_BLENDER_EXECUTABLE") or shutil.which("blender")


def _repo_root():
    return Path(__file__).resolve().parents[1]


def _git_sha(repo):
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), text=True
    ).strip()


def _script():
    return r'''
import bpy
import hashlib
import json
import math
import os
import pathlib
import sys

REPO = os.environ["ATLAS_REPO_ROOT"]
sys.path.insert(0, REPO)

from planning.blender.bpy_extraction import extract_scene
from planning.blender.extraction_payload import payload_to_scene_model
from planning.blender.kernel import run_scene_health, soccer_field_profile_default
from planning.blender.finding_codes import FindingCode
from planning.blender.scene_report import REPORT_FORMAT_VERSION, VALIDATOR_VERSION

MARKER = "ATLAS_SCENE_PROFILE_COMPLIANCE_V1"

def reset_scene():
    # Each case is independent; restore scene policy state after unit-policy cases.
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.length_unit = "METERS"
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.meshes, bpy.data.curves, bpy.data.materials,
        bpy.data.cameras, bpy.data.lights,
    ):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)
    for c in list(bpy.data.collections):
        if c.name != "Collection" and c.users == 0:
            bpy.data.collections.remove(c)
    root = bpy.context.scene.collection
    for c in list(root.children):
        root.children.unlink(c)

def collection(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
    if c.name not in {x.name for x in bpy.context.scene.collection.children}:
        bpy.context.scene.collection.children.link(c)
    return c

def mesh_object(name, verts, faces, coll):
    me = bpy.data.meshes.new(name + "_Mesh")
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob

def empty(name, coll):
    ob = bpy.data.objects.new(name, None)
    coll.objects.link(ob)
    return ob

def add_roles(field, goals):
    pitch = mesh_object(
        "pitch",
        [(-20,-20,0), (-19,-20,0), (-20,-19,0)],
        [(0,1,2)],
        field,
    )
    empty("goal_left", goals)
    empty("goal_right", goals)
    return pitch

def snapshot():
    rows = []
    for ob in sorted(bpy.context.scene.objects, key=lambda x: x.name):
        mesh = getattr(ob, "data", None) if ob.type == "MESH" else None
        verts = []
        faces = []
        if mesh is not None:
            verts = [
                [round(float(v.co.x), 7), round(float(v.co.y), 7), round(float(v.co.z), 7)]
                for v in mesh.vertices
            ]
            faces = [list(p.vertices) for p in mesh.polygons]
        cols = sorted(c.name for c in ob.users_collection)
        rows.append({
            "name": ob.name,
            "type": ob.type,
            "location": [round(float(x), 7) for x in ob.location],
            "rotation": [round(float(x), 7) for x in ob.rotation_euler],
            "scale": [round(float(x), 7) for x in ob.scale],
            "parent": ob.parent.name if ob.parent else None,
            "collections": cols,
            "verts": verts,
            "faces": faces,
        })
    return {
        "objects": rows,
        "scene_unit_system": bpy.context.scene.unit_settings.system,
        "scene_length_unit": bpy.context.scene.unit_settings.length_unit,
        "collections": sorted(c.name for c in bpy.data.collections),
        "mesh_datablocks": sorted(m.name for m in bpy.data.meshes),
    }

def effective_profile():
    from planning.blender.soccer_field_profile import soccer_field_profile
    p = soccer_field_profile()
    return {
        "name": p.name,
        "envelope_min": list(p.envelope_min),
        "envelope_max": list(p.envelope_max),
        "allowed_units": sorted(p.allowed_units),
        "name_pattern": p.name_pattern.pattern if p.name_pattern else None,
        "allowed_collections": sorted(p.allowed_collections or ()),
        "required_object_roles": list(p.required_object_roles),
        "ready_blocking_codes": sorted(c.value for c in p.ready_blocking_codes),
        "permitted_hierarchy_depth": p.permitted_hierarchy_depth,
        "expected_up_axis": p.expected_up_axis,
        "expected_ground_level": p.expected_ground_level,
        "tolerance_bounds_metres": p.tolerance_bounds_metres,
    }

def _polygon_disjoint_2d(poly_a, poly_b):
    """Independent fixture-truth check; intentionally not the production AABB predicate."""
    def axes(poly):
        for i, point in enumerate(poly):
            other = poly[(i + 1) % len(poly)]
            edge_x = other[0] - point[0]
            edge_y = other[1] - point[1]
            yield (-edge_y, edge_x)

    def project(poly, axis):
        values = [point[0] * axis[0] + point[1] * axis[1] for point in poly]
        return min(values), max(values)

    for axis in list(axes(poly_a)) + list(axes(poly_b)):
        min_a, max_a = project(poly_a, axis)
        min_b, max_b = project(poly_b, axis)
        if max_a < min_b or max_b < min_a:
            return True
    return False


def _world_xy(ob):
    return [[
        float((ob.matrix_world @ v.co).x),
        float((ob.matrix_world @ v.co).y),
    ] for v in ob.data.vertices]


def evaluate(case_id):
    reset_scene()
    field = collection("Field")
    goals = collection("Goals")
    misc = collection("Misc")
    add_roles(field, goals)

    if case_id == "A02_collection":
        mesh_object("collection_probe", [(10,0,0),(11,0,0),(10,1,0)], [(0,1,2)], misc)
    elif case_id == "A03_name":
        mesh_object("Bad Name!", [(10,0,0),(11,0,0),(10,1,0)], [(0,1,2)], field)
    elif case_id == "A04_unit":
        bpy.context.scene.unit_settings.system = "IMPERIAL"
    elif case_id == "A05_zero_scale":
        ob = mesh_object("scale_probe", [(10,0,0),(11,0,0),(10,1,0)], [(0,1,2)], field)
        ob.scale = (0.0, 1.0, 1.0)
    elif case_id == "A06_dangling_parent":
        child = mesh_object("dangling_child", [(10,0,0),(11,0,0),(10,1,0)], [(0,1,2)], field)
        ghost = bpy.data.objects.new("ghost", None)
        child.parent = ghost
    elif case_id in ("A07_upper_exact", "A08_upper_ulp", "A09_lower_exact", "A10_lower_ulp"):
        if case_id == "A07_upper_exact":
            x = 50.05
        elif case_id == "A08_upper_ulp":
            x = 50.05000305175781
        elif case_id == "A09_lower_exact":
            x = -50.05
        else:
            x = -50.05000305175781
        mesh_object("envelope_probe", [(x,0,1),(x,0.1,1),(x,0,1.1)], [(0,1,2)], field)
    elif case_id == "A11_missing_role":
        # Deliberately omit goal_right.
        for ob in list(bpy.data.objects):
            if ob.name == "goal_right":
                bpy.data.objects.remove(ob, do_unlink=True)
    elif case_id in ("A12_overlap", "A13_containment", "A14_coincident", "A15_x_flush", "A16_yz_flush", "A17_rotated_aabb"):
        if case_id == "A12_overlap":
            a = [(0,0,1),(1,0,1),(1,1,1),(0,1,1)]
            b = [(0.75,0,1),(1.75,0,1),(1.75,1,1),(0.75,1,1)]
            mesh_object("a", a, [(0,1,2,3)], field)
            mesh_object("b", b, [(0,1,2,3)], field)
        elif case_id == "A13_containment":
            mesh_object("a", [(0,0,1),(4,0,1),(4,4,1),(0,4,1)], [(0,1,2,3)], field)
            mesh_object("b", [(1,1,1),(2,1,1),(2,2,1),(1,2,1)], [(0,1,2,3)], field)
        elif case_id == "A14_coincident":
            verts = [(0,0,1),(1,0,1),(1,1,1),(0,1,1)]
            mesh_object("a", verts, [(0,1,2,3)], field)
            mesh_object("b", verts, [(0,1,2,3)], field)
        elif case_id == "A15_x_flush":
            mesh_object("a", [(0,0,1),(1,0,1),(1,1,1),(0,1,1)], [(0,1,2,3)], field)
            mesh_object("b", [(1,0,1),(2,0,1),(2,1,1),(1,1,1)], [(0,1,2,3)], field)
        elif case_id == "A16_yz_flush":
            mesh_object("a", [(0,0,1),(2,0,1),(2,1,1),(0,1,1)], [(0,1,2,3)], field)
            mesh_object("b", [(0,1,1),(2,1,1),(2,2,1),(0,2,1)], [(0,1,2,3)], field)
        else:
            # Deliberately disjoint oriented geometry whose axis-aligned bounds overlap.
            # The rotated square is centered at (1.6, 1.6), so its nearest vertex is
            # approximately (0.893, 1.6): outside the anchor [0,1] x [0,1].
            a = [(0,0,1),(1,0,1),(1,1,1),(0,1,1)]
            b = [(-0.5,-0.5,0),(0.5,-0.5,0),(0.5,0.5,0),(-0.5,0.5,0)]
            mesh_object("anchor", a, [(0,1,2,3)], field)
            ob = mesh_object("rotated", b, [(0,1,2,3)], field)
            ob.location = (1.6, 1.6, 1.0)
            ob.rotation_euler[2] = math.radians(45)

    before = snapshot()
    payload = extract_scene(bpy)
    scene = payload_to_scene_model(payload)
    profile = soccer_field_profile_default()
    report = run_scene_health(scene, profile, include_envelope=True)
    after = snapshot()

    findings = [f.snapshot() for f in report.findings]
    codes = sorted({f.code.value for f in report.findings})
    result = {
        "case": case_id,
        "finding_codes": codes,
        "findings": findings,
        "validation_state": report.validation_state,
        "readiness_reason": report.scene_metrics.get("readiness_reason"),
        "input_digest": report.input_digest,
        "report_digest": report.digest(),
        "payload_schema_version": payload["schema_version"],
        "profile": effective_profile(),
        "read_only_equal": before == after,
    }
    if case_id == "A17_rotated_aabb":
        anchor = bpy.data.objects["anchor"]
        rotated = bpy.data.objects["rotated"]
        anchor_xy = _world_xy(anchor)
        rotated_xy = _world_xy(rotated)
        result["fixture_truth"] = {
            "oriented_geometry_disjoint": _polygon_disjoint_2d(anchor_xy, rotated_xy),
            "aabb_overlap_expected": True,
            "anchor_world_xy": anchor_xy,
            "rotated_world_xy": rotated_xy,
        }
    return result

def main():
    cases = []
    for case_id in (
        "A01_clean","A02_collection","A03_name","A04_unit","A05_zero_scale",
        "A06_dangling_parent","A07_upper_exact","A08_upper_ulp","A09_lower_exact",
        "A10_lower_ulp","A11_missing_role","A12_overlap","A13_containment",
        "A14_coincident","A15_x_flush","A16_yz_flush","A17_rotated_aabb"
    ):
        cases.append(evaluate(case_id))

    # Engine identity is captured once from the actual Blender runtime.
    engine = {
        "version_string": bpy.app.version_string,
        "version": list(bpy.app.version),
        "build_hash": bpy.app.build_hash.decode() if isinstance(bpy.app.build_hash, bytes) else str(bpy.app.build_hash),
        "build_date": bpy.app.build_date.decode() if isinstance(bpy.app.build_date, bytes) else str(bpy.app.build_date),
    }
    out = {
        "marker": MARKER,
        "git_sha": os.environ["ATLAS_GIT_SHA"],
        "engine": engine,
        "validator_version": VALIDATOR_VERSION,
        "report_format_version": REPORT_FORMAT_VERSION,
        "cases": cases,
    }
    print(json.dumps(out, sort_keys=True))
    print(MARKER + "_PASS")

if __name__ == "__main__":
    main()
'''


def _blend_artifact_inventory(repo, temp_dir):
    roots = {
        "repo": repo,
        "temp": temp_dir,
    }
    inventory = {}
    for label, root in roots.items():
        paths = []
        for suffix in ("*.blend", "*.blend1"):
            for path in root.rglob(suffix):
                if path.is_file():
                    paths.append(str(path.resolve()))
        inventory[label] = sorted(set(paths))
    return inventory


def test_live_scene_profile_compliance_boundary():
    executable = _blender_executable()
    if not executable:
        pytest.fail("Blender executable not found; set ATLAS_BLENDER_EXECUTABLE")

    repo = _repo_root()
    sha = _git_sha(repo)
    script_path = Path(tempfile.gettempdir()) / "atlas_scene_profile_compliance_v1_live.py"
    script_path.write_text(_script(), encoding="utf-8")

    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("ATLAS_") and key != "PYTHONPATH"
    }
    env["ATLAS_REPO_ROOT"] = str(repo)
    env["ATLAS_GIT_SHA"] = sha

    temp_dir = Path(tempfile.gettempdir())
    artifacts_before = _blend_artifact_inventory(repo, temp_dir)

    completed = subprocess.run(
        [
            executable,
            "--background",
            "--python-exit-code",
            "1",
            "--python",
            str(script_path),
        ],
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    combined = completed.stdout + "\n" + completed.stderr
    artifacts_after = _blend_artifact_inventory(repo, temp_dir)
    assert completed.returncode == 0, combined
    assert artifacts_after == artifacts_before, {
        "before": artifacts_before,
        "after": artifacts_after,
    }

    payload = None
    for line in completed.stdout.splitlines():
        if line.startswith("{") and '"marker"' in line:
            payload = json.loads(line)
            break
    assert payload is not None, combined
    assert tuple(payload["engine"]["version"]) == EXPECTED_BLENDER
    assert payload["git_sha"] == sha
    assert payload["validator_version"] == "1"
    assert payload["report_format_version"] == "1"
    assert [c["case"] for c in payload["cases"]] == list(REQUIRED_CASES)
    assert all(c["read_only_equal"] for c in payload["cases"])

    by_case = {c["case"]: c for c in payload["cases"]}
    assert by_case["A01_clean"]["finding_codes"] == []
    assert by_case["A01_clean"]["validation_state"] == "production_ready"

    assert by_case["A02_collection"]["finding_codes"] == ["OBJECT_COLLECTION_INVALID"]
    assert by_case["A03_name"]["finding_codes"] == ["OBJECT_NAME_INVALID"]
    assert by_case["A04_unit"]["finding_codes"] == ["SCENE_UNIT_INVALID"]
    assert by_case["A05_zero_scale"]["finding_codes"] == ["OBJECT_TRANSFORM_INVALID"]
    assert by_case["A06_dangling_parent"]["finding_codes"] == ["OBJECT_HIERARCHY_INVALID"]

    assert by_case["A07_upper_exact"]["finding_codes"] == []
    assert by_case["A08_upper_ulp"]["finding_codes"] == ["MESH_SCALE_OUT_OF_RANGE"]
    assert by_case["A09_lower_exact"]["finding_codes"] == []
    assert by_case["A10_lower_ulp"]["finding_codes"] == ["MESH_SCALE_OUT_OF_RANGE"]

    assert by_case["A11_missing_role"]["finding_codes"] == []
    assert by_case["A11_missing_role"]["validation_state"] == "needs_review"
    assert "missing required roles: goal_right" == by_case["A11_missing_role"]["readiness_reason"]

    assert by_case["A12_overlap"]["finding_codes"] == ["OBJECT_BOUNDS_OVERLAP"]
    assert by_case["A13_containment"]["finding_codes"] == []
    assert by_case["A14_coincident"]["finding_codes"] == []
    assert by_case["A15_x_flush"]["finding_codes"] == []
    assert by_case["A16_yz_flush"]["finding_codes"] == ["OBJECT_BOUNDS_OVERLAP"]
    assert by_case["A17_rotated_aabb"]["finding_codes"] == ["OBJECT_BOUNDS_OVERLAP"]
    assert by_case["A17_rotated_aabb"]["fixture_truth"]["oriented_geometry_disjoint"] is True
    assert by_case["A17_rotated_aabb"]["fixture_truth"]["aabb_overlap_expected"] is True

    # Exact measured evidence for the primary NEW findings.
    assert by_case["A02_collection"]["findings"][0]["measured"]["collection"] == "Misc"
    assert by_case["A03_name"]["findings"][0]["measured"]["name"] == "Bad Name!"
    assert by_case["A04_unit"]["findings"][0]["measured"]["unit_system"] == "FEET"
    assert by_case["A05_zero_scale"]["findings"][0]["measured"]["scale"] == [0.0, 1.0, 1.0]
    assert by_case["A06_dangling_parent"]["findings"][0]["measured"]["parent"] == "ghost"

    for case in ("A08_upper_ulp", "A10_lower_ulp"):
        f = by_case[case]["findings"][0]
        assert f["mesh_id"] == "envelope_probe"
        assert f["expected"]["tolerance"] == 0.05

    assert "DIGITAL_TWIN_READINESS_FAILED" not in by_case["A11_missing_role"]["finding_codes"]

    # Profile identity must contain the effective policy, not merely the profile name.
    profile = by_case["A01_clean"]["profile"]
    assert profile["envelope_min"] == [-50.0, -40.0, 0.0]
    assert profile["envelope_max"] == [50.0, 40.0, 12.0]
    assert profile["allowed_units"] == ["METERS", "m", "meters"]
    assert profile["allowed_collections"] == ["Field", "Goals", "Players", "Sidelines", "Structure"]
    assert profile["required_object_roles"] == ["pitch", "goal_left", "goal_right"]
    assert profile["tolerance_bounds_metres"] == 0.05

    # Complete final evidence on the host side, including the no-artifact inventory.
    payload["artifact_inventory"] = {
        "before": artifacts_before,
        "after": artifacts_after,
        "no_new_blend_or_blend1": artifacts_before == artifacts_after,
    }
    evidence_bytes = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    evidence_sha256 = hashlib.sha256(evidence_bytes).hexdigest()

    evidence_path = Path(tempfile.gettempdir()) / f"atlas_scene_profile_compliance_v1_{sha[:12]}.json"
    evidence_path.write_bytes(evidence_bytes)
    assert evidence_path.read_bytes() == evidence_bytes
    assert hashlib.sha256(evidence_path.read_bytes()).hexdigest() == evidence_sha256

    manifest = {
        "evidence_file": str(evidence_path),
        "evidence_sha256": evidence_sha256,
        "hash_recipe": {
            "encoding": "utf-8",
            "serialization": "json.dumps(payload, sort_keys=True, separators=(',', ':'))",
            "hashed_bytes_are_persisted_exactly": True,
            "self_field_excluded": True,
        },
    }
    manifest_path = evidence_path.with_suffix(".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8"
    )

    print("ATLAS_SCENE_PROFILE_EVIDENCE=" + str(evidence_path))
    print("ATLAS_SCENE_PROFILE_EVIDENCE_SHA256=" + evidence_sha256)
    print("ATLAS_SCENE_PROFILE_EVIDENCE_MANIFEST=" + str(manifest_path))
    print(MARKER + "_PASS")
