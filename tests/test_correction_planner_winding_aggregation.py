"""Deterministic tests for the WAVE-2 planner-side winding aggregation (design §2).

The planner — not the executor — owns aggregation. These tests pin the exact Rev-3 rules:
per-mesh grouping, the canonical finding identity, D1/D2/D3, canonical parameter ordering, the
suppression of per-finding winding proposals, determinism, and the fail-closed handling of malformed
or ungroupable winding findings.
"""
import copy
import json

import pytest

from planning.blender.correction_planner import (
    WINDING_ORIENTATION,
    WINDING_PARAMETER_KEYS,
    plan_scene_report,
)
from planning.blender.correction_values import CorrectionInputError, thaw_jsonable
from planning.blender.extraction_payload import PAYLOAD_SCHEMA_VERSION, payload_to_scene_model
from planning.blender.finding_codes import FindingCode
from planning.blender.kernel import run_scene_health, soccer_field_profile_default
from planning.blender.scene_report import REPORT_FORMAT_VERSION, Finding, build_report
from planning.blender.correction_codes import PlannerState

WINDING = "REPAIR_FACE_WINDING"
PROFILE = {
    "name": "soccer-field", "version": "1",
    "allowed_units": ["METERS", "meters", "m"], "name_pattern": r"^[a-z0-9][a-z0-9._-]*$",
}
Q = ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1))
Q6 = Q + ((0, -1, 1),)


# ---------------------------------------------------------------------------
# helpers: hand-made reports (planner input data) and real kernel reports
# ---------------------------------------------------------------------------

def _winding_finding(edge, faces, *, mesh_id="m", object_id="pitch"):
    return Finding(code=FindingCode.MESH_WINDING_INCONSISTENT, object_id=object_id, mesh_id=mesh_id,
                   measured={"edge": list(edge), "faces": list(faces)}, message="winding")


def _finding(code, measured, *, mesh_id="m", object_id="pitch"):
    return Finding(code=code, object_id=object_id, mesh_id=mesh_id, measured=measured,
                   message=code.value)


def _report_payload(findings):
    report = build_report(scene_id="scene", validation_state="needs_review", findings=findings,
                          scene_metrics={}, profile_name="soccer-field", input_digest=None,
                          source_revision_id=None)
    payload = report.to_json_compatible()
    payload["digest"] = report.digest()
    payload["report_format_version"] = REPORT_FORMAT_VERSION
    return payload


def _plan(findings, **overrides):
    return plan_scene_report(_report_payload(findings), profile=PROFILE, **overrides)


def _scene(faces, verts):
    payload = {"schema_version": PAYLOAD_SCHEMA_VERSION, "scene_id": "s", "unit_system": "METERS",
               "objects": [{"object_id": "pitch", "name": "pitch", "collection": "Field",
                            "parent_object_id": None, "location": [0, 0, 0], "scale": [1, 1, 1],
                            "rotation": [1, 0, 0, 0], "visible": True,
                            "mesh": {"mesh_id": "m", "vertices": [list(v) for v in verts],
                                     "faces": [list(f) for f in faces], "normals": None, "uvs": None,
                                     "materials": [], "local_frame_id": None}}]}
    return payload_to_scene_model(payload)


def _kernel_plan(faces, verts):
    scene = _scene(faces, verts)
    report = run_scene_health(scene, soccer_field_profile_default())
    payload = report.to_json_compatible()
    payload["digest"] = report.digest()
    payload["report_format_version"] = REPORT_FORMAT_VERSION
    return report, plan_scene_report(payload, profile=PROFILE)


def _winding_corrections(plan):
    return [c for c in plan.corrections if c.correction_type == WINDING]


def _only_winding(plan):
    corrections = _winding_corrections(plan)
    assert len(corrections) == 1, f"expected exactly one winding correction, got {len(corrections)}"
    return corrections[0]


def _params(correction):
    return thaw_jsonable(correction.parameters)


# ---------------------------------------------------------------------------
# D1 / D2 / D3 (the Rev-3 algorithm)
# ---------------------------------------------------------------------------

def test_no_winding_findings_produces_no_winding_correction():
    plan = _plan([_finding(FindingCode.MESH_DEGENERATE_FACE, {"face": 3, "signed_area": 0.0})])
    assert _winding_corrections(plan) == []
    assert plan.summary_metrics["planning_errors"] == 0


def test_single_finding_is_d2_and_requires_an_authorization_designation():
    plan = _plan([_winding_finding((0, 1), (0, 1))])
    correction = _only_winding(plan)
    params = _params(correction)
    assert params["designated_face_index"] is None, "D2: never designated by the planner"
    assert params["candidate_faces"] == [0, 1]
    assert params["recorded_edges"] == [[0, 1]]
    assert params["counterpart_faces"] == [1]
    assert params["orientation"] == WINDING_ORIENTATION
    assert params["mesh_id"] == "m"
    assert correction.requires_human_review is True
    assert plan.state == PlannerState.REVIEW_REQUIRED.value


def test_two_findings_with_one_common_face_are_d1_aggregated():
    plan = _plan([_winding_finding((0, 1), (0, 1)), _winding_finding((1, 2), (0, 2))])
    correction = _only_winding(plan)
    params = _params(correction)
    assert params["designated_face_index"] == 0, "D1: the unique common face is evidence-designated"
    assert params["candidate_faces"] is None
    assert params["recorded_edges"] == [[0, 1], [1, 2]]
    assert params["counterpart_faces"] == [1, 2]      # positionally aligned per edge
    assert correction.requires_human_review is True


def test_three_or_more_findings_with_one_common_face_are_one_d1_correction():
    plan = _plan([
        _winding_finding((0, 1), (0, 1)),
        _winding_finding((0, 2), (0, 3)),
        _winding_finding((1, 2), (0, 2)),
    ])
    corrections = _winding_corrections(plan)
    assert len(corrections) == 1, "3+ findings sharing one face aggregate into ONE correction"
    params = _params(corrections[0])
    assert params["designated_face_index"] == 0
    assert params["candidate_faces"] is None
    assert params["recorded_edges"] == [[0, 1], [0, 2], [1, 2]]   # lexicographic, canonical
    assert params["counterpart_faces"] == [1, 3, 2]


def test_empty_intersection_is_d3_and_produces_no_correction():
    plan = _plan([_winding_finding((0, 1), (0, 1)), _winding_finding((4, 5), (2, 3))])
    assert _winding_corrections(plan) == [], "D3: no winding correction may be fabricated"
    # the findings are still counted/classified and REMAIN REVIEW-ONLY (§2.1 step E): the plan must
    # say REVIEW_REQUIRED, never NO_CORRECTIONS, and a D3 refusal is not a planning error
    assert plan.summary_metrics["total"] == 2
    assert plan.state == PlannerState.REVIEW_REQUIRED.value
    assert plan.summary_metrics["planning_errors"] == 0


def test_identical_pairs_with_different_edges_is_d3_not_a_fabricated_designation():
    """Two findings with the same pair have an intersection of size 2, so there is no unique common
    face: the algorithm must refuse (D3) rather than pick one of the two faces."""
    plan = _plan([_winding_finding((0, 1), (0, 1)), _winding_finding((1, 2), (0, 1))])
    assert _winding_corrections(plan) == []


# ---------------------------------------------------------------------------
# real-kernel fixtures (design §12.1/§12.3)
# ---------------------------------------------------------------------------

def test_fixture_a_real_mesh_is_d2():
    report, plan = _kernel_plan([(0, 1, 2), (0, 1, 3)], Q)
    assert [f.measured for f in report.findings
            if f.code is FindingCode.MESH_WINDING_INCONSISTENT] == [
        {"edge": [0, 1], "faces": [0, 1]}]
    params = _params(_only_winding(plan))
    assert params["designated_face_index"] is None
    assert params["candidate_faces"] == [0, 1]
    assert params["recorded_edges"] == [[0, 1]]
    assert params["counterpart_faces"] == [1]


def test_fixture_b_real_mesh_is_d1_designating_the_common_face():
    report, plan = _kernel_plan([(0, 1, 2), (0, 1, 3), (1, 2, 4)], Q)
    assert len([f for f in report.findings
                if f.code is FindingCode.MESH_WINDING_INCONSISTENT]) == 2
    params = _params(_only_winding(plan))
    assert params["designated_face_index"] == 0
    assert params["recorded_edges"] == [[0, 1], [1, 2]]
    assert params["counterpart_faces"] == [1, 2]


def test_fixture_g_real_mesh_is_d1_with_three_recorded_edges():
    report, plan = _kernel_plan([(0, 1, 2), (0, 1, 3), (1, 2, 4), (2, 0, 5)], Q6)
    identities = sorted((tuple(f.measured["edge"]), tuple(f.measured["faces"]))
                        for f in report.findings
                        if f.code is FindingCode.MESH_WINDING_INCONSISTENT)
    assert identities == [((0, 1), (0, 1)), ((0, 2), (0, 3)), ((1, 2), (0, 2))]
    params = _params(_only_winding(plan))
    assert params["designated_face_index"] == 0
    assert params["recorded_edges"] == [[0, 1], [0, 2], [1, 2]]
    assert params["counterpart_faces"] == [1, 3, 2]


def test_fixture_c_real_disconnected_pairs_is_d3():
    report, plan = _kernel_plan(
        [(0, 1, 2), (0, 1, 3), (4, 5, 6), (4, 5, 7)],
        ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1), (2, 0, 0), (3, 0, 0), (2, 1, 0)))
    assert len([f for f in report.findings
                if f.code is FindingCode.MESH_WINDING_INCONSISTENT]) == 2
    assert _winding_corrections(plan) == []


def test_real_duplicate_pair_yields_d3_not_a_winding_correction():
    """Measured: an exact duplicate pair produces MESH_DUPLICATE_FACE **and** three winding findings
    (all with the SAME face pair), so the candidate-face intersection has size 2 and the §2.1
    algorithm refuses at planning time (D3). This is one stage EARLIER than WC-P14's refusal and is
    strictly more conservative: no winding correction exists for such a mesh at all (the duplicate
    removal is the correct remedy)."""
    report, plan = _kernel_plan([(0, 1, 2), (1, 2, 0)], Q)
    codes = [f.code.value for f in report.findings]
    assert "MESH_DUPLICATE_FACE" in codes
    winding = [f for f in report.findings if f.code is FindingCode.MESH_WINDING_INCONSISTENT]
    assert len(winding) == 3
    assert {tuple(f.measured["faces"]) for f in winding} == {(0, 1)}
    assert _winding_corrections(plan) == []
    assert plan.summary_metrics["planning_errors"] == 0
    assert any(c.correction_type == "REMOVE_DUPLICATE_FACE" for c in plan.corrections)


# ---------------------------------------------------------------------------
# canonicalization, determinism, identity
# ---------------------------------------------------------------------------

def test_aggregation_is_independent_of_finding_input_order():
    """The AGGREGATE is order-independent (§2.4). The report itself is not fully order-canonical —
    ``SceneReport`` orders findings by (code, object_id, mesh_id) and same-key findings keep their
    insertion order, so a hand-made report's digest (and therefore the plan's source binding) differs
    when two same-key findings are swapped. That is the report contract, not an aggregation defect:
    kernel-produced reports are emitted in a fixed order."""
    findings = [_winding_finding((0, 1), (0, 1)), _winding_finding((0, 2), (0, 3)),
                _winding_finding((1, 2), (0, 2))]
    forward = _plan(findings)
    backward = _plan(list(reversed(findings)))
    assert _params(_only_winding(forward)) == _params(_only_winding(backward))
    assert _only_winding(forward).correction_id == _only_winding(backward).correction_id
    assert forward.summary_metrics == backward.summary_metrics
    # the kernels own report order: a real scene produces a byte-identical plan on every run
    report_a, real_a = _kernel_plan([(0, 1, 2), (0, 1, 3), (1, 2, 4)], Q)
    report_b, real_b = _kernel_plan([(0, 1, 2), (0, 1, 3), (1, 2, 4)], Q)
    assert real_a.canonical_json() == real_b.canonical_json()
    assert real_a.plan_id == real_b.plan_id


def test_duplicate_finding_identity_is_counted_once():
    """§2.0: a repeated canonical identity is the SAME finding — it must not turn a D2 into a D1."""
    plan = _plan([_winding_finding((0, 1), (0, 1)), _winding_finding((0, 1), (0, 1))])
    params = _params(_only_winding(plan))
    assert params["designated_face_index"] is None, "a repeated identity stays a single D2 finding"
    assert params["candidate_faces"] == [0, 1]
    assert params["recorded_edges"] == [[0, 1]]


def test_reversed_edge_or_face_order_in_the_finding_is_canonicalized():
    """The identity is undirected: (b,a) with (f2,f1) is the SAME finding."""
    plan = _plan([_winding_finding((1, 0), (1, 0))])
    params = _params(_only_winding(plan))
    assert params["recorded_edges"] == [[0, 1]]
    assert params["candidate_faces"] == [0, 1]
    assert params["counterpart_faces"] == [1]


def test_identical_logical_aggregate_yields_identical_correction_id():
    a = _plan([_winding_finding((0, 1), (0, 1)), _winding_finding((1, 2), (0, 2))])
    b = _plan([_winding_finding((1, 2), (2, 0)), _winding_finding((0, 1), (1, 0))])
    # the aggregated correction id is CONTENT-addressed over (code, scope, canonical parameters):
    # identical logical aggregates produce identical ids regardless of report ordering (§2.4)
    assert _only_winding(a).correction_id == _only_winding(b).correction_id
    assert _params(_only_winding(a)) == _params(_only_winding(b))


def test_parameter_key_set_is_exactly_the_design_schema():
    plan = _plan([_winding_finding((0, 1), (0, 1))])
    correction = _only_winding(plan)
    assert tuple(sorted(dict(correction.parameters).keys())) == tuple(sorted(WINDING_PARAMETER_KEYS))
    assert set(WINDING_PARAMETER_KEYS) == {
        "mesh_id", "designated_face_index", "candidate_faces", "recorded_edges",
        "counterpart_faces", "orientation",
    }


def test_deep_frozen_aggregated_parameters_cannot_be_mutated():
    plan = _plan([_winding_finding((0, 1), (0, 1))])
    correction = _only_winding(plan)
    with pytest.raises((TypeError, AttributeError)):
        correction.parameters["recorded_edges"].append((9, 9))
    with pytest.raises((TypeError, AttributeError)):
        correction.parameters["designated_face_index"] = 7
    assert plan.plan_id == plan._compute_plan_id()


# ---------------------------------------------------------------------------
# suppression, dependencies, multi-mesh, malformed input
# ---------------------------------------------------------------------------

def test_per_finding_winding_proposals_are_suppressed_entirely():
    """§2.5 L/M: the aggregation pass is the ONLY producer for every mesh with findings."""
    plan = _plan([_winding_finding((0, 1), (0, 1))])
    corrections = _winding_corrections(plan)
    assert len(corrections) == 1
    params = _params(corrections[0])
    assert "faces" not in params, "the legacy per-finding parameter shape must never be emitted"
    assert params["orientation"] != "repair_to_shared_edge_opposite"
    assert all(c.correction_type != WINDING for c in plan.corrections
               if c.finding_code != FindingCode.MESH_WINDING_INCONSISTENT.value)


@pytest.mark.parametrize("code,measured,removal_type", [
    (FindingCode.MESH_DUPLICATE_FACE, {"face_a": 0, "face_b": 4}, "REMOVE_DUPLICATE_FACE"),
    (FindingCode.MESH_DEGENERATE_FACE, {"face": 3, "signed_area": 0.0}, "REMOVE_DEGENERATE_FACE"),
])
def test_removal_dependency_edge_points_at_the_aggregated_correction(code, measured, removal_type):
    findings = [_finding(code, measured), _winding_finding((0, 1), (0, 1))]
    plan = _plan(findings)
    removal = [c for c in plan.corrections if c.correction_type == removal_type]
    winding = _only_winding(plan)
    assert len(removal) == 1
    assert (removal[0].correction_id, winding.correction_id) in plan.dependencies
    # the aggregate is ONE node: exactly one dependency edge into it, never one per finding
    assert sum(1 for edge in plan.dependencies if edge[1] == winding.correction_id) == 1
    order = [c.correction_id for c in plan.corrections]
    assert order.index(removal[0].correction_id) < order.index(winding.correction_id)


def test_two_meshes_produce_two_aggregated_corrections():
    """§2.6 O: aggregation is per mesh; the executor then refuses such a plan (one mesh per run)."""
    findings = [_winding_finding((0, 1), (0, 1), mesh_id="m1"),
                _winding_finding((2, 3), (0, 1), mesh_id="m2")]
    plan = _plan(findings)
    corrections = _winding_corrections(plan)
    assert len(corrections) == 2
    assert len({c.correction_id for c in corrections}) == 2
    assert {c.mesh_id for c in corrections} == {"m1", "m2"}


def test_findings_for_other_meshes_never_influence_a_meshes_aggregate():
    """A mesh's D1 designation must be computed only from that mesh's own findings."""
    findings = [
        _winding_finding((0, 1), (0, 1), mesh_id="m1"),
        _winding_finding((1, 2), (0, 2), mesh_id="m1"),
        _winding_finding((5, 6), (3, 4), mesh_id="m2"),   # a different mesh: must not join the set
    ]
    plan = _plan(findings)
    by_mesh = {c.mesh_id: _params(c) for c in _winding_corrections(plan)}
    assert by_mesh["m1"]["designated_face_index"] == 0
    assert by_mesh["m1"]["recorded_edges"] == [[0, 1], [1, 2]]
    assert by_mesh["m2"]["designated_face_index"] is None
    assert by_mesh["m2"]["recorded_edges"] == [[5, 6]]


def test_malformed_winding_measured_is_a_planning_error():
    for bad in ({"edge": [0], "faces": [0, 1]},
                {"edge": [0, 1], "faces": [0]},
                {"edge": [0, 1]},
                {"faces": [0, 1]},
                {"edge": [0, 1], "faces": [0, 0]},
                {"edge": [0, 0], "faces": [0, 1]},
                {"edge": [0.0, 1.0], "faces": [0, 1]},
                {"edge": [0, 1], "faces": [0, True]},
                "not-a-dict"):
        plan = _plan([_finding(FindingCode.MESH_WINDING_INCONSISTENT, bad)])
        assert _winding_corrections(plan) == [], bad
        assert plan.summary_metrics["planning_errors"] >= 1, bad
        assert plan.state == PlannerState.PLANNING_ERROR.value, bad


def test_winding_finding_without_a_mesh_id_is_refused_never_inferred():
    plan = _plan([_winding_finding((0, 1), (0, 1), mesh_id=None)])
    assert _winding_corrections(plan) == []
    assert plan.summary_metrics["planning_errors"] == 1
    assert plan.state == PlannerState.PLANNING_ERROR.value


def test_one_edge_attributed_to_two_pairs_is_refused():
    """An impossible vertex in a manifold mesh: fail closed rather than guess a counterpart."""
    plan = _plan([_winding_finding((0, 1), (0, 1)), _winding_finding((0, 1), (2, 3))])
    assert _winding_corrections(plan) == []
    assert plan.summary_metrics["planning_errors"] == 1


def test_winding_findings_with_conflicting_object_ids_are_refused():
    plan = _plan([_winding_finding((0, 1), (0, 1), object_id="pitch"),
                  _winding_finding((1, 2), (2, 3), object_id="other")])
    assert _winding_corrections(plan) == []
    assert plan.summary_metrics["planning_errors"] == 1


def test_aggregated_plan_metrics_still_classify_the_winding_finding():
    plan = _plan([_winding_finding((0, 1), (0, 1))])
    assert plan.summary_metrics["total"] == 1
    assert plan.summary_metrics["heuristic"] == 1
    assert plan.summary_metrics["requires_review"] == 0   # determinism is HEURISTIC, not review-class
    assert plan.summary_metrics["planning_errors"] == 0


def test_aggregation_does_not_disturb_unrelated_correction_types():
    findings = [
        _finding(FindingCode.MESH_DEGENERATE_FACE, {"face": 3, "signed_area": 0.0}),
        _winding_finding((0, 1), (0, 1)),
        _finding(FindingCode.MESH_DUPLICATE_FACE, {"face_a": 0, "face_b": 4}),
    ]
    plan = _plan(findings)
    types = sorted(c.correction_type for c in plan.corrections)
    assert types == ["REMOVE_DEGENERATE_FACE", "REMOVE_DUPLICATE_FACE", "REPAIR_FACE_WINDING"]
    assert json.loads(json.dumps(thaw_jsonable(plan.corrections[0].parameters))) is not None
    copied = copy.deepcopy(plan.canonical_json())
    assert copied == plan.canonical_json()

def test_per_finding_winding_proposal_function_never_emits_a_winding_proposal():
    """The guard is explicit, not incidental: ``_finding_to_proposal`` returns [] for a winding
    finding, so no caller can obtain a per-finding winding proposal from it."""
    from planning.blender.correction_planner import _finding_to_proposal

    # the planner passes the report's JSON-shaped finding (``Finding.snapshot()``)
    proposal_finding = _winding_finding((0, 1), (0, 1)).snapshot()
    assert _finding_to_proposal(proposal_finding, report_digest="a" * 64, profile=PROFILE,
                                object_scope_optional=True, index=0) == []
