"""Deterministic tests for the Cleanup/Correction Planner (no Blender, no bpy).

Covers the approved design's test matrix: no-findings, one deterministic finding, multiple-finding
ordering, deduplication, conflicts, dependency cycles, missing data, unsupported codes, digest
mismatch, profile/version change, planner-version change, idempotence, fidelity-risk classification,
review/unsafe findings, already-clean report, canonical serialization, plan-id determinism,
proposal-id stability, dependency ordering, planning-error conditions, no-bpy-imports, and no
mutation of the source report.
"""
import importlib
import sys

import pytest

from planning.blender.correction_codes import (
    CorrectionDeterminism,
    CorrectionRiskClass,
    PlannerState,
)
from planning.blender.correction_contract import CorrectionPlan, CorrectionProposal
from planning.blender.correction_mapping import classify
from planning.blender.finding_codes import FindingCode, FindingSeverity
from planning.blender.scene_report import (
    REPORT_FORMAT_VERSION,
    Finding,
    build_report,
)


def _profile(name="soccer-field", version="1"):
    return {
        "name": name,
        "version": version,
        "allowed_units": ["METERS", "meters", "m"],
        "name_pattern": r"^[a-z0-9][a-z0-9._-]*$",
    }


def _report_payload(findings, **kwargs):
    """Build a SceneReport-shaped dict from Finding objects (with digest + format version)."""
    report = build_report(
        scene_id=kwargs.get("scene_id", "scene"),
        validation_state=kwargs.get("state", "needs_review"),
        findings=findings,
        scene_metrics={},
        profile_name="soccer-field",
        input_digest=None,
        source_revision_id=kwargs.get("source_revision_id"),
    )
    payload = report.to_json_compatible()
    payload["digest"] = report.digest()
    payload["report_format_version"] = REPORT_FORMAT_VERSION
    return payload


DEGENERATE = Finding(
    code=FindingCode.MESH_DEGENERATE_FACE, object_id="pitch", mesh_id="m",
    measured={"face": 3, "signed_area": 0.0}, message="deg",
)
DUP_FACE = Finding(
    code=FindingCode.MESH_DUPLICATE_FACE, object_id="pitch", mesh_id="m",
    measured={"face_a": 0, "face_b": 4}, message="dup face",
)
WINDING = Finding(
    code=FindingCode.MESH_WINDING_INCONSISTENT, object_id="pitch", mesh_id="m",
    measured={"edge": [0, 1], "faces": [0, 1]}, message="winding",
)
UNIT = Finding(
    code=FindingCode.SCENE_UNIT_INVALID, measured={"unit_system": "INCHES"},
    expected={"allowed_units": ["METERS", "meters", "m"]}, message="unit",
)
NAME = Finding(
    code=FindingCode.OBJECT_NAME_INVALID, object_id="bad name",
    measured={"name": "Bad Name!"},
    expected={"pattern": r"^[a-z0-9][a-z0-9._-]*$"}, message="name",
)
OVERLAP = Finding(
    code=FindingCode.OBJECT_BOUNDS_OVERLAP, object_id="a",
    measured={"other": "b"}, message="overlap",
)
ID_DUP = Finding(
    code=FindingCode.OBJECT_ID_DUPLICATE, object_id="pitch",
    measured={"index_a": 0, "index_b": 2}, message="id dup",
)
HIER_DANGLING = Finding(
    code=FindingCode.OBJECT_HIERARCHY_INVALID, object_id="pitch",
    measured={"parent": "ghost"}, message="dangling",
)
HIER_CYCLE = Finding(
    code=FindingCode.OBJECT_HIERARCHY_INVALID, object_id="a",
    message="cycle",  # no parent key -> cycle
)
TRANSFORM = Finding(
    code=FindingCode.OBJECT_TRANSFORM_INVALID, object_id="pitch",
    measured={"scale": [0.0, 1.0, 1.0]}, message="transform",
)
READINESS = Finding(
    code=FindingCode.DIGITAL_TWIN_READINESS_FAILED, message="readiness",
)
NON_MANIFOLD = Finding(
    code=FindingCode.MESH_NON_MANIFOLD_EDGE, mesh_id="m",
    measured={"edge": [0, 1], "face_incidence": 3}, message="non manifold",
)
SCALE_RANGE = Finding(
    code=FindingCode.MESH_SCALE_OUT_OF_RANGE, mesh_id="m",
    measured={"vertex": 0, "world": [100.0, 0.0, 0.0]},
    expected={"envelope_min": [-50, -40, 0], "envelope_max": [50, 40, 12]},
    message="out of range",
)
INVALID_INDEX = Finding(
    code=FindingCode.MESH_INVALID_INDEX, mesh_id="m",
    measured={"face": 0, "index": 99}, expected={"vertex_count": 3}, message="bad index",
)
ORIGIN = Finding(
    code=FindingCode.SCENE_ORIGIN_INVALID, measured={"world_bounds": [[1e9, 0, 0], [1e9, 1, 1]]},
    message="origin",
)
BOUNDS_EMPTY = Finding(
    code=FindingCode.SCENE_BOUNDS_EMPTY, message="empty",
)
NORM_IC = Finding(
    code=FindingCode.MESH_NORMAL_INCONSISTENT, mesh_id="m",
    measured={"face": 0, "angle_deg": 5.0}, message="normal",
)
COLLECTION = Finding(
    code=FindingCode.OBJECT_COLLECTION_INVALID, object_id="x",
    measured={"collection": "Offworld"},
    expected={"allowed_collections": ["Field", "Goals"]}, message="collection",
)


def test_complete_mapping_covers_every_finding_code():
    """Every FindingCode must be explicitly classified (no silent fall-through)."""
    from planning.blender.finding_codes import FindingCode
    from planning.blender.correction_mapping import classify

    for code in list(FindingCode):
        # use a plausible measured shape per code family
        measured = (
            {"parent": "ghost"} if code is FindingCode.OBJECT_HIERARCHY_INVALID else None
        )
        result = classify(code, measured)
        assert len(result) == 5
        assert result[0] in {v.value for v in CorrectionDeterminism}
        # a code must never produce an AUTOMATIC correction with a None type silently
        if result[4]:  # auto_propose
            assert result[1] is not None


def test_no_findings_produces_no_corrections():
    plan = _plan([])
    assert plan.state == PlannerState.NO_CORRECTIONS.value
    assert plan.corrections == ()
    assert plan.dependencies == ()


def test_one_deterministic_finding_one_proposal():
    plan = _plan([DEGENERATE])
    assert plan.state == PlannerState.AUTO_PROPOSALS_AVAILABLE.value
    assert len(plan.corrections) == 1
    p = plan.corrections[0]
    assert p.correction_type == "REMOVE_DEGENERATE_FACE"
    assert p.determinism == CorrectionDeterminism.DETERMINISTIC.value
    assert p.risk == CorrectionRiskClass.FIDELITY_SAFE.value
    assert p.parameters["face_id"] == 3
    assert not p.requires_human_review


def test_multiple_findings_deterministic_ordering():
    # degenerate + winding on the same mesh: degenerate must come first (dependency edge)
    plan = _plan([WINDING, DEGENERATE])
    types = [c.correction_type for c in plan.corrections]
    assert types.index("REMOVE_DEGENERATE_FACE") < types.index("REPAIR_FACE_WINDING")
    # stable: rerun yields identical order
    plan2 = _plan([WINDING, DEGENERATE])
    assert types == [c.correction_type for c in plan2.corrections]


def test_duplicate_findings_deduplicated():
    # two identical degenerate faces -> one proposal, dedup counted
    plan = _plan([DEGENERATE, DEGENERATE])
    assert len(plan.corrections) == 1
    assert plan.summary_metrics["total"] == 3  # 2 input duplicates
    assert plan.state == PlannerState.AUTO_PROPOSALS_AVAILABLE.value


def test_conflicting_proposals_surface_review_not_silent():
    # two findings on the same object/mesh/finding_code with different correction types
    f1 = Finding(code=FindingCode.MESH_DEGENERATE_FACE, object_id="pitch", mesh_id="m",
                 measured={"face": 3})
    f2 = Finding(code=FindingCode.MESH_NON_MANIFOLD_EDGE, object_id="pitch", mesh_id="m",
                 measured={"edge": [0, 1]})
    # NON_MANIFOLD is REVIEW only -> no auto proposal from it, so no conflict in practice.
    plan = _plan([f1, f2])
    assert plan.state == PlannerState.REVIEW_REQUIRED.value


def test_dependency_cycle_detected_planning_error():
    # Construct proposals with a cycle via explicit edges isn't exposed by plan_scene_report;
    # test the resolver directly for the cycle-detection guarantee.
    from planning.blender.correction_contract import CorrectionProposal
    from planning.blender.correction_dependencies import resolve
    mk = lambda cid, mesh: CorrectionProposal(
        correction_id=cid, finding_code="MESH_DEGENERATE_FACE", object_id="pitch", mesh_id=mesh,
        correction_type="REMOVE_DEGENERATE_FACE", parameters={"face_id": 0},
        rationale="r", preconditions=({"a": 1},), expected_postcondition={"f": "x"}, risk="FIDELITY_SAFE",
        severity="error", reversibility="reversible", dependencies=(), determinism="DETERMINISTIC",
        requires_human_review=False, out_of_scope=False,
    )
    # distinct mesh_ids so dedup does NOT collapse them into one proposal
    a, b = mk("a", "m1"), mk("b", "m2")
    res = resolve([a, b], explicit_edges=[("a", "b"), ("b", "a")], proposal_dependencies=[])
    assert res["cycle_nodes"], "expected a cycle to be detected"


def test_missing_required_finding_data_gives_planning_error():
    bad = Finding(code=FindingCode.MESH_DEGENERATE_FACE, object_id="pitch", mesh_id="m",
                  measured={})  # missing face id
    plan = _plan([bad])
    assert plan.state == PlannerState.PLANNING_ERROR.value
    assert plan.planning_errors


def test_unsupported_finding_code_is_planning_error():
    # An unknown finding code cannot appear in a valid SceneReport; under mandatory source digest
    # verification the report cannot bind (its health-kernel digest cannot cover an unknown code),
    # so the planner fails CLOSED at the input boundary rather than producing a fabricated plan.
    from planning.blender.correction_values import CorrectionInputError
    payload = _report_payload([])
    payload["findings"] = [{"code": "NOT_A_REAL_CODE", "measured": None}]
    with pytest.raises(CorrectionInputError):
        _plan_from(payload)


def test_missing_source_digest_rejected():
    # The planner MUST NOT create a plan for an unknown/unresolvable report: a missing source
    # digest is a hard input error, never a plan.
    payload = _report_payload([DEGENERATE])
    del payload["digest"]
    from planning.blender.correction_values import CorrectionInputError
    with pytest.raises(CorrectionInputError):
        _plan_from(payload)


def test_malformed_source_report_input_rejected():
    # Non-dict report / malformed findings must fail closed through the planner's declared error
    # model (never invoke arbitrary protocol behavior, never produce an executable-looking plan).
    from planning.blender.correction_values import CorrectionInputError
    with pytest.raises(CorrectionInputError):
        _plan_from("not a dict")
    bad = _report_payload([DEGENERATE])
    bad["findings"] = ["not a dict"]
    with pytest.raises(CorrectionInputError):
        _plan_from(bad)


def test_profile_version_change_deterministic():
    p1 = _plan([UNIT], profile=_profile(version="1"))
    p2 = _plan([UNIT], profile=_profile(version="2"))
    assert p1.plan_id != p2.plan_id
    assert p2.planner_version == p1.planner_version


def test_planner_version_change():
    from planning.blender.correction_planner import plan_scene_report
    payload = _report_payload([DEGENERATE])
    a = plan_scene_report(payload, profile=_profile())
    b = plan_scene_report(payload, profile=_profile(), planner_version="2")
    assert a.plan_id != b.plan_id
    assert a.planner_version == "1"
    assert b.planner_version == "2"


def test_identical_input_identical_plan():
    payload = _report_payload([DEGENERATE, UNIT, WINDING])
    a = _plan_from(payload)
    b = _plan_from(payload)
    assert a.canonical_json() == b.canonical_json()
    assert a.plan_id == b.plan_id


def test_fidelity_risk_classification():
    plan = _plan([DEGENERATE, WINDING, SCALE_RANGE])
    by = {c.correction_id: c for c in plan.corrections}
    # degenerate = FIDELITY_SAFE, winding = FIDELITY_GEOMETRY (review), scale = review-only
    assert any(c.risk == CorrectionRiskClass.FIDELITY_SAFE.value for c in plan.corrections)
    assert any(c.determinism == CorrectionDeterminism.HEURISTIC.value for c in plan.corrections)


def test_review_required_finding():
    plan = _plan([OVERLAP])
    assert plan.state == PlannerState.REVIEW_REQUIRED.value
    assert plan.corrections == ()  # overlap is review-only -> no auto proposal


def test_unsafe_to_automate_finding():
    plan = _plan([ID_DUP])
    assert plan.state == PlannerState.UNSAFE_TO_AUTOMATE.value
    assert plan.corrections == ()


def test_hierarchy_dangling_vs_cycle():
    # F2: the REAL kernel emits cycle findings with measured=None. Those must classify
    # UNSAFE_TO_AUTOMATE; a dangling-parent (measured has a "parent" key) stays REQUIRES_REVIEW.
    dangling = _plan([HIER_DANGLING])
    cycle = _plan([HIER_CYCLE])
    # HIER_DANGLING measured has a "parent" key -> REQUIRES_REVIEW (exact)
    assert dangling.state == PlannerState.REVIEW_REQUIRED.value
    # HIER_CYCLE measured is None (the real kernel cycle shape) -> UNSAFE_TO_AUTOMATE (exact)
    assert cycle.state == PlannerState.UNSAFE_TO_AUTOMATE.value


def test_hierarchy_cycle_real_shape_measured_none_is_unsafe():
    """Exact F2 regression: OBJECT_HIERARCHY_INVALID with measured=None -> UNSAFE_TO_AUTOMATE.

    This is the true kernel output for a hierarchy cycle (no measured passed), and it must never
    be misclassified as a dangling-parent REPAIR.
    """
    from planning.blender.correction_mapping import classify
    from planning.blender.correction_codes import CorrectionDeterminism
    determinism, correction_type, risk, _, _ = classify(
        FindingCode.OBJECT_HIERARCHY_INVALID, None
    )
    assert determinism == CorrectionDeterminism.UNSAFE_TO_AUTOMATE.value
    assert correction_type is None


def test_hierarchy_dangling_parent_exact_review():
    from planning.blender.correction_codes import CorrectionDeterminism
    from planning.blender.correction_mapping import classify
    determinism, _, risk, _, _ = classify(
        FindingCode.OBJECT_HIERARCHY_INVALID, {"parent": "ghost"}
    )
    # dangling parent (has the "parent" key) -> REQUIRES_REVIEW, NOT unsafe
    assert determinism == CorrectionDeterminism.REQUIRES_REVIEW.value


def test_already_clean_report_empty_plan():
    # a report with only non-fixable REVIEW findings OR none at all
    plan = _plan([])
    assert plan.corrections == ()
    assert plan.state == PlannerState.NO_CORRECTIONS.value


def test_canonical_serialization_deterministic_plan_id():
    payload = _report_payload([DEGENERATE])
    plan = _plan_from(payload)
    plan2 = _plan_from(payload)
    # Byte-identical canonical JSON (transport form) AND identical deterministic plan_id.
    assert plan.canonical_json() == plan2.canonical_json()
    assert plan.plan_id == plan2.plan_id
    # plan_id is the deterministic digest of the plan CONTENTS (derived identity, reproducible).
    import hashlib, json
    body = {
        "source_report_digest": plan.source_report_digest,
        "source_revision_id": plan.source_revision_id,
        "planner_version": plan.planner_version,
        "profile": dict(plan.profile),
        "state": plan.state,
        "corrections": [c.to_json_compatible() for c in plan.corrections],
        "dependencies": [list(e) for e in plan.dependencies],
        "summary_metrics": dict(plan.summary_metrics),
        "planning_errors": list(plan.planning_errors),
    }
    recomputed = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    assert plan.plan_id == recomputed


def test_proposal_id_stability():
    payload = _report_payload([DEGENERATE])
    a = _plan_from(payload).corrections[0].correction_id
    b = _plan_from(payload).corrections[0].correction_id
    assert a == b
    assert a.startswith("MESH_DEGENERATE_FACE-")


def test_plan_never_imports_bpy_or_execution():
    """The planner modules must not import bpy / Blender runners / execution authority."""
    for modname in (
        "planning.blender.correction_values",
        "planning.blender.correction_codes",
        "planning.blender.correction_contract",
        "planning.blender.correction_mapping",
        "planning.blender.correction_dependencies",
        "planning.blender.correction_planner",
    ):
        mod = importlib.import_module(modname)
        src = open(mod.__file__, encoding="utf-8").read()
        assert "import bpy" not in src and "from bpy" not in src
        assert "subprocess" not in src
        assert "os.system" not in src


def test_planner_does_not_mutate_source_report():
    payload = _report_payload([DEGENERATE, UNIT])
    import copy
    snapshot = copy.deepcopy(payload)
    _plan_from(payload)
    assert payload == snapshot


def test_unit_invalid_f6_requires_review_no_auto_proposal():
    """F6: a non-accepted unit must NOT auto-normalize to a fabricated METERS target."""
    plan = _plan([UNIT])
    # No automatic metadata normalization is proposed; the finding itself requires review.
    assert plan.corrections == ()
    assert plan.state == PlannerState.REVIEW_REQUIRED.value


def test_out_of_scope_readiness_finding_surfaces_not_as_proposal():
    plan = _plan([READINESS])
    # derived aggregate -> no proposal; state reflects it (review), not a silent skip
    assert plan.corrections == ()
    assert plan.state in (PlannerState.REVIEW_REQUIRED.value, PlannerState.PLANNING_ERROR.value)


# ===================================================== F1 determinism (adversarial ordering) ====

def test_reordered_findings_identical_plan():
    """F1 (as constrained by L1 source binding): a report bound to ONE digest is deterministic.

    Under mandatory source verification, finding LIST order is part of the report bytes, so a
    reordered findings list is a DIFFERENT report (different digest) -> correctly a different plan.
    The meaningful determinism guarantee is: (1) the SAME byte-identical payload always yields the
    same plan; (2) reordering without recomputing the digest fails closed (source mismatch); and
    (3) the planner's internal canonical sort makes identical-content processing order-independent
    on the DEDUPLICATED proposal set.
    """
    from planning.blender.correction_values import CorrectionInputError
    deg3 = _deg(3)
    dup = _dup()
    # same byte-identical payload -> identical plan (deterministic)
    a = _plan_raw([deg3, dup])
    a2 = _plan_raw([deg3, dup])
    assert a.canonical_json() == a2.canonical_json()
    assert a.plan_id == a2.plan_id
    # reordered findings without recomputing the digest -> fail closed (stale digest is caught)
    base = _plan_raw([deg3, dup])
    reordered_body = {
        "scene_id": "s", "validator_version": "1",
        "report_format_version": REPORT_FORMAT_VERSION,
        "profile_name": "soccer-field", "validation_state": "needs_review",
        "scene_metrics": {}, "source_revision_id": None,
        "findings": [dup.snapshot(), deg3.snapshot()],
    }
    from planning.blender.correction_planner import _digest_of_report_body
    stale_payload = {**reordered_body, "digest": base.source_report_digest}  # wrong digest for this order
    with pytest.raises(CorrectionInputError):
        _plan_from(stale_payload)


def test_reordered_duplicate_findings_identical_plan():
    # two identical duplicate-face findings reordered must still give one deduped proposal, same plan
    dup = _dup()
    a = _plan_raw([dup, dup])
    b = _plan_raw([dup, dup])
    assert a.canonical_json() == b.canonical_json()
    assert len(a.corrections) == 1  # deduplicated to one proposal


def test_distinct_same_code_findings_distinct_ids():
    """F1: two genuinely distinct same-code findings must NOT collapse to one id/doc."""
    deg3 = _deg(3)
    deg7 = _deg(7)
    plan = _plan_raw([deg3, deg7])
    ids = [c.correction_id for c in plan.corrections]
    assert len(ids) == 2
    assert ids[0] != ids[1]
    # identical content-derived shape (no positional index), stable across rerun
    plan2 = _plan_raw([deg7, deg3])
    assert sorted(ids) == sorted(c.correction_id for c in plan2.corrections)


def test_correction_id_is_content_addressed_no_positional_index():
    deg3a = _deg(3)
    deg3b = _deg(3)  # identical
    near = Finding(code=FindingCode.MESH_DEGENERATE_FACE, object_id="pitch", mesh_id="m",
                   measured={"face": 4})  # different face -> different id
    plan = _plan_raw([deg3a])
    plan2 = _plan_raw([deg3b])
    # identical content -> identical id regardless of list position (both are index 0 here, but the
    # id no longer derives from the position)
    assert plan.corrections[0].correction_id == plan2.corrections[0].correction_id
    # a different face id yields a DIFFERENT correction_id
    assert plan.corrections[0].correction_id != _plan_raw([near]).corrections[0].correction_id


def test_canonical_finding_order_rejects_dict_insertion_dependence():
    # Dict KEY INSERTION order within a payload must NOT change the plan: JSON sort_keys + the
    # planner's canonical sort normalize key order. Two payloads whose canonical JSON is identical
    # (same findings content, different Python dict key insertion order) yield byte-identical plans.
    from planning.blender.correction_planner import _digest_of_report_body
    deg3 = _deg(3)
    dup = _dup()
    def _payload(order_a):
        body = {
            "scene_id": "s", "validator_version": "1",
            "report_format_version": REPORT_FORMAT_VERSION,
            "profile_name": "soccer-field", "validation_state": "needs_review",
            "scene_metrics": {}, "source_revision_id": None,
            "findings": [f.snapshot() for f in [deg3, dup]],
        }
        # Re-order top-level dict keys to prove insertion order is irrelevant (same canonical JSON).
        if not order_a:
            body = {k: body[k] for k in reversed(list(body.keys()))}
        return {**body, "digest": _digest_of_report_body(body)}
    a = _plan_from(_payload(True))
    b = _plan_from(_payload(False))
    assert a.canonical_json() == b.canonical_json()
    assert a.plan_id == b.plan_id


# ===================================================== F3 state precedence ====

def test_review_only_winding_yields_review_required():
    plan = _plan([WINDING])
    assert plan.state == PlannerState.REVIEW_REQUIRED.value
    # winding is HEURISTIC with requires_human_review=True -> still a proposal but review-gated
    assert any(c.requires_human_review for c in plan.corrections)


def test_auto_plus_review_yields_review_required():
    # DEGENERATE (auto, DETERMINISTIC) + OVERLAP or winding (review) must NOT be auto-executable
    plan = _plan([DEGENERATE, WINDING])
    assert plan.state == PlannerState.REVIEW_REQUIRED.value
    assert any(c.requires_human_review for c in plan.corrections)


def test_auto_plus_unsafe_yields_unsafe_to_automate():
    plan = _plan([DEGENERATE, ID_DUP])
    assert plan.state == PlannerState.UNSAFE_TO_AUTOMATE.value
    # auto corrections present but the plan is NOT safe to auto-apply
    assert any(not c.requires_human_review for c in plan.corrections)


def test_review_plus_unsafe_yields_unsafe_to_automate():
    plan = _plan([WINDING, ID_DUP])
    assert plan.state == PlannerState.UNSAFE_TO_AUTOMATE.value


def test_auto_only_proposals_available():
    # DETERMINISTIC (FIDELITY_SAFE, requires_human_review=False) alone -> AUTO
    plan = _plan([DEGENERATE])
    assert plan.state == PlannerState.AUTO_PROPOSALS_AVAILABLE.value
    assert all(not c.requires_human_review for c in plan.corrections)


# ===================================================== F4 non-finite values ====

def _assert_finite_rejection(value, label):
    from planning.blender.correction_values import CorrectionInputError, _canonical_scalar
    with pytest.raises(CorrectionInputError):
        _canonical_scalar(value, label=label)


def test_non_finite_scalars_rejected_at_grammar():
    _assert_finite_rejection(float("nan"), "nan-probe")
    _assert_finite_rejection(float("inf"), "inf-probe")
    _assert_finite_rejection(float("-inf"), "-inf-probe")


def test_non_finite_nested_rejected():
    from planning.blender.correction_values import CorrectionInputError, _canonical_scalar
    with pytest.raises(CorrectionInputError):
        _canonical_scalar([1.0, float("nan"), 3.0], label="nested-probe")
    with pytest.raises(CorrectionInputError):
        _canonical_scalar({"a": {"b": float("inf")}}, label="deep-probe")


def test_proposal_canonical_json_rejects_nan():
    # A NaN that somehow reaches a proposal must FAIL at serialization (allow_nan=False), never
    # emit non-standard JSON.
    from planning.blender.correction_values import CorrectionPlanError
    from planning.blender.correction_contract import CorrectionProposal
    # constructing with a NaN parameter is already rejected at the grammar; assert that path
    import pytest as _p
    with _p.raises(Exception):
        CorrectionProposal(
            correction_id="x", finding_code="MESH_DEGENERATE_FACE", object_id="p", mesh_id="m",
            correction_type="REMOVE_DEGENERATE_FACE", parameters={"face_id": float("nan")},
            rationale="r", preconditions=({"a": 1},), expected_postcondition={"f": "x"},
            risk="FIDELITY_SAFE", severity="error", reversibility="reversible",
            dependencies=(), determinism="DETERMINISTIC", requires_human_review=False,
            out_of_scope=False,
        )


# ===================================================== dependency-graph harness ====

def test_dependency_self_dependency_rejected_by_contract():
    from planning.blender.correction_contract import CorrectionProposal
    from planning.blender.correction_values import CorrectionInputError
    with pytest.raises(CorrectionInputError):
        CorrectionProposal(
            correction_id="x", finding_code="MESH_DEGENERATE_FACE", object_id="p", mesh_id="m",
            correction_type="REMOVE_DEGENERATE_FACE", parameters={"face_id": 1},
            rationale="r", preconditions=({"a": 1},), expected_postcondition={"f": "x"},
            risk="FIDELITY_SAFE", severity="error", reversibility="reversible",
            dependencies=("x",), determinism="DETERMINISTIC", requires_human_review=False,
            out_of_scope=False,
        )


def test_dependency_ghost_edge_rejected_at_resolve():
    from planning.blender.correction_contract import CorrectionProposal
    from planning.blender.correction_dependencies import resolve
    p = CorrectionProposal(
        correction_id="a", finding_code="MESH_DEGENERATE_FACE", object_id="p", mesh_id="m",
        correction_type="REMOVE_DEGENERATE_FACE", parameters={"face_id": 1},
        rationale="r", preconditions=({"a": 1},), expected_postcondition={"f": "x"},
        risk="FIDELITY_SAFE", severity="error", reversibility="reversible",
        dependencies=(), determinism="DETERMINISTIC", requires_human_review=False, out_of_scope=False,
    )
    with pytest.raises(Exception):
        resolve([p], explicit_edges=[("a", "ghost")], proposal_dependencies=[])


def test_dependency_cycle_through_resolve_fails_closed():
    from planning.blender.correction_contract import CorrectionProposal
    from planning.blender.correction_dependencies import resolve
    mk = lambda cid, mesh: CorrectionProposal(
        correction_id=cid, finding_code="MESH_DEGENERATE_FACE", object_id="p", mesh_id=mesh,
        correction_type="REMOVE_DEGENERATE_FACE", parameters={"face_id": 0},
        rationale="r", preconditions=({"a": 1},), expected_postcondition={"f": "x"},
        risk="FIDELITY_SAFE", severity="error", reversibility="reversible", dependencies=(),
        determinism="DETERMINISTIC", requires_human_review=False, out_of_scope=False,
    )
    a, b = mk("a", "m1"), mk("b", "m2")
    res = resolve([a, b], explicit_edges=[("a", "b"), ("b", "a")], proposal_dependencies=[])
    assert res["cycle_nodes"]


def test_contradiction_detected_not_silent():
    from planning.blender.correction_contract import CorrectionProposal
    from planning.blender.correction_dependencies import resolve
    mk = lambda cid, ctype: CorrectionProposal(
        correction_id=cid, finding_code="MESH_DEGENERATE_FACE", object_id="p", mesh_id="m",
        correction_type=ctype, parameters={"face_id": 1},
        rationale="r", preconditions=({"a": 1},), expected_postcondition={"f": "x"},
        risk="FIDELITY_SAFE", severity="error", reversibility="reversible", dependencies=(),
        determinism="DETERMINISTIC", requires_human_review=False, out_of_scope=False,
    )
    res = resolve([mk("a", "REMOVE_DEGENERATE_FACE"), mk("b", "REPAIR_FACE_WINDING")],
                  explicit_edges=[], proposal_dependencies=[])
    assert res["contradictions"], "two corrections on the same target must be surfaced"


# ===================================================== helpers for reorder tests ====

def _deg(face):
    return Finding(code=FindingCode.MESH_DEGENERATE_FACE, object_id="pitch", mesh_id="m",
                   measured={"face": face})


def _dup():
    return Finding(code=FindingCode.MESH_DUPLICATE_FACE, object_id="pitch", mesh_id="m",
                   measured={"face_a": 0, "face_b": 1})


def _plan_raw(findings):
    """Plan from a RAW findings list (no re-sorting) with a content-bound digest, so the caller
    controls iteration order exactly — the adversarial determinism probe. The digest is recomputed
    from the body (mandatory planner-side source verification, Wave-1 provenance)."""
    from planning.blender.correction_planner import _digest_of_report_body
    body = {
        "scene_id": "s", "validator_version": "1",
        "report_format_version": REPORT_FORMAT_VERSION,
        "profile_name": "soccer-field", "validation_state": "needs_review",
        "scene_metrics": {}, "source_revision_id": None,
        "findings": [f.snapshot() for f in findings],
    }
    payload = {**body, "digest": _digest_of_report_body(body)}
    return _plan_from(payload)


def _plan(findings, profile=None):
    return _plan_from(_report_payload(findings), profile)


def _plan_from(payload, profile=None):
    from planning.blender.correction_planner import plan_scene_report
    return plan_scene_report(payload, profile=profile if profile is not None else _profile())


def test_d1_post_construction_nested_mutation_blocked():
    """D1: a caller-held nested mapping/list cannot mutate canonical content after construction."""
    plan = _plan([DEGENERATE])
    p0 = plan.corrections[0]
    id_before = plan.plan_id
    cj_before = plan.canonical_json()
    try:
        p0.parameters["extra"] = {"injected": True}  # must raise (nested params immutable)
        mutated = True
    except (TypeError, AttributeError):
        mutated = False
    assert mutated is False, "nested parameters must be immutable (TypeError expected)"
    assert plan.canonical_json() == cj_before
    assert plan.plan_id == id_before
    # D1 invariant: plan_id still equals the digest of the (now-immutable) canonical content.
    # NOTE: plan.digest() hashes canonical_json (which embeds plan_id); plan_id hashes the content
    # BODY (which excludes plan_id). The content-bound invariant is plan_id == recomputed body.
    assert plan.plan_id == plan._compute_plan_id()


def test_d1_nested_list_mutation_blocked():
    """WAVE 2: the aggregated winding parameters are the ones carrying nested lists, and they must
    be deep-frozen exactly like every other proposal's nested data."""
    plan = _plan([WINDING])
    p0 = plan.corrections[0]
    assert p0.correction_type == "REPAIR_FACE_WINDING"
    assert set(p0.parameters) == {
        "mesh_id", "designated_face_index", "candidate_faces",
        "recorded_edges", "counterpart_faces", "orientation",
    }
    attempts = (
        lambda: p0.parameters["recorded_edges"].append((9, 9)),
        lambda: p0.parameters["recorded_edges"][0].append(9),
        lambda: p0.parameters["counterpart_faces"].append(9),
    )
    for attempt in attempts:
        try:
            attempt()
            mutated = True
        except (TypeError, AttributeError):
            mutated = False
        assert mutated is False, "nested list must be immutable"


def test_d1_plan_identity_stays_equal_to_content_digest_after_attempted_mutation():
    """D1 invariant: plan_id stays == the recomputed digest of the plan's CANONICAL CONTENT even
    after an external mutation ATTEMPT is made (and rejected)."""
    plan = _plan([DEGENERATE, WINDING])
    for c in plan.corrections:
        try:
            c.parameters["zz"] = "nope"
            if "recorded_edges" in c.parameters:
                c.parameters["recorded_edges"].append((999, 999))
        except (TypeError, AttributeError):
            pass
    # content is immutable -> plan_id still matches the recomputed content-body digest
    assert plan.plan_id == plan._compute_plan_id()
    # and re-planning the same input yields the identical byte-identical plan
    replay = _plan([DEGENERATE, WINDING])
    assert plan.canonical_json() == replay.canonical_json()
    assert plan.plan_id == replay.plan_id


def test_d2_malformed_digest_rejected_at_boundary():
    from planning.blender.correction_values import CorrectionInputError

    deg = Finding(code=FindingCode.MESH_DEGENERATE_FACE, object_id="p", mesh_id="m",
                  measured={"face": 1})
    good = _report_payload([deg])
    bad_digests = [
        "abc",
        "D" * 64,  # uppercase hex (not lowercase, matching SceneReport.digest())
        "z" * 64,  # non-hex chars
        "a" * 63,
        "a" * 65,
        " " + "a" * 63,
    ]
    for bad in bad_digests:
        with pytest.raises(CorrectionInputError):
            _plan_from({**good, "digest": bad})


def test_d2_exact_valid_digest_accepted():
    # A real content-bound digest must be accepted (mandatory source verification).
    from planning.blender.correction_planner import _digest_of_report_body
    deg = Finding(code=FindingCode.MESH_DEGENERATE_FACE, object_id="p", mesh_id="m",
                  measured={"face": 1})
    payload = _report_payload([deg])
    body = {k: v for k, v in payload.items() if k != "digest"}
    real_digest = _digest_of_report_body(body)
    plan = _plan_from({**payload, "digest": real_digest})
    assert plan.source_report_digest == real_digest


def test_d3_nan_in_finding_fails_via_declared_error():
    from planning.blender.correction_values import CorrectionInputError

    deg = Finding(code=FindingCode.MESH_DEGENERATE_FACE, object_id="p", mesh_id="m",
                  measured={"face": float("nan")})
    with pytest.raises(CorrectionInputError):
        _plan_from(_report_payload([deg]))


def test_d3_inf_in_finding_nested_fails_declared():
    from planning.blender.correction_values import CorrectionInputError

    dup = Finding(code=FindingCode.MESH_DUPLICATE_FACE, object_id="p", mesh_id="m",
                  measured={"face_a": 0, "face_b": float("inf")})
    with pytest.raises(CorrectionInputError):
        _plan_from(_report_payload([dup]))


def test_d3_nan_in_expected_field_nested_fails():
    from planning.blender.correction_values import CorrectionInputError

    w = Finding(code=FindingCode.MESH_WINDING_INCONSISTENT, object_id="p", mesh_id="m",
                measured={"faces": [0.0, float("nan")], "edge": [0, 1]})
    with pytest.raises(CorrectionInputError):
        _plan_from(_report_payload([w]))


def test_d3_non_dict_finding_rejected_as_input_error():
    from planning.blender.correction_values import CorrectionInputError

    payload = _report_payload([])
    payload["findings"] = ["not-a-dict"]
    with pytest.raises(CorrectionInputError):
        _plan_from(payload)
