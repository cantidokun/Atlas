"""Read-only non-manifold evidence boundary v1: deterministic offline contract gate.

This gate deliberately exercises the existing finding kernel, independent topology intelligence,
and correction planner without changing any production contract or adding a correction.
"""

import hashlib
import json

from planning.blender.correction_codes import PlannerState
from planning.blender.correction_planner import plan_scene_report
from planning.blender.finding_codes import FindingCode, FindingSeverity
from planning.blender.mesh_health import check_mesh
from planning.blender.scene_model import MeshModel
from planning.blender.scene_report import REPORT_FORMAT_VERSION, Finding, build_report
from planning.blender.topology_intelligence import analyze_topology


def _mesh(name, faces, vertex_count):
    vertices = tuple((float(i), float((i * 7) % 11), float((i * 13) % 17)) for i in range(vertex_count))
    # Replace generated coordinates with deterministic non-collinear fixtures below.
    return MeshModel(mesh_id=name, vertices=vertices, faces=tuple(tuple(f) for f in faces))


def _valence_mesh(valence):
    faces = []
    for i in range(valence):
        # All triangles share edge (0,1), with a distinct third vertex.
        faces.append((0, 1, 2 + i))
    vertices = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        *tuple((0.2 + 0.1 * i, 1.0 + 0.2 * i, 0.5 + 0.1 * i) for i in range(valence)),
    )
    return MeshModel(mesh_id=f"v{valence}", vertices=vertices, faces=tuple(faces))


def _non_manifold_two_edge_mesh():
    faces = (
        (0, 1, 2), (0, 1, 3), (0, 1, 4),
        (5, 6, 7), (5, 6, 8), (5, 6, 9),
    )
    vertices = (
        (0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1),
        (10, 0, 0), (11, 0, 0), (10, 1, 0), (10, 0, 1), (11, 1, 1),
    )
    return MeshModel(mesh_id="two_nm", vertices=vertices, faces=faces)


def _report_payload(findings):
    report = build_report(
        scene_id="nm-discovery",
        validation_state="needs_review",
        findings=findings,
        scene_metrics={},
        profile_name="soccer-field",
    )
    body = report.to_json_compatible()
    body["report_format_version"] = REPORT_FORMAT_VERSION
    body.pop("digest", None)
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return {**body, "digest": digest}


def test_valence_matrix_1_2_3_4():
    # Boundary valence 1 is not a finding; manifold valence 2 is not a finding;
    # non-manifold begins strictly above 2.
    for valence in (1, 2, 3, 4):
        mesh = _valence_mesh(valence)
        findings = [f for f in check_mesh(mesh) if f.code is FindingCode.MESH_NON_MANIFOLD_EDGE]
        assert bool(findings) is (valence > 2)
        if findings:
            assert len(findings) == 1
            assert findings[0].measured == {"edge": [0, 1], "face_incidence": valence}
            assert findings[0].expected == {"face_incidence": 2}
            assert findings[0].severity is FindingSeverity.WARNING


def test_two_non_manifold_edges_are_stably_ordered():
    findings = [
        f for f in check_mesh(_non_manifold_two_edge_mesh())
        if f.code is FindingCode.MESH_NON_MANIFOLD_EDGE
    ]
    assert [f.measured["edge"] for f in findings] == [[0, 1], [5, 6]]
    assert [f.measured["face_incidence"] for f in findings] == [3, 3]


def test_boundary_and_closed_manifold_negative_controls():
    boundary = MeshModel(
        mesh_id="boundary",
        vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0)),
        faces=((0, 1, 2),),
    )
    tetra = MeshModel(
        mesh_id="closed",
        vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)),
        faces=((0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)),
    )
    for mesh in (boundary, tetra):
        assert not [f for f in check_mesh(mesh) if f.code is FindingCode.MESH_NON_MANIFOLD_EDGE]


def test_duplicate_face_is_not_non_manifold():
    mesh = MeshModel(
        mesh_id="dup",
        vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0)),
        faces=((0, 1, 2), (0, 1, 2)),
    )
    findings = check_mesh(mesh)
    assert not [f for f in findings if f.code is FindingCode.MESH_NON_MANIFOLD_EDGE]
    assert any(f.code is FindingCode.MESH_DUPLICATE_FACE for f in findings)


def test_quad_triangle_shared_edge_is_not_non_manifold():
    mesh = MeshModel(
        mesh_id="quadtri",
        vertices=((0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0), (1, 1, 1)),
        faces=((0, 1, 2, 3), (0, 1, 4)),
    )
    assert not [f for f in check_mesh(mesh) if f.code is FindingCode.MESH_NON_MANIFOLD_EDGE]


def test_finding_and_topology_metric_cohere():
    mesh = _non_manifold_two_edge_mesh()
    finding_count = len([f for f in check_mesh(mesh) if f.code is FindingCode.MESH_NON_MANIFOLD_EDGE])
    topology = analyze_topology(mesh)
    assert finding_count == topology.non_manifold_edge_count
    histogram = dict(topology.edge_valence_histogram)
    assert sum(v for k, v in histogram.items() if k > 2) == finding_count


def test_non_manifold_finding_never_proposes_correction():
    finding = Finding(
        code=FindingCode.MESH_NON_MANIFOLD_EDGE,
        mesh_id="m",
        measured={"edge": [0, 1], "face_incidence": 3},
        expected={"face_incidence": 2},
    )
    plan = plan_scene_report(_report_payload([finding]), profile={
        "name": "soccer-field", "version": "1",
        "allowed_units": ["METERS", "meters", "m"],
        "name_pattern": r"^[a-z0-9][a-z0-9._-]*$",
    })
    assert plan.corrections == ()
    assert plan.state == PlannerState.REVIEW_REQUIRED.value
    assert not any(c.finding_code == FindingCode.MESH_NON_MANIFOLD_EDGE.value for c in plan.corrections)


def test_positive_planner_control_is_human_review_gated():
    finding = Finding(
        code=FindingCode.OBJECT_NAME_INVALID,
        object_id="Bad Name!",
        measured={"name": "Bad Name!"},
        expected={"pattern": r"^[a-z0-9][a-z0-9._-]*$"},
    )
    plan = plan_scene_report(_report_payload([finding]), profile={
        "name": "soccer-field", "version": "1",
        "allowed_units": ["METERS", "meters", "m"],
        "name_pattern": r"^[a-z0-9][a-z0-9._-]*$",
    })
    assert plan.state == PlannerState.REVIEW_REQUIRED.value
    assert len(plan.corrections) >= 1
    assert any(
        c.correction_type == "RENAME_OBJECT" and c.requires_human_review
        for c in plan.corrections
    )


def test_deterministic_digest_repeats():
    mesh = _non_manifold_two_edge_mesh()
    findings_a = check_mesh(mesh)
    findings_b = check_mesh(mesh)
    assert [f.snapshot() for f in findings_a] == [f.snapshot() for f in findings_b]
    topology_a = analyze_topology(mesh).to_dict()
    topology_b = analyze_topology(mesh).to_dict()
    assert topology_a == topology_b
