"""Disposable Blender gate for Read-Only Non-Manifold Evidence Boundary v1."""
from collections import Counter
import json
from pathlib import Path
import sys

# Blender starts this script with the tests directory as its script path. Resolve the repository
# root explicitly so this gate is hermetic and does not depend on ambient PYTHONPATH.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import bpy

from planning.blender.bpy_extraction import extract_scene
from planning.blender.correction_codes import PlannerState
from planning.blender.correction_mapping import _TABLE
from planning.blender.correction_planner import plan_scene_report
from planning.blender.correction_executor import _EXECUTABLE_TYPES
from planning.blender.finding_codes import FindingCode
from planning.blender.kernel import run_scene_health
from planning.blender.mesh_health import check_mesh
from planning.blender.soccer_field_profile import soccer_field_profile
from planning.blender.extraction_payload import payload_to_scene_model
from planning.blender.topology_intelligence import analyze_topology

EXPECTED_BLENDER = (4, 4, 3)
MARKER = "ATLAS_READONLY_NON_MANIFOLD_V1_LIVE"
EXPECTED_EXECUTOR_TYPES = frozenset({
    "REMOVE_DUPLICATE_FACE",
    "REMOVE_DEGENERATE_FACE",
    "REPAIR_FACE_WINDING",
    "REPAIR_MERGE_VERTEX",
})


def profile():
    # Keep the real dimensional envelope and allowed-collection policy. Required semantic roles
    # are intentionally disabled because this disposable topology fixture is not a soccer-field
    # production scene; the evidence under test is the topology boundary itself.
    return soccer_field_profile(required_object_roles=())


def add(name, verts, faces, x, collection):
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.location = (x, 0, 0)
    return obj


def independent_incidence(polygons):
    counts = Counter()
    for face in polygons:
        for a, b in zip(face, face[1:] + face[:1]):
            edge = tuple(sorted((int(a), int(b))))
            counts[edge] += 1
    return sorted((list(edge), count) for edge, count in counts.items() if count > 2)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    field = bpy.data.collections.new("Field")
    scene.collection.children.link(field)

    specs = [
        ("nm_v1_boundary", [(0,0,0),(1,0,0),(0,1,0)], [(0,1,2)], 0),
        ("nm_v2_manifold", [(0,0,0),(1,0,0),(0,1,0),(0,0,1)], [(0,2,1),(1,2,3)], 5),
        ("nm_v3_edge3", [(0,0,0),(1,0,0),(.2,1,.5),(.3,1.2,.7),(.4,1.4,.9)], [(0,1,2),(0,1,3),(0,1,4)], 10),
        ("nm_v4_edge4", [(0,0,0),(1,0,0),(.2,1,.5),(.3,1.2,.7),(.4,1.4,.9),(.5,1.6,1.1)], [(0,1,2),(0,1,3),(0,1,4),(0,1,5)], 15),
        ("nm_clean_control", [(0,0,0),(1,0,0),(0,1,0),(0,0,1)], [(0,2,1),(0,1,3),(1,2,3),(2,0,3)], 20),
        ("nm_two_nm_edges", [(0,0,0),(1,0,0),(0,1,0),(0,0,1),(1,1,1),(5,0,0),(6,0,0),(5,1,0),(5,0,1),(6,1,1)], [(0,1,2),(0,1,3),(0,1,4),(5,6,7),(5,6,8),(5,6,9)], 25),
        ("nm_quadtri_control", [(0,0,0),(2,0,0),(2,2,0),(0,2,0),(1,1,1)], [(0,1,2,3),(1,0,4)], 35),
    ]

    objs = [add(*spec, field) for spec in specs]
    bpy.context.view_layer.update()

    before = {
        o.name: (
            tuple(tuple(float(c) for c in v.co) for v in o.data.vertices),
            tuple(tuple(int(i) for i in p.vertices) for p in o.data.polygons),
        )
        for o in objs
    }

    checks = {}
    for o, spec in zip(objs, specs):
        checks[o.name + "_raw_faces"] = (
            tuple(tuple(int(i) for i in p.vertices) for p in o.data.polygons)
            == tuple(tuple(f) for f in spec[2])
        )

    pa = extract_scene(bpy)
    pb = extract_scene(bpy)
    checks["repeatable_extraction"] = pa == pb

    scene_model = payload_to_scene_model(pa)
    by = {o.object_id: o for o in scene_model.objects}

    expected = {
        "nm_v1_boundary": [],
        "nm_v2_manifold": [],
        "nm_v3_edge3": [([0,1], 3)],
        "nm_v4_edge4": [([0,1], 4)],
        "nm_clean_control": [],
        "nm_two_nm_edges": [([0,1], 3), ([5,6], 3)],
        "nm_quadtri_control": [],
    }

    for name, exp in expected.items():
        mesh = by[name].mesh
        assert mesh is not None
        checks[name + "_canonical_faces"] = (
            tuple(mesh.faces)
            == tuple(tuple(f) for f in next(s[2] for s in specs if s[0] == name))
        )
        findings = check_mesh(mesh)
        nm = [
            (f.measured["edge"], f.measured["face_incidence"])
            for f in findings
            if f.code is FindingCode.MESH_NON_MANIFOLD_EDGE
        ]
        checks[name + "_finding"] = nm == exp
        checks[name + "_no_extra_findings"] = [
            f.code.value
            for f in findings
            if f.code is not FindingCode.MESH_NON_MANIFOLD_EDGE
        ] == []
        topo = analyze_topology(mesh)
        checks[name + "_metric_coherence"] = (
            topo.non_manifold_edge_count == len(nm)
            and sum(v for k, v in topo.edge_valence_histogram if k > 2) == len(nm)
        )
        report = run_scene_health(scene_model, profile(), include_envelope=True)
        plan = plan_scene_report(report.to_json_compatible() | {"digest": report.digest()}, profile=profile().__dict__)
        # Per-mesh planner state is intentionally evaluated from the actual scene report below;
        # this local check only proves the topology finding itself never maps to a correction.
        checks[name + "_planner_no_correction"] = not any(
            c.correction_type == "FLAG_NON_MANIFOLD_FOR_REVIEW"
            for c in plan.corrections
        )
        checks[name + "_planner_state"] = (
            plan.state in {
                PlannerState.REVIEW_REQUIRED.value,
                PlannerState.AUTO_PROPOSALS_AVAILABLE.value,
                PlannerState.NO_CORRECTIONS.value,
            }
        )

    report_a = run_scene_health(scene_model, profile(), include_envelope=True)
    report_b = run_scene_health(scene_model, profile(), include_envelope=True)
    report_a_json = report_a.to_json_compatible()
    report_b_json = report_b.to_json_compatible()
    checks["scene_report_digest_repeatable"] = report_a.digest() == report_b.digest()
    checks["scene_input_digest_repeatable"] = (
        report_a.input_digest == report_b.input_digest and report_a.input_digest is not None
    )

    intended = {
        FindingCode.MESH_NON_MANIFOLD_EDGE.value: 4,
    }
    actual_counts = Counter(f.code.value for f in report_a.findings)
    checks["scene_report_no_unexpected_findings"] = (
        actual_counts == intended
        and all(f.severity.value == "warning" for f in report_a.findings)
    )

    scene_plan = plan_scene_report(
        {**report_a_json, "digest": report_a.digest()},
        profile=profile().__dict__,
    )
    checks["scene_report_planner_no_correction"] = (
        scene_plan.corrections == ()
        and not any(
            c.finding_code == FindingCode.MESH_NON_MANIFOLD_EDGE.value
            for c in scene_plan.corrections
        )
    )
    checks["scene_report_planner_state"] = scene_plan.state == PlannerState.REVIEW_REQUIRED.value

    row = _TABLE[FindingCode.MESH_NON_MANIFOLD_EDGE]
    checks["mapping_row_frozen"] = (
        row.determinism.value == "REQUIRES_REVIEW"
        and row.correction_type == "FLAG_NON_MANIFOLD_FOR_REVIEW"
        and row.auto_propose is False
    )
    checks["executor_allowlist_frozen"] = _EXECUTABLE_TYPES == EXPECTED_EXECUTOR_TYPES

    raw_expected = {
        name: independent_incidence(spec[2])
        for name, spec in ((s[0], s) for s in specs)
    }
    checks["raw_incidence_independent"] = all(
        [
            raw_expected[name] == expected[name]
            for name in expected
        ]
    )
    checks["independent_v3_incidence"] = raw_expected["nm_v3_edge3"] == [([0,1], 3)]
    checks["independent_v4_incidence"] = raw_expected["nm_v4_edge4"] == [([0,1], 4)]
    checks["independent_two_edge_incidence"] = raw_expected["nm_two_nm_edges"] == [([0,1], 3), ([5,6], 3)]

    checks["finding_scope"] = all(
        f.mesh_id in expected and f.object_id is None
        for f in report_a.findings
        if f.code is FindingCode.MESH_NON_MANIFOLD_EDGE
    )

    after = {
        o.name: (
            tuple(tuple(float(c) for c in v.co) for v in o.data.vertices),
            tuple(tuple(int(i) for i in p.vertices) for p in o.data.polygons),
        )
        for o in objs
    }
    checks["no_post_validation_mutation"] = before == after
    checks["no_save"] = bpy.data.filepath == ""
    checks["fixture_count_stable"] = len(tuple(scene.objects)) == len(objs)

    # These are derived from observed Blender state, not hard-coded claims.
    checks["scene_report_input_digest_matches_model"] = report_a.input_digest == report_b.input_digest

    failed = [k for k, v in checks.items() if v is not True]
    passed = len(checks) - len(failed)
    payload = {
        "marker": MARKER,
        "blender_version": tuple(bpy.app.version),
        "blender_build_hash": getattr(bpy.app, "build_hash", ""),
        "required_assertions": len(checks),
        "passed": passed,
        "failed": failed,
        "checks": checks,
        "save_attempted": bpy.data.filepath != "",
        "opened_frozen_asset": False,
    }
    print(json.dumps(payload, sort_keys=True))
    if failed:
        return 1
    print(f"{MARKER}_PASS {passed} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
