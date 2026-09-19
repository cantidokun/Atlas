"""LIVE Blender gate for W2 ``REPAIR_FACE_WINDING`` (Wave 15, gate family 2 — authorization-aware).

Operator-gated; NOT run in CI. Runs the real Blender 4.4.3 process against the disposable in-memory
fixtures built by ``tests/w2_winding_live_script.py`` and asserts the complete live path::

    live Blender scene -> real extraction -> SceneModel/SceneReport -> REAL planner (D1/D2/D3)
    -> REAL AuthorizationArtifact (correction_authorization contract)
    -> execute_repair_face_winding (plan integrity -> allowlist -> parameter allowlist
       -> AUTHORIZATION GATE -> source binding -> WC-P6..P17 -> authorization_verified
       -> exactly one bounded mutation -> fresh extraction -> WC-Q1..Q13 -> receipt)
    -> REAL Blender mutation (Wave 14 Pattern B) -> raw boundary evidence

Explicit authorized run only::

    ATLAS_RUN_LIVE_BLENDER=1 .venv/Scripts/python.exe -m pytest \\
        tests/test_live_blender_w2_winding_gate.py -s

This is a SEPARATE gate family from the W1/W1b face-removal harness (design §H.2): different executor
entry point, mandatory authorization BEFORE engine contact, a closed parameter set, the WC-P*/WC-Q*
vocabulary and a D1/D2 designation model. Nothing about the W1/W1b implementation is reused in a way
that would hide W2's authorization semantics, and W1/W1b production code is untouched by this task.

AUTHORITY MODEL (asserted live, read from the repository's own mapping module):
``MESH_WINDING_INCONSISTENT`` is ``HEURISTIC`` / ``REPAIR_FACE_WINDING`` / ``FIDELITY_GEOMETRY`` /
``PARTIALLY_REVERSIBLE`` / ``auto_propose=True``, and the emitted proposal carries
``requires_human_review=True``. Authorization is therefore MANDATORY: this gate never treats plan
state (``REVIEW_REQUIRED``) as authorization, and every execution presents a real artifact.

``authorization_verified == True`` DOES NOT MEAN THE CORRECTION SUCCEEDED. It means the authorization
bindings AND the fresh-evidence preconditions (WC-P6..P17) passed immediately before the single
bounded mutation. The no-op-after-accepted-authorization case here asserts exactly that: a valid
artifact, ``authorization_verified == True``, one mutator invocation, no effective reversal, and
``POSTCONDITION_FAILED`` / ``WC-Q1`` on the receipt. Authorization is never used as a success flag.

ORDERING PROOF (design §E): the extractor invocation counter is asserted per case, so the gate proves
that no authorization-rejected path consumed ANY Blender engine contact (0 extractions, 0 mutations),
that source/precondition refusals consumed exactly the source extraction (1, 0 mutations), and that
only accepted executions performed the source + fresh-post extraction pair (2).

REQUIRED NON-CLAIM (design §G) — repeated in gate documentation exactly as §G/F.1 mandate::

    Pattern B rebuild resets polygon.material_index. mesh.clear_geometry() followed by
    mesh.from_pydata(...) reconstructs every polygon with material_index == 0; per-face material
    assignment does NOT survive a geometry rebuild. Polygon material assignment is OUTSIDE the frozen
    Atlas representation contract. This gate makes NO claim that per-face material assignment
    survives, and it must never assert material_index preservation.

RAW-EVIDENCE CONTAINMENT (design §F.1, red-team F-4): raw slot tables, datablock identity/inventory,
orphan detection and unrelated-object material state are TEST-ONLY boundary evidence — test/gate code
only, never imported by production, never promoted into a production assertion/validator library, and
never a hidden canonical Atlas contract. The W2 executor carries no material or datablock clause.

ADAPTER DISCIPLINE (carried forward from the W1/W1b red-team refinement): **one mutator invocation =
one intended bounded engine edit**. The canonical contract observes the mutator invocation plus the
fresh post-state; it does NOT audit arbitrary internal bpy call sequences, and no production
instrumentation was added to try. The ``two-engine-edits`` case (three internal rebuilds ending on the
authorized canonical state, COMPLETED with ``engine_edits == 3``) is documented and asserted as that
observable boundary rather than being hidden.

DOCUMENTED UNREACHABILITY (asserted by reachability probes, never invented as an executable case):
  * ``WC-Q7`` "a reversal creates a new duplicate" — the exact reversal of the designated face has the
    same vertex set, so a same-vertex-set twin makes the winding edge NON-MANIFOLD (incidence 3); the
    pre-state then carries no winding finding and no W2 plan exists. Measured live.
  * ``WC-P14`` duplicate clause — reachable ONLY through a contract-legal plan that the real aggregator
    provably cannot emit for such a report (measured: intersection is not a single face -> D3-style
    non-emission). It is executed live through a contract-legal synthetic plan, and the reachability
    probe records why the planner cannot produce one.
  * D3 (empty candidate-face intersection) — planner non-emission only: NO artifact is fabricated and
    no execution is attempted. A live D1 control in the same probe proves the non-emission discriminates.
"""

import hashlib
import json
import os
import subprocess

import pytest

FROZEN_ASSET = os.path.join("tests", "assets", "blender", "atlas_transform_validation.blend")
FROZEN_SHA256 = "cf618bdc1123734bf49bf6f22677ded3f2e6c3fa2803b97f7a6cf7c7c66f11aa"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "tests", "w2_winding_live_script.py")

W2 = "REPAIR_FACE_WINDING"
WINDING = "MESH_WINDING_INCONSISTENT"
DEG = "MESH_DEGENERATE_FACE"
DV = "MESH_DUPLICATE_FACE"
NON_MANIFOLD = "MESH_NON_MANIFOLD_EDGE"
INVALID_INDEX = "MESH_INVALID_INDEX"

#: the frozen W2 receipt skeleton for ``execute_repair_face_winding`` (pinned so schema drift fails
#: loudly instead of passing silently)
RECEIPT_FIELD_COUNT = 27

#: production modules that MUST NOT change (byte-identical before/after the live run)
PRODUCTION_FILES = (
    "planning/blender/bpy_extraction.py",
    "planning/blender/extraction_payload.py",
    "planning/blender/scene_model.py",
    "planning/blender/kernel.py",
    "planning/blender/scene_report.py",
    "planning/blender/correction_planner.py",
    "planning/blender/correction_authorization.py",
    "planning/blender/correction_executor.py",
    "planning/blender/correction_mapping.py",
)

#: every §E.1 authorization negative row present in the live case table
AUTHORIZATION_NEGATIVES = (
    "w2-negative-authorization-absent-d2",
    "w2-negative-authorization-absent-d1",
    "w2-negative-artifact-malformed-json",
    "w2-negative-artifact-json-not-an-object",
    "w2-negative-artifact-not-a-mapping",
    "w2-negative-artifact-missing-required-field",
    "w2-negative-artifact-duplicate-json-key",
    "w2-negative-authorization-version-unsupported",
    "w2-negative-policy-version-unsupported",
    "w2-negative-decision-not-approved",
    "w2-negative-correction-type-not-authorizable",
    "w2-negative-correction-type-mismatch",
    "w2-negative-correction-id-mismatch",
    "w2-negative-plan-id-mismatch",
    "w2-negative-source-digest-mismatch",
    "w2-negative-artifact-unknown-field",
    "w2-negative-artifact-digest-format-invalid",
    "w2-negative-d2-designation-required",
    "w2-negative-d2-designation-outside-candidate-pair",
    "w2-negative-d2-designation-is-counterpart",
    "w2-negative-d1-designation-supplied",
)

#: the subset of authorization negatives that must consume NO engine contact at all
NO_ENGINE_CONTACT_NEGATIVES = tuple(
    label for label in AUTHORIZATION_NEGATIVES
    if label not in ("w2-negative-d2-designation-is-counterpart",)
)


def _live_enabled() -> bool:
    return os.environ.get("ATLAS_RUN_LIVE_BLENDER", "") == "1"


pytestmark = [pytest.mark.skipif(not _live_enabled(), reason="live Blender gate off")]


def _sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _blend_files():
    found = {}
    for root, _dirs, files in os.walk(REPO):
        if ".venv" in root or ".git" in root or "__pycache__" in root:
            continue
        for name in files:
            if name.endswith(".blend") or name.endswith(".blend1"):
                full = os.path.join(root, name)
                found[full] = (_sha256(full), os.path.getmtime(full))
    return found


@pytest.fixture(scope="module")
def live_results():
    import tools.blender as tb

    blends_before = _blend_files()
    assert _sha256(os.path.join(REPO, FROZEN_ASSET)) == FROZEN_SHA256, "frozen asset already differs"
    production_before = {rel: _sha256(os.path.join(REPO, rel)) for rel in PRODUCTION_FILES}

    env = dict(os.environ)
    env["PYTHONPATH"] = REPO
    proc = subprocess.run(
        [tb.BLENDER, "--background", "--python", SCRIPT],
        capture_output=True, text=True, timeout=900, cwd=REPO, env=env,
    )
    stdout = proc.stdout
    start = stdout.find("ATLAS_W2_LIVE_START")
    end = stdout.find("ATLAS_W2_LIVE_END")
    assert proc.returncode == 0, f"blender rc={proc.returncode}: {proc.stderr[-3000:]}"
    assert start != -1 and end != -1, f"live markers missing\n{stdout[-4000:]}"
    results = json.loads(stdout[start + len("ATLAS_W2_LIVE_START"):end].strip())

    blends_after = _blend_files()
    assert blends_after == blends_before, "a .blend/.blend1 file was created or modified"
    assert _sha256(os.path.join(REPO, FROZEN_ASSET)) == FROZEN_SHA256, "frozen asset changed"
    production_after = {rel: _sha256(os.path.join(REPO, rel)) for rel in PRODUCTION_FILES}
    assert production_after == production_before, "a production module changed during the live run"

    results["_blend_snapshot_unchanged"] = True
    results["_frozen_before"] = FROZEN_SHA256
    results["_frozen_after"] = _sha256(os.path.join(REPO, FROZEN_ASSET))
    results["_production_hashes_before"] = production_before
    results["_production_hashes_after"] = production_after
    return results


def _case(results, label):
    for case in results["cases"]:
        if case["case"] == label:
            return case
    raise AssertionError(f"case {label} missing; errors={results['errors']}")


def _raw_object(snapshot, name):
    return next(o for o in snapshot["objects"] if o["name"] == name)


# --------------------------------------------------------------------------- assertion helpers
def assert_equal(actual, expected, label):
    assert actual == expected, f"{label}: expected {expected!r}, got {actual!r}"


def assert_reversal(pre_face, post_face, label):
    """The post tuple must be the EXACT plain reversal of the pre tuple (WC-Q1)."""
    assert post_face == list(reversed(pre_face)), (
        f"{label}: {post_face} is not the exact plain reversal of {pre_face}")


def assert_other_faces_unchanged(pre_faces, post_faces, index, label):
    """Every non-designated face must be bit-identical and in the same ORDER (WC-Q2/WC-Q4)."""
    assert len(pre_faces) == len(post_faces), f"{label}: face count changed"
    for i, (before, after) in enumerate(zip(pre_faces, post_faces)):
        if i == index:
            continue
        assert after == before, f"{label}: non-target face {i} changed {before} -> {after}"


def assert_finding_cleared(pre_hist, post_hist, code, label):
    """The recorded finding class must be cleared for the mesh (WC-Q6/WC-Q13)."""
    assert code in pre_hist, f"{label}: the pre-state was expected to carry {code}"
    assert code not in post_hist, f"{label}: {code} survived the correction: {post_hist.get(code)}"


def assert_no_invalid_index(hist, label):
    assert INVALID_INDEX not in hist, f"{label}: {INVALID_INDEX} present"


def assert_authorization_negative(case, *, expected_result, expected_code):
    """Every §E.1 row: exact result, exact typed code, authorization_verified False, zero mutation,
    no Blender mutation, and no engine contact consumed after the authorization rejection."""
    receipt = case["receipt"]
    assert_equal(receipt["result"], expected_result, f"{case['case']} result")
    assert_equal(receipt["failure_code"], expected_code, f"{case['case']} failure_code")
    assert receipt["authorization_verified"] is False, (
        f"{case['case']}: authorization_verified must stay False on a rejected path")
    assert_equal(case["mutator"]["invocations"], 0, f"{case['case']} mutator invocations")
    assert_equal(case["raw_after"], case["raw_before"], f"{case['case']} raw state unchanged")
    assert_equal(case["extractor_calls"], 0, f"{case['case']} engine contact after rejection")
    assert_equal(case["mutator"]["engine_edits"], 0, f"{case['case']} engine edits")
    assert receipt["postcondition_results"] == [], f"{case['case']} no postcondition ran"
    assert receipt["output_report_digest"] is None, f"{case['case']} no fresh report was produced"


def assert_raw_slots(expected_table, actual_table, label):
    assert actual_table == expected_table, (
        f"{label}: raw material slot table changed\n expected={expected_table}\n actual={actual_table}")


def assert_inventory_unchanged(before, after, label):
    assert after == before, f"{label}: datablock inventory changed {before} -> {after}"


def assert_anti_vacuity(view, label):
    assert view["key_present"] is True and view["payload_value"], (
        f"{label}: ANTI-VACUITY FAILURE - this case is meant to be material-bearing but its canonical "
        f"materials evidence is {view!r}")


# --------------------------------------------------------------------------- self-tests (non-vacuity)
def test_selftest_reversal_and_face_assertions_are_live():
    assert_reversal([0, 1, 2], [2, 1, 0], "ok")
    with pytest.raises(AssertionError):     # a rotation is not the exact reversal
        assert_reversal([0, 1, 2], [1, 2, 0], "x")
    with pytest.raises(AssertionError):     # unchanged face
        assert_reversal([0, 1, 2], [0, 1, 2], "x")
    assert_other_faces_unchanged([[0, 1], [2, 3]], [[0, 1], [2, 3]], 0, "ok")
    with pytest.raises(AssertionError):     # a second face was altered
        assert_other_faces_unchanged([[0, 1], [2, 3]], [[0, 1], [3, 2]], 0, "x")
    with pytest.raises(AssertionError):     # a face disappeared
        assert_other_faces_unchanged([[0, 1], [2, 3]], [[0, 1]], 0, "x")


def test_selftest_finding_and_material_assertions_are_live():
    assert_finding_cleared({WINDING: {"count": 1}}, {}, WINDING, "ok")
    with pytest.raises(AssertionError):     # finding survived
        assert_finding_cleared({WINDING: {"count": 1}}, {WINDING: {"count": 1}}, WINDING, "x")
    with pytest.raises(AssertionError):     # class was never there
        assert_finding_cleared({}, {}, WINDING, "x")
    assert_no_invalid_index({WINDING: {"count": 1}}, "ok")
    with pytest.raises(AssertionError):
        assert_no_invalid_index({INVALID_INDEX: {"count": 1}}, "x")
    assert_raw_slots([["DATA", "turf"]], [["DATA", "turf"]], "ok")
    with pytest.raises(AssertionError):
        assert_raw_slots([["DATA", "turf"]], [], "x")
    assert_inventory_unchanged(["goal", "pitch"], ["goal", "pitch"], "ok")
    with pytest.raises(AssertionError):
        assert_inventory_unchanged(["goal", "pitch"], ["goal", "pitch", "pitch.001"], "x")
    assert_anti_vacuity({"key_present": True, "payload_value": ["turf"]}, "ok")
    with pytest.raises(AssertionError):
        assert_anti_vacuity({"key_present": False, "payload_value": None}, "x")


def test_selftest_authorization_negative_assertion_is_live():
    good = {"case": "x", "receipt": {"result": "AUTHORIZATION_REQUIRED",
                                     "failure_code": "AUTHORIZATION_REQUIRED",
                                     "authorization_verified": False,
                                     "postcondition_results": [],
                                     "output_report_digest": None},
            "mutator": {"invocations": 0, "engine_edits": 0},
            "raw_before": {"a": 1}, "raw_after": {"a": 1}, "extractor_calls": 0}
    assert_authorization_negative(good, expected_result="AUTHORIZATION_REQUIRED",
                                  expected_code="AUTHORIZATION_REQUIRED")
    with pytest.raises(AssertionError):     # authorization_verified True must fail
        bad = json.loads(json.dumps(good))
        bad["receipt"]["authorization_verified"] = True
        assert_authorization_negative(bad, expected_result="AUTHORIZATION_REQUIRED",
                                      expected_code="AUTHORIZATION_REQUIRED")
    with pytest.raises(AssertionError):     # a mutation would fail
        bad = json.loads(json.dumps(good))
        bad["mutator"]["invocations"] = 1
        assert_authorization_negative(bad, expected_result="AUTHORIZATION_REQUIRED",
                                      expected_code="AUTHORIZATION_REQUIRED")
    with pytest.raises(AssertionError):     # consumed engine contact would fail
        bad = json.loads(json.dumps(good))
        bad["extractor_calls"] = 1
        assert_authorization_negative(bad, expected_result="AUTHORIZATION_REQUIRED",
                                      expected_code="AUTHORIZATION_REQUIRED")
    with pytest.raises(AssertionError):     # a spawned fresh report would fail
        bad = json.loads(json.dumps(good))
        bad["receipt"]["output_report_digest"] = "0" * 64
        assert_authorization_negative(bad, expected_result="AUTHORIZATION_REQUIRED",
                                      expected_code="AUTHORIZATION_REQUIRED")


# --------------------------------------------------------------------------- environment / scope
def test_environment_and_no_persistence(live_results):
    env = live_results["environment"]
    assert env["blender_version"] == "4.4.3"
    assert env["build_hash"] == "802179c51ccc"
    assert env["build_date"] == "2025-04-29"
    assert env["filepath_at_start"] == "", "Blender must start with NO .blend loaded"
    assert env["frozen_asset_sha256"] == FROZEN_SHA256
    assert live_results["errors"] == []
    assert live_results["session"]["filepath_at_end"] == ""
    assert live_results["session"]["is_dirty"] is True
    assert live_results["session"]["saved_anything"] is False
    assert live_results["_blend_snapshot_unchanged"] is True
    assert live_results["_frozen_before"] == FROZEN_SHA256
    assert live_results["_frozen_after"] == FROZEN_SHA256


def test_no_production_module_changed_during_the_live_run(live_results):
    assert live_results["_production_hashes_after"] == live_results["_production_hashes_before"]


def test_target_selection_is_identity_based_with_a_decoy_that_sorts_first(live_results):
    contract = live_results["environment"]["target_contract"]
    assert contract == {"target_object_id": "pitch", "target_mesh_id": "pitch",
                        "decoy_object_id": "goal", "decoy_sorts_before_target": True}
    case = _case(live_results, "w2-positive-d2-operator-designation")
    assert case["target"]["resolved_by"] == "identity"
    assert case["raw_before"]["object_names_in_extraction_order"] == ["goal", "pitch"]
    assert _raw_object(case["raw_before"], "goal") is not None


def test_authority_model_matches_the_repository_contract(live_results):
    for case in live_results["cases"]:
        authority = case["authority"]
        assert_equal(authority["determinism"], "HEURISTIC", f"{case['case']} determinism")
        assert_equal(authority["correction_type"], W2, f"{case['case']} correction type")
        assert_equal(authority["risk"], "FIDELITY_GEOMETRY", f"{case['case']} risk")
        assert_equal(authority["reversibility"], "partially_reversible",
                     f"{case['case']} reversibility")
        assert_equal(authority["auto_propose"], True, f"{case['case']} auto_propose")
        assert_equal(authority["requires_human_review"], True,
                     f"{case['case']} requires_human_review")
        assert_equal(authority["proposal_count"], 1, f"{case['case']} exactly one W2 proposal")
        assert_equal(case["capability"], W2, f"{case['case']} capability")


def test_receipt_schema_is_pinned_and_audit_only(live_results):
    for case in live_results["cases"]:
        receipt = case["receipt"]
        assert_equal(receipt["field_count"], RECEIPT_FIELD_COUNT, f"{case['case']} receipt fields")
        assert_equal(receipt["persisted"], False, f"{case['case']} persisted")
        assert_equal(receipt["rollback_performed"], False, f"{case['case']} rollback_performed")
        assert_equal(receipt["topology_only_orientation_repair"], True,
                     f"{case['case']} topology_only_orientation_repair")
        assert_equal(receipt["normal_agreement_not_verified"], True,
                     f"{case['case']} normal_agreement_not_verified")
        if case["plan"]["plan_id_tampered"]:
            # the deliberately forged plan is the ONE case whose integrity must NOT hold
            assert receipt["plan_integrity_ok"] is False, (
                f"{case['case']}: a forged plan_id must fail the integrity recomputation")
        else:
            assert receipt["plan_integrity_ok"] is True, f"{case['case']} plan integrity"
        assert_no_invalid_index(case["post"]["histogram"] if case["post"] else {}, case["case"])


def test_every_case_matches_its_declared_expectation(live_results):
    assert len(live_results["cases"]) == 46
    for case in live_results["cases"]:
        expect = case["expect"]
        receipt = case["receipt"]
        assert_equal(receipt["result"], expect["result"], f"{case['case']} result")
        assert_equal(receipt["failure_code"], expect["failure_code"], f"{case['case']} failure_code")
        assert_equal(case["mutator"]["invocations"], expect["mutations"],
                     f"{case['case']} mutator invocations")
        assert_equal(receipt["authorization_verified"], expect["authorization_verified"],
                     f"{case['case']} authorization_verified")
        assert_equal(case["extractor_calls"], expect["extractor_calls"],
                     f"{case['case']} extractor calls")


def test_content_verified_pre_flight_binding(live_results):
    """Identity alone is insufficient: finding code, mesh id, exact measured edge and proposal count."""
    case = _case(live_results, "w2-positive-d2-operator-designation")
    binding = case["binding"]
    assert_equal(binding["proposal_count"], 1, "one W2 proposal")
    assert_equal(binding["expected_finding"], {"code": WINDING, "mesh_id": "pitch",
                                              "measured": {"edge": [0, 1], "faces": [0, 1]}},
                 "the bound finding")
    params = binding["parameters"][0]
    assert_equal(params["recorded_edges"], [binding["expected_finding"]["measured"]["edge"]],
                 "the plan's recorded edge equals the MEASURED edge")
    assert_equal(list(params["candidate_faces"]),
                 list(binding["expected_finding"]["measured"]["faces"]),
                 "the plan's candidate pair equals the MEASURED face pair")
    assert_equal(params["counterpart_faces"], [1], "the recorded counterpart")

    d1 = _case(live_results, "w2-positive-d1-evidence-designation")
    assert_equal(d1["binding"]["expected_finding"]["measured"],
                 {"edge": [0, 1], "faces": [0, 1]}, "D1 binds the first measured finding")
    assert_equal(d1["binding"]["plan_designation"], 0, "D1 designation comes from evidence")
    assert_equal(d1["binding"]["plan_candidate_faces"], None, "D1 carries no candidate pair")


# --------------------------------------------------------------------------- D2 / D1 positives
def test_d2_positive_authorization_and_single_bounded_reversal(live_results):
    case = _case(live_results, "w2-positive-d2-operator-designation")
    receipt = case["receipt"]
    assert_equal(case["authorization"]["kind"], "valid", "a real artifact was presented")
    assert_equal(case["authorization"]["designated_face_index"], 0, "D2 operator designation")
    assert_equal(case["authorization"]["policy_version"], "1", "authorization policy version")
    assert_equal(receipt["authorization_verified"], True, "authorization verified before mutation")
    assert_equal(receipt["authorization_policy_version"], "1", "receipt policy version")
    assert receipt["authorization_digest"] == case["authorization"]["artifact_digest"]
    assert_equal(receipt["precondition_results"], [{"ok": True, "target": ["pitch", "pitch"]}],
                 "WC-P preconditions passed on fresh evidence")
    assert_equal(case["mutator"]["invocations"], 1, "exactly one bounded mutation")
    assert_equal(case["mutator"]["engine_edits"], 1, "exactly one engine edit")
    assert_equal(case["mutator"]["calls"], [{"object_id": "pitch", "mesh_id": "pitch",
                                             "face_index": 0, "face_tuple": [0, 1, 2]}],
                 "the mutator received the exact resolved designation")


def test_d2_positive_exact_reversal_and_ordered_preservation(live_results):
    case = _case(live_results, "w2-positive-d2-operator-designation")
    assert_equal(case["pre"]["faces"], [[0, 1, 2], [0, 1, 3]], "pre faces")
    assert_equal(case["post"]["faces"], [[2, 1, 0], [0, 1, 3]], "post faces")
    assert_reversal(case["pre"]["faces"][0], case["post"]["faces"][0], "D2 designated face")
    assert_other_faces_unchanged(case["pre"]["faces"], case["post"]["faces"], 0, "D2 other faces")
    assert_equal(case["pre"]["vertex_count"], 4, "vertex count")
    raw_before = _raw_object(case["raw_before"], "pitch")
    raw_after = _raw_object(case["raw_after"], "pitch")
    assert_equal(raw_after["vertices"], raw_before["vertices"], "the vertex table is unchanged")
    assert_equal(raw_after["vertex_count"], raw_before["vertex_count"], "raw vertex count")
    assert_equal(raw_after["polygon_count"], raw_before["polygon_count"], "face count unchanged")
    assert_equal(raw_after["data_block"], "pitch", "the datablock is unchanged (observed behaviour)")
    # the designated directed edge is now OPPOSITE-traversed by the recorded pair (WC-Q5)
    target_face, counterpart = case["post"]["faces"][0], case["post"]["faces"][1]
    edge = case["receipt"]["recorded_edges"][0]
    def directed(face, edge):
        for i in range(len(face)):
            pair = (face[i], face[(i + 1) % len(face)])
            if sorted(pair) == sorted(edge):
                return pair
        return None
    assert_equal(directed(target_face, edge), (1, 0), "post target traversal of the recorded edge")
    assert_equal(directed(counterpart, edge), (0, 1), "post counterpart traversal")
    assert_equal([c["face_tuple"] for c in case["receipt"]["counterpart_faces"]], [[0, 1, 3]],
                 "the counterpart face tuple is unchanged")


def test_d2_positive_finding_cleared_and_receipt_authoritative_after_fresh_state(live_results):
    case = _case(live_results, "w2-positive-d2-operator-designation")
    receipt = case["receipt"]
    assert_equal(case["pre"]["histogram"],
                 {WINDING: {"count": 1, "measured": [{"edge": [0, 1], "faces": [0, 1]}]}},
                 "pre histogram")
    assert_equal(case["post"]["histogram"], {}, "post histogram: the winding finding is cleared")
    assert_finding_cleared(case["pre"]["histogram"], case["post"]["histogram"], WINDING, "WC-Q13")
    assert_equal(receipt["pre_winding_findings"], [{"edge": [0, 1], "faces": [0, 1]}],
                 "receipt pre findings")
    assert_equal(receipt["post_winding_findings"], [], "receipt post findings")
    assert_equal(receipt["target_face"], {"object_id": "pitch", "mesh_id": "pitch", "face_index": 0,
                                         "face_tuple_before": [0, 1, 2],
                                         "face_tuple_after": [2, 1, 0]}, "receipt target face")
    assert_equal(receipt["executed_correction_ids"], case["binding"]["correction_ids"],
                 "the executed correction is the authorized one")
    assert_equal(receipt["skipped_correction_ids"], [], "nothing was skipped")
    assert receipt["output_report_digest"] == case["post"]["digest"], (
        "the receipt's post digest is derived from the FRESH post-mutation verification")
    assert_equal(case["extractor_calls"], 2, "source + fresh post extraction")


def test_d1_positive_designation_comes_from_evidence(live_results):
    case = _case(live_results, "w2-positive-d1-evidence-designation")
    receipt = case["receipt"]
    assert_equal(case["binding"]["plan_designation"], 0, "the planner supplied the designation")
    assert_equal(case["authorization"]["designated_face_index"], None,
                 "a D1 artifact must NOT supply a designation")
    assert_equal(receipt["authorization_verified"], True, "D1 authorization verified")
    assert_equal(receipt["target_face"]["face_index"], 0, "the evidence designation was used")
    assert_equal(case["mutator"]["invocations"], 1, "exactly one bounded mutation")
    assert_equal(case["mutator"]["calls"][0]["face_index"], 0, "one reversal at the evidence index")
    assert_equal(case["pre"]["histogram"],
                 {WINDING: {"count": 2, "measured": [{"edge": [0, 1], "faces": [0, 1]},
                                                     {"edge": [0, 2], "faces": [0, 2]}]}},
                 "D1 pre histogram: TWO findings sharing the common face")
    assert_equal(case["post"]["histogram"], {}, "D1 post histogram: both findings cleared")
    assert_equal(case["post"]["faces"], [[2, 1, 0], [0, 1, 3], [2, 0, 4]], "D1 post faces")
    assert_reversal(case["pre"]["faces"][0], case["post"]["faces"][0], "D1 designated face")
    assert_other_faces_unchanged(case["pre"]["faces"], case["post"]["faces"], 0, "D1 other faces")
    assert_equal([c["index"] for c in receipt["counterpart_faces"]], [1, 2], "D1 counterparts")
    assert_equal(receipt["recorded_edges"], [[0, 1], [0, 2]], "D1 recorded edges")


def test_expected_face_tuple_assertion_path_is_exercised(live_results):
    case = _case(live_results, "w2-positive-d2-expected-face-tuple-assertion")
    assert_equal(case["authorization"]["expected_face_tuple"], [0, 1, 2],
                 "the artifact asserted the execution-time tuple")
    assert_equal(case["receipt"]["result"], "COMPLETED", "the deferred assertion agreed")
    assert_equal(case["receipt"]["authorization_verified"], True, "verified after the deferred check")
    assert_reversal(case["pre"]["faces"][0], case["post"]["faces"][0], "deferred-path reversal")


# --------------------------------------------------------------------------- authorization negatives
def test_authorization_negative_family_full_matrix(live_results):
    expected = {
        "w2-negative-authorization-absent-d2": ("AUTHORIZATION_REQUIRED", "AUTHORIZATION_REQUIRED"),
        "w2-negative-authorization-absent-d1": ("AUTHORIZATION_REQUIRED", "AUTHORIZATION_REQUIRED"),
        "w2-negative-artifact-malformed-json": ("AUTHORIZATION_INVALID", "MALFORMED_JSON"),
        "w2-negative-artifact-json-not-an-object": ("AUTHORIZATION_INVALID", "NOT_A_MAPPING"),
        "w2-negative-artifact-not-a-mapping": ("AUTHORIZATION_INVALID", "NOT_A_MAPPING"),
        "w2-negative-artifact-missing-required-field": ("AUTHORIZATION_INVALID", "MISSING_FIELD"),
        "w2-negative-artifact-duplicate-json-key": ("AUTHORIZATION_INVALID", "DUPLICATE_JSON_KEY"),
        "w2-negative-authorization-version-unsupported":
            ("AUTHORIZATION_INVALID", "UNSUPPORTED_AUTHORIZATION_VERSION"),
        "w2-negative-policy-version-unsupported":
            ("AUTHORIZATION_INVALID", "UNSUPPORTED_POLICY_VERSION"),
        "w2-negative-decision-not-approved": ("AUTHORIZATION_INVALID", "DECISION_NOT_APPROVED"),
        "w2-negative-correction-type-not-authorizable":
            ("AUTHORIZATION_INVALID", "CORRECTION_TYPE_NOT_AUTHORIZABLE"),
        "w2-negative-correction-type-mismatch":
            ("AUTHORIZATION_SCOPE_MISMATCH", "CORRECTION_TYPE_MISMATCH"),
        "w2-negative-correction-id-mismatch":
            ("AUTHORIZATION_SCOPE_MISMATCH", "CORRECTION_ID_MISMATCH"),
        "w2-negative-plan-id-mismatch": ("AUTHORIZATION_SCOPE_MISMATCH", "PLAN_ID_MISMATCH"),
        "w2-negative-source-digest-mismatch":
            ("AUTHORIZATION_SCOPE_MISMATCH", "SOURCE_DIGEST_MISMATCH"),
        "w2-negative-artifact-unknown-field": ("AUTHORIZATION_INVALID", "UNKNOWN_FIELD"),
        "w2-negative-artifact-digest-format-invalid":
            ("AUTHORIZATION_INVALID", "DIGEST_FORMAT_INVALID"),
        "w2-negative-d2-designation-required":
            ("AUTHORIZATION_REQUIRED", "DESIGNATION_REQUIRED"),
        "w2-negative-d2-designation-outside-candidate-pair":
            ("AUTHORIZATION_SCOPE_MISMATCH", "DESIGNATION_NOT_IN_CANDIDATE_PAIR"),
        "w2-negative-d1-designation-supplied":
            ("AUTHORIZATION_SCOPE_MISMATCH", "DESIGNATION_SUPPLIED_FOR_D1"),
    }
    assert set(expected) | {"w2-negative-d2-designation-is-counterpart"} == set(AUTHORIZATION_NEGATIVES)
    for label, (result, code) in expected.items():
        assert_authorization_negative(_case(live_results, label), expected_result=result,
                                      expected_code=code)


def test_d2_designation_naming_the_counterpart_is_refused_on_fresh_evidence(live_results):
    """The counterpart rule (WC-P8): the artifact verifies, then the FRESH evidence refuses it."""
    case = _case(live_results, "w2-negative-d2-designation-is-counterpart")
    receipt = case["receipt"]
    assert_equal(receipt["result"], "PRECONDITION_FAILED", "counterpart designation result")
    assert_equal(receipt["failure_code"], "PRECONDITION_FAILED", "counterpart failure code")
    assert_equal(receipt["authorization_verified"], False, "authorization_verified stays False")
    assert_equal(case["mutator"]["invocations"], 0, "ZERO mutator invocations")
    assert_equal(case["extractor_calls"], 1, "the source extraction was consumed, then refused")
    assert_equal(case["authorization"]["designated_face_index"], 1, "the recorded counterpart")
    reason = receipt["precondition_results"][0]["reason"]
    assert "WC-P8" in reason and "COUNTERPART_EQUALS_DESIGNATED_FACE" in reason, reason
    assert_equal(case["raw_after"], case["raw_before"], "no Blender mutation occurred")
    assert_equal(receipt["output_report_digest"], None, "no fresh report was produced")


# --------------------------------------------------------------------------- plan / source negatives
def test_stale_plan_and_malformed_parameters_never_touch_the_engine(live_results):
    stale = _case(live_results, "w2-negative-stale-plan-id")
    assert_equal(stale["receipt"]["result"], "PLAN_INVALID", "stale plan result")
    assert_equal(stale["receipt"]["failure_code"], "PLAN_ID_MISMATCH", "stale plan code")
    assert_equal(stale["plan"]["plan_id_tampered"], True, "the plan id was forged post-construction")
    assert_equal(stale["extractor_calls"], 0, "no engine contact at all")
    assert_equal(stale["mutator"]["invocations"], 0, "zero mutations")
    assert_equal(stale["receipt"]["authorization_verified"], False, "not authorized")
    assert_equal(stale["raw_after"], stale["raw_before"], "raw state unchanged")

    malformed = _case(live_results, "w2-negative-malformed-parameters-unexpected-key")
    assert_equal(malformed["receipt"]["result"], "PLAN_INVALID", "malformed params result")
    assert_equal(malformed["receipt"]["failure_code"], "UNEXPECTED_PARAMETER:unexpected_key",
                 "malformed params code")
    assert_equal(malformed["extractor_calls"], 0,
                 "the parameter allowlist precedes the authorization and source stages")
    assert_equal(malformed["mutator"]["invocations"], 0, "zero mutations")
    assert_equal(malformed["raw_after"], malformed["raw_before"], "raw state unchanged")


def test_precondition_negatives_consume_only_the_source_extraction(live_results):
    expected_reason_fragments = {
        "w2-negative-wrong-mesh": ("WC-P6", "0 object(s)"),
        "w2-negative-missing-target-object": ("WC-P6", "does not exist"),
        "w2-negative-designated-index-out-of-range": ("WC-P7", "out of range"),
        "w2-negative-designated-face-degenerate": ("WC-P14", "DEGENERATE"),
        "w2-negative-designated-face-duplicate": ("WC-P14", "DUPLICATE pair"),
        "w2-negative-recorded-edges-disagree-with-fresh": ("WC-P17", "RECORDED_SET_MISMATCH"),
    }
    for label, (predicate, fragment) in expected_reason_fragments.items():
        case = _case(live_results, label)
        receipt = case["receipt"]
        assert_equal(receipt["result"], "PRECONDITION_FAILED", f"{label} result")
        assert_equal(receipt["failure_code"], "PRECONDITION_FAILED", f"{label} code")
        assert_equal(receipt["authorization_verified"], False, f"{label} not verified")
        assert_equal(case["mutator"]["invocations"], 0, f"{label}: zero mutations")
        assert_equal(case["mutator"]["engine_edits"], 0, f"{label}: zero engine edits")
        assert_equal(case["extractor_calls"], 1, f"{label}: exactly the source extraction")
        assert_equal(case["raw_after"], case["raw_before"], f"{label}: no Blender mutation")
        reason = receipt["precondition_results"][0]["reason"]
        assert predicate in reason and fragment in reason, f"{label}: {reason}"
        assert_equal(receipt["output_report_digest"], None, f"{label}: no post-mutation report")


def test_designated_face_duplicate_plan_is_contract_legal_but_not_planner_emittable(live_results):
    case = _case(live_results, "w2-negative-designated-face-duplicate")
    assert_equal(case["plan"]["plan_mode"], "synthetic", "this negative uses the documented plan mode")
    assert_equal(case["plan_integrity_recomputes"], True,
                 "the plan is CONTRACT-LEGAL: its plan_id recomputes from its own contents")
    assert_equal(case["authorization"]["kind"], "valid", "the artifact is bound to that plan")
    assert_equal(case["receipt"]["plan_integrity_ok"], True, "the executor accepted the integrity")
    assert_equal(case["receipt"]["authorization_verified"], False, "but the fresh evidence refused")
    assert_equal(case["receipt"]["failure_code"], "PRECONDITION_FAILED", "refused at a precondition")
    probe = live_results["unreachable_negative_probes"]["wc_p14_duplicate"]
    assert_equal(probe["winding_proposal_count"], 0,
                 "the real planner provably emits no W2 plan for that report")
    assert_equal(probe["coverage"], "NOT_REACHABLE_THROUGH_THE_LIVE_BOUNDARY", "documented coverage")


def test_engine_mutation_after_planning_is_a_source_mismatch(live_results):
    case = _case(live_results, "w2-negative-engine-mutated-after-planning")
    receipt = case["receipt"]
    assert_equal(receipt["result"], "SOURCE_MISMATCH", "digest-first result")
    assert_equal(receipt["failure_code"], "SOURCE_DIGEST_MISMATCH", "digest-first code")
    assert receipt["source_report_digest_recomputed"] != case["plan"]["source_report_digest"], (
        "the fresh engine digest moved away from the plan's source digest")
    assert_equal(receipt["authorization_verified"], False, "authorization_verified stays False")
    assert_equal(case["authorization"]["kind"], "valid",
                 "the artifact DID verify against the plan - the refusal is source binding")
    assert_equal(case["mutator"]["invocations"], 0, "zero mutations")
    assert_equal(case["extractor_calls"], 1, "one extraction (the source binding)")


# --------------------------------------------------------------------------- postcondition negatives
def test_noop_after_accepted_authorization_proves_authorization_is_not_a_success_flag(live_results):
    case = _case(live_results, "w2-negative-noop-after-accepted-authorization")
    receipt = case["receipt"]
    assert_equal(case["authorization"]["kind"], "valid", "a valid artifact was accepted")
    assert_equal(receipt["authorization_verified"], True,
                 "authorization_verified is True (authorization + WC-P passed)")
    assert_equal(case["mutator"]["invocations"], 1, "the mutator WAS invoked")
    assert_equal(receipt["result"], "POSTCONDITION_FAILED", "the correction did NOT succeed")
    assert_equal(receipt["failure_code"], "WC-Q1", "the failed predicate is typed")
    assert_equal(receipt["executed_correction_ids"], [], "nothing is reported as executed")
    assert "not the exact plain reversal" in receipt["postcondition_results"][0]["reason"]
    assert_equal(case["post"]["faces"], case["pre"]["faces"], "the engine state is in fact unchanged")


def test_liar_mutator_and_wrong_face_and_rotation_are_refused(live_results):
    liar = _case(live_results, "w2-negative-liar-mutator")
    assert_equal(liar["receipt"]["result"], "POSTCONDITION_FAILED", "liar mutator result")
    assert_equal(liar["receipt"]["failure_code"], "WC-Q1", "liar mutator code")
    assert_equal(liar["mutator"]["liar"], True, "the liar claimed success")
    assert_equal(liar["receipt"]["authorization_verified"], True, "authorization was valid")
    assert_equal(liar["post"]["faces"], liar["pre"]["faces"], "the receipt is not authority")

    wrong = _case(live_results, "w2-negative-mutator-reverses-wrong-face")
    assert_equal(wrong["receipt"]["failure_code"], "WC-Q1", "wrong-face code")
    assert_equal(wrong["post"]["faces"][0], [0, 1, 2], "the designated face was not reversed")
    assert_equal(wrong["post"]["faces"][1], [3, 1, 0], "a different face WAS reversed")

    rotation = _case(live_results, "w2-negative-mutator-rotates-designated-face")
    assert_equal(rotation["receipt"]["failure_code"], "WC-Q1", "rotation code")
    assert_equal(rotation["post"]["faces"][0], [1, 2, 0], "a rotation is not the exact reversal")


def test_other_postcondition_negatives(live_results):
    two = _case(live_results, "w2-negative-mutator-reverses-two-faces")
    assert_equal(two["receipt"]["result"], "POSTCONDITION_FAILED", "two-face result")
    assert_equal(two["receipt"]["failure_code"], "WC-Q4", "two-face code")
    assert_equal(two["post"]["faces"], [[2, 1, 0], [3, 1, 0]], "the second face was altered")
    assert_reversal(two["pre"]["faces"][0], two["post"]["faces"][0], "the designated face did reverse")

    vertex = _case(live_results, "w2-negative-mutator-changes-vertex-table")
    assert_equal(vertex["receipt"]["failure_code"], "WC-Q3", "vertex-table code")
    assert _raw_object(vertex["raw_after"], "pitch")["vertices"] != \
        _raw_object(vertex["raw_before"], "pitch")["vertices"], "the vertex really moved"

    unrelated = _case(live_results, "w2-negative-mutator-touches-unrelated-object")
    assert_equal(unrelated["receipt"]["failure_code"], "WC-Q11", "unrelated-object code")
    assert_equal(_raw_object(unrelated["raw_after"], "goal")["vertices"][0], [99.0, 99.0, 99.0],
                 "the unrelated object really was touched")


# --------------------------------------------------------------------------- reachability / D3
def test_d3_planner_non_emission_with_a_live_positive_control(live_results):
    probe = live_results["d3_planner_non_emission"]
    assert_equal(probe["candidate_face_intersection"], [],
                 "D3: the candidate-face intersection is empty")
    assert_equal(len(probe["winding_findings"]), 2, "two disjoint winding findings")
    assert_equal(probe["winding_proposal_count"], 0, "the planner emits NO winding proposal")
    assert_equal(probe["d1_control_winding_proposal_count"], 1,
                 "POSITIVE CONTROL: the same live path DOES emit a proposal when the intersection is "
                 "a single face, so the non-emission is discriminating")
    assert_equal(probe["d1_control_designation"], 0, "the control's evidence designation")
    assert_equal(probe["artifact_constructed"], False,
                 "D3 is planner non-emission only: NO artifact may be fabricated")
    assert_equal(probe["execution_attempted"], False, "D3 is never executed")
    assert_equal(probe["plan_state"], "REVIEW_REQUIRED", "the findings remain review-only")


def test_unreachable_negative_probes_are_recorded_not_invented(live_results):
    probes = live_results["unreachable_negative_probes"]

    duplicate = probes["wc_p14_duplicate"]
    assert_equal(duplicate["coverage"], "NOT_REACHABLE_THROUGH_THE_LIVE_BOUNDARY",
                 "WC-P14 duplicate coverage")
    assert_equal(duplicate["winding_proposal_count"], 0, "no winding proposal for that mesh")
    assert_equal(duplicate["candidate_face_intersection"], [], "the intersection is empty (D3)")
    assert DV in json.dumps(duplicate["findings"]), "the duplicate pair really is present"

    new_duplicate = probes["wc_q7_new_duplicate"]
    assert_equal(new_duplicate["coverage"], "NOT_REACHABLE_THROUGH_THE_LIVE_BOUNDARY",
                 "WC-Q7 coverage")
    assert_equal(new_duplicate["non_manifold_edges"],
                 [{"edge": [0, 1], "face_incidence": 3}],
                 "the reversal-twin makes the winding edge non-manifold: no legal W2 pre-state")
    assert_equal(new_duplicate["winding_finding_count"], 0, "and therefore no winding finding")
    assert_equal(new_duplicate["winding_proposal_count"], 0, "and therefore no W2 plan")


# --------------------------------------------------------------------------- Wave 14 fidelity
def test_positive_material_evidence_is_non_vacuous_and_preserved(live_results):
    case = _case(live_results, "w2-positive-d2-operator-designation")
    assert_anti_vacuity(case["pre"]["materials"], "W2 D2 positive")
    assert_equal(case["pre"]["materials"]["payload_value"], ["turf", "line_markings"],
                 "canonical materials value (pre)")
    assert_equal(case["post"]["materials"]["payload_value"], ["turf", "line_markings"],
                 "canonical materials value (post)")
    assert_equal(case["pre"]["materials"]["representation_state"], [], "representation state")
    assert_raw_slots([["DATA", "turf"], ["DATA", "line_markings"]],
                     _raw_object(case["raw_before"], "pitch")["material_slots"], "pre raw slots")
    assert_raw_slots([["DATA", "turf"], ["DATA", "line_markings"]],
                     _raw_object(case["raw_after"], "pitch")["material_slots"], "post raw slots")
    assert_raw_slots([["DATA", "banner"]], _raw_object(case["raw_after"], "goal")["material_slots"],
                     "unrelated object raw slots")
    assert_inventory_unchanged(case["raw_before"]["mesh_datablocks"],
                              case["raw_after"]["mesh_datablocks"], "inventory")
    assert_equal(case["post"]["decoy_histogram"], case["pre"]["decoy_histogram"],
                 "the unrelated object's findings are unchanged")


def test_unassigned_and_object_linked_slots_are_raw_only(live_results):
    unassigned = _case(live_results, "w2-positive-d2-unassigned-slot-raw-only")
    assert_equal(unassigned["pre"]["materials"]["key_present"], False,
                 "the producer omits the key when a slot is unassigned (frozen behaviour)")
    assert_equal(unassigned["pre"]["materials"]["representation_state"], ["materials:omitted"],
                 "representation state records the omission")
    assert_raw_slots([["DATA", "turf"], ["DATA", None], ["DATA", "goal_net"]],
                     _raw_object(unassigned["raw_before"], "pitch")["material_slots"], "unassigned pre")
    assert_raw_slots([["DATA", "turf"], ["DATA", None], ["DATA", "goal_net"]],
                     _raw_object(unassigned["raw_after"], "pitch")["material_slots"], "unassigned post")

    linked = _case(live_results, "w2-positive-d2-object-linked-slot-raw-only")
    assert_equal(linked["pre"]["materials"]["key_present"], False,
                 "an OBJECT-linked slot also omits the canonical key")
    assert_raw_slots([["DATA", "turf"], ["OBJECT", "line_markings"]],
                     _raw_object(linked["raw_before"], "pitch")["material_slots"], "linked pre")
    assert_raw_slots([["DATA", "turf"], ["OBJECT", "line_markings"]],
                     _raw_object(linked["raw_after"], "pitch")["material_slots"], "linked post")


def test_slot_destruction_and_datablock_replacement_are_caught_by_gate_evidence_only(live_results):
    """The W2 canonical postcondition has NO material/datablock clause: only gate evidence sees it."""
    destroyed = _case(live_results, "w2-evidence-material-slot-destruction")
    assert_equal(destroyed["receipt"]["result"], "COMPLETED", "the executor cannot see slot loss")
    assert_anti_vacuity(destroyed["pre"]["materials"], "slot-destruction pre-state")
    assert_equal(destroyed["post"]["materials"]["canonical"], [], "canonical tuple emptied")
    assert_equal(destroyed["post"]["materials"]["key_present"], False, "and the key is omitted")
    assert_raw_slots([["DATA", None]], _raw_object(destroyed["raw_after"], "pitch")["material_slots"],
                     "destroyed raw slot table")
    assert_inventory_unchanged(destroyed["raw_before"]["mesh_datablocks"],
                              destroyed["raw_after"]["mesh_datablocks"], "no orphan appeared")

    replaced = _case(live_results, "w2-evidence-datablock-replacement")
    assert_equal(replaced["receipt"]["result"], "COMPLETED", "Pattern A is canonical-legal")
    assert_equal(replaced["post"]["materials"]["payload_value"], [], "canonical tuple emptied")
    assert_raw_slots([], _raw_object(replaced["raw_after"], "pitch")["material_slots"],
                     "Pattern A destroyed the slot table")
    assert_equal(_raw_object(replaced["raw_after"], "pitch")["data_block"], "pitch.001",
                 "the datablock was replaced")
    assert_equal(replaced["raw_after"]["mesh_datablocks"], ["goal", "pitch", "pitch.001"],
                 "raw inventory gained the replacement datablock")


def test_orphan_inventory_gain_and_the_two_engine_edit_boundary(live_results):
    orphan = _case(live_results, "w2-evidence-orphan-inventory-gain")
    assert_equal(orphan["receipt"]["result"], "COMPLETED", "the canonical layer sees nothing")
    assert_equal(orphan["raw_after"]["mesh_datablocks"], ["goal", "pitch", "w2_orphan_probe"],
                 "raw datablock inventory gained an orphan")
    assert_raw_slots([["DATA", "turf"], ["DATA", "line_markings"]],
                     _raw_object(orphan["raw_after"], "pitch")["material_slots"],
                     "slots survived while the orphan appeared")

    edits = _case(live_results, "w2-evidence-two-engine-edits-net-correct")
    assert_equal(edits["receipt"]["result"], "COMPLETED", "net-correct edit sequence completes")
    assert_equal(edits["mutator"]["invocations"], 1, "ONE invocation is counted")
    assert_equal(edits["mutator"]["engine_edits"], 3, "THREE internal engine rebuilds happened")
    assert_equal(edits["post"]["faces"], edits["pre"]["faces"][:1] and
                 [[2, 1, 0], [0, 1, 3]], "the final canonical state is the authorized one")
    assert_equal(edits["receipt"]["authorization_verified"], True, "authorization was valid")


def test_material_index_non_claim_is_not_asserted_anywhere(live_results):
    for source_path in (SCRIPT, os.path.abspath(__file__)):
        assert "polygon.material_index" in open(source_path, encoding="utf-8").read(), (
            f"the non-claim must be documented in {source_path}")
    for case in live_results["cases"]:
        assert "material_index" not in json.dumps(case["raw_before"])
        assert "material_index" not in json.dumps(case["raw_after"])
        assert "material_index" not in json.dumps(case["pre"]["materials"])
        assert "material_index" not in json.dumps(case["post"]["materials"])


# --------------------------------------------------------------------------- save / scope
def test_save_attempt_is_refused_and_creates_nothing(live_results):
    probe = live_results["save_attempt"]
    assert_equal(probe["filepath_before"], "", "no .blend was loaded, so there is no save target")
    assert_equal(probe["refused"], True, "the engine must refuse to save an unsaved file")
    assert_equal(probe["error_type"], "RuntimeError", "refusal type")
    assert "filepath" in probe["error_message"], probe["error_message"]
    assert_equal(probe["files_created_in_sandbox"], [], "the sandboxed attempt created no file")
    assert_equal(probe["filepath_after"], "", "no file is bound after the attempt")
    assert_equal(probe["sandbox_removed"], True, "the sandbox directory was removed")
    assert_equal(live_results["session"]["saved_anything"], False, "nothing was saved")
    assert live_results["_blend_snapshot_unchanged"] is True


def test_w1_w1b_remains_untouched_and_this_is_a_separate_gate_family(live_results):
    """W2 is its own gate family: no face-removal capability, case or harness is involved."""
    assert live_results["environment"]["w1_w1b_untouched"] is True
    for case in live_results["cases"]:
        assert case["capability"] == W2, f"{case['case']} must be a W2 case"
        assert "REMOVE_DUPLICATE_FACE" not in json.dumps(case["receipt"]["executed_correction_ids"])
        assert "REMOVE_DEGENERATE_FACE" not in json.dumps(case["receipt"]["executed_correction_ids"])
    source = open(SCRIPT, encoding="utf-8").read()
    for forbidden in ("_execute_face_removal", "execute_remove_duplicate_face",
                      "execute_remove_degenerate_face", "w1_w1b_face_removal_live_script"):
        assert forbidden not in source, f"the W2 driver must not reuse {forbidden!r}"


def test_gate_documentation_states_the_binding_constraints():
    gate_source = open(os.path.abspath(__file__), encoding="utf-8").read()
    for required in ("polygon.material_index", "TEST-ONLY", "one mutator invocation",
                     "authorization_verified == True DOES NOT MEAN", "WC-P14", "WC-Q7",
                     "NOT_REACHABLE_THROUGH_THE_LIVE_BOUNDARY", "D3"):
        assert required in gate_source, f"gate documentation must state: {required}"
