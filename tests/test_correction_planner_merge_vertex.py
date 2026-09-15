"""Deterministic tests for the Wave-3 ``REPAIR_MERGE_VERTEX`` PLANNER path.

Covers the explicitly-requested merge planning entry point
(:func:`planning.blender.correction_planner.plan_merge_vertex_correction`, design §1–§7, OI-2
"explicit operator request"): kernel finding collection, authoritative-table grouping, the DERIVED
exact-bit/sub-grid case, the canonical survivor, the canonical index mapping and its digest, the
predicted post-merge topology checks, the review-gated proposal, and every refusal state.

There is NO bpy, NO Blender, NO live run, NO mutation and NO executor invocation here: the planner
never mutates geometry, and no merge executor exists in this slice.

Test discipline: every fixture is built from REAL project contracts — `parse_scene_report_input` over a
canonical scene payload, the real `mesh_health` kernel for the findings, `build_report` +
`SceneReport.digest()` for the source binding (never a hand-written digest), and the real
`CorrectionPlan`/`CorrectionProposal` machinery for the ids, so nothing fakes a plan id or bypasses
artifact integrity. Negative tests assert STRUCTURED refusal codes exactly, never message substrings.
"""
import ast
import inspect
import json

import pytest

from planning.blender import correction_planner as planner
from planning.blender import mesh_health as kernel
from planning.blender.correction_codes import PlannerState
from planning.blender.correction_planner import (
    MERGE_FINDING_CODE,
    MERGE_PARAMETER_KEYS,
    MergePlanningCode,
    plan_merge_vertex_correction,
    plan_scene_report,
)
from planning.blender.finding_codes import FindingCode
from planning.blender.scene_model import parse_scene_report_input
from planning.blender.scene_report import REPORT_FORMAT_VERSION, Finding, build_report

MESH_ID = "pitch_mesh"
OBJECT_ID = "pitch"
PROFILE = {
    "name": "soccer-field",
    "version": "1",
    "allowed_units": ["METERS", "meters", "m"],
    "name_pattern": r"^[a-z0-9][a-z0-9._-]*$",
}
#: A clean target mesh whose vertex 3 is an EXACT-BIT duplicate of vertex 0.
TRIPLE = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
EXACT_PAIR_VERTICES = TRIPLE + ((0.0, 0.0, 0.0),)
EXACT_TRIPLE_VERTICES = TRIPLE + ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
SUB_GRID_VERTICES = TRIPLE + ((1e-7, 0.0, 0.0),)
CLEAN_FACE = ((0, 1, 2),)


def scene_payload(*meshes, scene_id="merge_scene", unit_system="METERS"):
    """Canonical scene payload (meshes: (object_id, mesh_id, vertices, faces))."""
    return {
        "scene_id": scene_id,
        "unit_system": unit_system,
        "objects": [
            {
                "object_id": object_id,
                "name": object_id,
                "mesh": {
                    "mesh_id": mesh_id,
                    "vertices": [list(vertex) for vertex in vertices],
                    "faces": [list(face) for face in faces],
                },
            }
            for object_id, mesh_id, vertices, faces in meshes
        ],
    }


def kernel_duplicate_findings(scene, mesh_id):
    """The REAL kernel's MESH_DUPLICATE_VERTEX findings for one mesh of a parsed scene."""
    model = parse_scene_report_input(scene)
    findings = []
    for obj in model.objects:
        if obj.mesh is None or obj.mesh.mesh_id != mesh_id:
            continue
        findings.extend(
            finding for finding in kernel.check_mesh(obj.mesh)
            if finding.code is FindingCode.MESH_DUPLICATE_VERTEX
        )
    return findings


def report_payload(scene, mesh_id, *, drop_pairs=(), omit_mesh_id=False, mutate_measured=None):
    """A REAL SceneReport-shaped payload bound to its own digest (never hand-written)."""
    findings = []
    for finding in kernel_duplicate_findings(scene, mesh_id):
        measured = finding.measured or {}
        if (measured.get("vertex_a"), measured.get("vertex_b")) in {tuple(p) for p in drop_pairs}:
            continue
        if mutate_measured is not None:
            measured = mutate_measured(dict(measured))
        findings.append(
            Finding(
                code=finding.code,
                object_id=finding.object_id,
                mesh_id=None if omit_mesh_id else finding.mesh_id,
                measured=measured,
                expected=finding.expected,
                message=finding.message,
            )
        )
    report = build_report(
        scene_id="merge_scene",
        validation_state="needs_review",
        findings=findings,
        scene_metrics={},
        profile_name="soccer-field",
    )
    payload = report.to_json_compatible()
    payload["digest"] = report.digest()
    payload["report_format_version"] = REPORT_FORMAT_VERSION
    return payload


def plan(scene, mesh_id=MESH_ID, **report_kwargs):
    """Run the explicit merge planning pass over a real report/scene pair."""
    return plan_merge_vertex_correction(
        report_payload(scene, mesh_id, **report_kwargs), scene, profile=PROFILE
    )


def params(proposal):
    """The proposal's parameters at the CANONICAL JSON boundary (what a future executor consumes).

    ``CorrectionProposal`` deep-freezes its parameters, so the in-memory form is tuples; asserting on
    the serialized form checks the boundary the executor will actually read.
    """
    return proposal.to_json_compatible()["parameters"]


def single_proposal(outcome):
    assert outcome.refusal_code is None, outcome.refusal_detail
    assert len(outcome.plan.corrections) == 1
    return outcome.plan.corrections[0]


# ===========================================================================
# 1-6. GROUPING, SURVIVOR AND ORDERING
# ===========================================================================


def test_no_duplicate_vertices_produces_no_merge_proposal():
    scene = scene_payload((OBJECT_ID, MESH_ID, TRIPLE, CLEAN_FACE))
    outcome = plan(scene)
    assert outcome.plan.corrections == ()
    assert outcome.plan.state == PlannerState.NO_CORRECTIONS.value
    assert outcome.refusal_code is None


def test_single_exact_bit_pair_produces_one_review_required_proposal():
    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_PAIR_VERTICES, CLEAN_FACE))
    outcome = plan(scene)
    proposal = single_proposal(outcome)
    assert outcome.plan.state == PlannerState.REVIEW_REQUIRED.value
    assert proposal.correction_type == "REPAIR_MERGE_VERTEX"
    assert proposal.finding_code == MERGE_FINDING_CODE.value
    assert proposal.requires_human_review is True
    assert proposal.object_id == OBJECT_ID
    assert proposal.mesh_id == MESH_ID
    assert tuple(proposal.parameters.keys()) == MERGE_PARAMETER_KEYS
    assert tuple(params(proposal).keys()) == MERGE_PARAMETER_KEYS
    assert params(proposal)["duplicate_groups"] == [[0, 3]]
    assert params(proposal)["recorded_pairs"] == [[0, 3]]
    assert params(proposal)["survivor_indices"] == [0]
    assert params(proposal)["all_groups_exact"] is True


def test_three_member_exact_group_uses_the_canonical_survivor():
    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_TRIPLE_VERTICES, CLEAN_FACE))
    proposal = single_proposal(plan(scene))
    assert params(proposal)["duplicate_groups"] == [[0, 3, 4]]
    assert params(proposal)["recorded_pairs"] == [[0, 3], [0, 4]]
    assert params(proposal)["survivor_indices"] == [0]
    assert params(proposal)["survivor_indices"] == [min(params(proposal)["duplicate_groups"][0])]


def test_transitive_duplicate_group_closes_over_the_pair_evidence():
    """0-3 and 0-4 are one class; the closure must be ONE group, not two."""
    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_TRIPLE_VERTICES, CLEAN_FACE))
    proposal = single_proposal(plan(scene))
    assert len(params(proposal)["duplicate_groups"]) == 1
    assert params(proposal)["duplicate_groups"][0] == [0, 3, 4]


def test_interleaved_group_indices_are_grouped_by_coincidence_not_by_proximity():
    """Duplicate members at 0/3 (interleaved with a non-member at 1/2) still close into one group."""
    vertices = ((0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (0.0, 5.0, 0.0), (0.0, 0.0, 0.0))
    scene = scene_payload((OBJECT_ID, MESH_ID, vertices, ((0, 1, 2),)))
    proposal = single_proposal(plan(scene))
    assert params(proposal)["duplicate_groups"] == [[0, 3]]
    assert params(proposal)["old_to_new_mapping"] == [0, 1, 2, 0]


def test_group_and_pair_ordering_is_deterministic_and_canonical():
    vertices = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
                (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    scene = scene_payload((OBJECT_ID, MESH_ID, vertices, CLEAN_FACE))
    proposal = single_proposal(plan(scene))
    assert params(proposal)["duplicate_groups"] == [[0, 3, 4], [1, 5]]
    assert params(proposal)["survivor_indices"] == [0, 1]
    assert params(proposal)["recorded_pairs"] == [[0, 3], [0, 4], [1, 5]]


# ===========================================================================
# 7-12. CASE, REFUSALS AND TARGET SCOPE
# ===========================================================================


def test_same_key_sub_grid_coordinates_are_refused():
    scene = scene_payload((OBJECT_ID, MESH_ID, SUB_GRID_VERTICES, CLEAN_FACE))
    outcome = plan(scene)
    assert outcome.refusal_code == MergePlanningCode.SUB_GRID_COLLAPSE_UNSUPPORTED
    assert outcome.plan.corrections == ()
    assert outcome.plan.state == PlannerState.REVIEW_REQUIRED.value


def test_half_to_even_boundary_coordinates_are_classified_by_the_kernel_rule():
    """0.5e-6 rounds to 0.0 (same key as 0.0) but is NOT bit-identical -> sub-grid refusal."""
    vertices = TRIPLE + ((0.0000005, 0.0, 0.0),)
    outcome = plan(scene_payload((OBJECT_ID, MESH_ID, vertices, CLEAN_FACE)))
    assert outcome.refusal_code == MergePlanningCode.SUB_GRID_COLLAPSE_UNSUPPORTED
    # 1.5e-6 rounds to 2e-6 (a DIFFERENT key), so it is not even a coincidence class.
    other = TRIPLE + ((0.0000015, 0.0, 0.0),)
    assert plan(scene_payload((OBJECT_ID, MESH_ID, other, CLEAN_FACE))).plan.corrections == ()


def test_invented_or_non_kernel_group_cannot_be_produced():
    """A declared pair the authoritative table does not support is refused, never grouped."""
    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_PAIR_VERTICES, CLEAN_FACE))
    forged_finding = Finding(
        code=FindingCode.MESH_DUPLICATE_VERTEX,
        object_id=OBJECT_ID,
        mesh_id=MESH_ID,
        measured={"vertex_a": 0, "vertex_b": 1, "coordinate": [0.0, 0.0, 0.0]},
    )
    report = build_report(scene_id="merge_scene", validation_state="needs_review",
                          findings=[forged_finding], scene_metrics={},
                          profile_name="soccer-field")
    forged = report.to_json_compatible()
    forged["digest"] = report.digest()
    forged["report_format_version"] = REPORT_FORMAT_VERSION
    outcome = plan_merge_vertex_correction(forged, scene, profile=PROFILE)
    assert outcome.refusal_code == MergePlanningCode.GROUP_MISMATCH
    assert outcome.plan.corrections == ()


def test_missing_mesh_identity_is_a_planning_error():
    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_PAIR_VERTICES, CLEAN_FACE))
    outcome = plan(scene, omit_mesh_id=True)
    assert outcome.refusal_code == MergePlanningCode.TARGET_MESH_UNRESOLVED
    assert outcome.plan.state == PlannerState.PLANNING_ERROR.value
    assert outcome.plan.corrections == ()


def test_cross_mesh_aggregation_is_refused():
    scene = scene_payload(
        (OBJECT_ID, MESH_ID, EXACT_PAIR_VERTICES, CLEAN_FACE),
        ("goal", "goal_mesh", EXACT_PAIR_VERTICES, CLEAN_FACE),
    )
    model = parse_scene_report_input(scene)
    findings = []
    for obj in model.objects:
        findings.extend(f for f in kernel.check_mesh(obj.mesh)
                        if f.code is FindingCode.MESH_DUPLICATE_VERTEX)
    report = build_report(scene_id="merge_scene", validation_state="needs_review",
                          findings=findings, scene_metrics={}, profile_name="soccer-field")
    payload = report.to_json_compatible()
    payload["digest"] = report.digest()
    payload["report_format_version"] = REPORT_FORMAT_VERSION
    outcome = plan_merge_vertex_correction(payload, scene, profile=PROFILE)
    assert outcome.refusal_code == MergePlanningCode.MULTI_CORRECTION_REFUSED
    assert outcome.plan.corrections == ()


def test_partial_group_coverage_is_refused_never_inferred():
    """Three coincident vertices but only one pair reported -> the missing member is never inferred."""
    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_TRIPLE_VERTICES, CLEAN_FACE))
    outcome = plan(scene, drop_pairs=[(0, 4)])
    assert outcome.refusal_code == MergePlanningCode.PARTIAL_GROUP_COVERAGE
    assert outcome.plan.corrections == ()
    assert outcome.plan.state == PlannerState.REVIEW_REQUIRED.value


# ===========================================================================
# 13-17. MAPPING AND PREDICTED TOPOLOGY
# ===========================================================================


def test_mapping_is_canonical_and_derived_from_the_vertex_table():
    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_TRIPLE_VERTICES, CLEAN_FACE))
    proposal = single_proposal(plan(scene))
    assert params(proposal)["old_to_new_mapping"] == [0, 1, 2, 0, 0]
    mapping = list(proposal.parameters["old_to_new_mapping"])
    assert len(mapping) == len(EXACT_TRIPLE_VERTICES)
    survivors = set(proposal.parameters["survivor_indices"])
    for index, target in enumerate(mapping):
        if index in survivors:
            assert target == mapping[index]
    assert sorted(set(mapping)) == [0, 1, 2]


def test_mapping_digest_matches_the_authorization_contract_digest():
    from planning.blender.correction_authorization import mapping_digest

    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_PAIR_VERTICES, CLEAN_FACE))
    proposal = single_proposal(plan(scene))
    assert proposal.parameters["mapping_digest"] == mapping_digest(
        MESH_ID, len(EXACT_PAIR_VERTICES), tuple(proposal.parameters["old_to_new_mapping"])
    )


def test_mapping_digest_is_deterministic_across_runs_and_finding_order():
    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_TRIPLE_VERTICES, CLEAN_FACE))
    first = single_proposal(plan(scene)).parameters["mapping_digest"]
    second = single_proposal(plan(scene)).parameters["mapping_digest"]
    assert first == second
    reversed_report = report_payload(scene, MESH_ID)
    reversed_report["findings"] = list(reversed(reversed_report["findings"]))
    # a reversed finding order would break the digest binding, so rebuild it honestly
    report = build_report(scene_id="merge_scene", validation_state="needs_review",
                          findings=sorted(kernel_duplicate_findings(scene, MESH_ID),
                                          key=lambda f: (f.measured["vertex_b"], f.measured["vertex_a"])),
                          scene_metrics={}, profile_name="soccer-field")
    payload = report.to_json_compatible()
    payload["digest"] = report.digest()
    payload["report_format_version"] = REPORT_FORMAT_VERSION
    third = single_proposal(
        plan_merge_vertex_correction(payload, scene, profile=PROFILE)
    ).parameters["mapping_digest"]
    assert first == third


def test_predicted_duplicate_face_consequence_is_refused():
    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_PAIR_VERTICES, ((0, 1, 2), (3, 1, 2))))
    outcome = plan(scene)
    assert outcome.refusal_code == MergePlanningCode.TOPOLOGY_CONSEQUENCE_PREDICTED
    assert outcome.plan.corrections == ()
    assert "MESH_DUPLICATE_FACE" in (outcome.refusal_detail or "")


def test_predicted_degenerate_face_consequence_is_refused_before_prediction():
    """A face that would repeat an index post-merge is refused by MP-5 (the guard that makes the
    predicted-degenerate class unreachable for a conforming exact-bit merge)."""
    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_PAIR_VERTICES, ((0, 3, 2),)))
    outcome = plan(scene)
    assert outcome.refusal_code == MergePlanningCode.FACE_REPEATS_GROUP_MEMBERS
    assert outcome.plan.corrections == ()


def test_invalid_mapped_face_index_is_refused():
    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_PAIR_VERTICES, ((0, 1, 99),)))
    outcome = plan(scene)
    assert outcome.refusal_code == MergePlanningCode.TOPOLOGY_CONSEQUENCE_PREDICTED
    assert outcome.plan.corrections == ()


# ===========================================================================
# 18-19. PLAN / CORRECTION IDENTITY
# ===========================================================================


def test_plan_and_correction_ids_are_deterministic():
    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_PAIR_VERTICES, CLEAN_FACE))
    first, second = plan(scene), plan(scene)
    assert first.plan.plan_id == second.plan.plan_id
    assert (single_proposal(first).correction_id
            == single_proposal(second).correction_id)
    assert len(first.plan.plan_id) == 64


def test_plan_changes_when_an_authority_bearing_parameter_changes():
    pair_scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_PAIR_VERTICES, CLEAN_FACE))
    triple_scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_TRIPLE_VERTICES, CLEAN_FACE))
    pair_plan = plan(pair_scene)
    triple_plan = plan(triple_scene)
    assert pair_plan.plan.plan_id != triple_plan.plan.plan_id
    assert (single_proposal(pair_plan).correction_id
            != single_proposal(triple_plan).correction_id)
    other_mesh = scene_payload((OBJECT_ID, "other_mesh", EXACT_PAIR_VERTICES, CLEAN_FACE))
    assert plan(other_mesh, mesh_id="other_mesh").plan.plan_id != pair_plan.plan.plan_id


def test_plan_binds_the_source_report_digest():
    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_PAIR_VERTICES, CLEAN_FACE))
    payload = report_payload(scene, MESH_ID)
    outcome = plan_merge_vertex_correction(payload, scene, profile=PROFILE)
    assert outcome.plan.source_report_digest == payload["digest"]
    assert outcome.plan.corrections[0].preconditions[0] == {
        "source_report_digest": payload["digest"]
    }


def test_forged_source_digest_is_refused():
    from planning.blender.correction_values import CorrectionInputError

    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_PAIR_VERTICES, CLEAN_FACE))
    payload = report_payload(scene, MESH_ID)
    payload["findings"] = []
    with pytest.raises(CorrectionInputError):
        plan_merge_vertex_correction(payload, scene, profile=PROFILE)


# ===========================================================================
# 20-21. all_groups_exact IS DERIVED, NEVER TRUSTED
# ===========================================================================


def test_all_groups_exact_is_derived_from_the_vertex_table():
    exact = plan(scene_payload((OBJECT_ID, MESH_ID, EXACT_PAIR_VERTICES, CLEAN_FACE)))
    assert single_proposal(exact).parameters["all_groups_exact"] is True
    # a sub-grid table cannot reach a proposal at all, so the flag can never be True there
    sub = plan(scene_payload((OBJECT_ID, MESH_ID, SUB_GRID_VERTICES, CLEAN_FACE)))
    assert sub.refusal_code == MergePlanningCode.SUB_GRID_COLLAPSE_UNSUPPORTED
    assert sub.plan.corrections == ()


def test_no_caller_supplied_all_groups_exact_parameter_exists():
    signature = inspect.signature(plan_merge_vertex_correction)
    assert "all_groups_exact" not in signature.parameters
    assert set(signature.parameters) == {"report", "scene_input", "profile", "planner_version"}


def test_presented_all_groups_exact_flag_cannot_make_a_sub_grid_group_executable():
    """Smuggling the flag into the presented finding evidence changes nothing: the case is derived."""
    scene = scene_payload((OBJECT_ID, MESH_ID, SUB_GRID_VERTICES, CLEAN_FACE))
    outcome = plan(scene, mutate_measured=lambda measured: {**measured, "all_groups_exact": True})
    assert outcome.refusal_code == MergePlanningCode.SUB_GRID_COLLAPSE_UNSUPPORTED
    assert outcome.plan.corrections == ()
    assert "all_groups_exact" not in json.dumps(outcome.plan.planning_errors)


def test_executor_flag_is_documented_as_advisory_and_must_be_re_derived():
    """The planner records the derived case; the plan never claims authority over the flag."""
    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_PAIR_VERTICES, CLEAN_FACE))
    proposal = single_proposal(plan(scene))
    assert proposal.parameters["all_groups_exact"] is True
    assert proposal.requires_human_review is True
    source = inspect.getsource(planner)
    assert "must never treat ``all_groups_exact`` as evidence" in source
    assert "MUST re-derive" in source


# ===========================================================================
# DISPATCH (design §11 / OI-2): the automatic pass still emits NO merge proposal
# ===========================================================================


def test_automatic_pass_emits_no_merge_proposal():
    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_PAIR_VERTICES, CLEAN_FACE))
    plan_auto = plan_scene_report(report_payload(scene, MESH_ID), profile=PROFILE)
    assert plan_auto.corrections == ()
    assert plan_auto.state == PlannerState.REVIEW_REQUIRED.value


def test_automatic_pass_is_unchanged_for_a_wave1_fixture():
    """The same report through the automatic pass still yields no merge correction of any kind."""
    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_TRIPLE_VERTICES, CLEAN_FACE))
    plan_auto = plan_scene_report(report_payload(scene, MESH_ID), profile=PROFILE)
    assert all(c.correction_type != "REPAIR_MERGE_VERTEX" for c in plan_auto.corrections)


def test_merge_proposal_is_never_executable_by_itself():
    """No execution authority: no executor import, review-gated, and the plan carries no mutation."""
    scene = scene_payload((OBJECT_ID, MESH_ID, EXACT_PAIR_VERTICES, CLEAN_FACE))
    proposal = single_proposal(plan(scene))
    assert proposal.requires_human_review is True
    assert proposal.out_of_scope is False
    assert proposal.dependencies == ()
    assert "correction_executor" not in inspect.getsource(planner)


# ===========================================================================
# 22. CODE BOUNDARY (no bpy / I/O / clock / randomness / mutation surface)
# ===========================================================================

_FORBIDDEN_IMPORTS = {
    "bpy", "bpy_extras", "os", "subprocess", "shutil", "socket", "time", "random", "uuid",
    "secrets", "threading", "multiprocessing", "tempfile", "pathlib", "sqlite3",
}
_FORBIDDEN_NAMES = {
    "from_pydata", "save_as_mainfile", "save_mainfile", "rollback", "recover", "persist",
    "Popen", "system", "execv", "spawn", "bpy",
}


def _planner_source():
    return open(planner.__file__, encoding="utf-8").read()


def test_planner_imports_no_forbidden_module():
    tree = ast.parse(_planner_source())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not (imported & _FORBIDDEN_IMPORTS), sorted(imported & _FORBIDDEN_IMPORTS)


def test_planner_contains_no_forbidden_authority_name():
    tree = ast.parse(_planner_source())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
    assert not (found & _FORBIDDEN_NAMES), sorted(found & _FORBIDDEN_NAMES)


def test_merge_path_does_not_import_the_executor():
    source = _planner_source()
    assert "correction_executor" not in source
    assert "execute_repair_merge_vertex" not in source
