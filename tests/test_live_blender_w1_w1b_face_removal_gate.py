"""LIVE Blender gate for W1 ``REMOVE_DUPLICATE_FACE`` and W1b ``REMOVE_DEGENERATE_FACE`` (Wave 15).

Operator-gated; NOT run in CI. Runs the real Blender 4.4.3 process against the disposable in-memory
fixtures built by ``tests/w1_w1b_face_removal_live_script.py`` and asserts the complete live path::

    live Blender scene -> extraction -> SceneModel/SceneReport -> REAL planner
    -> execute_remove_duplicate_face / execute_remove_degenerate_face (NO authorization artifact)
    -> REAL Blender mutation (Pattern B, same datablock) -> fresh extraction -> postconditions
    -> receipt + raw boundary evidence

It never opens or writes a ``.blend``: Blender is started WITHOUT a file argument, every fixture is
built in memory, the frozen validation asset is hash-checked before/after and must stay
byte-identical, and the repository's production modules are hash-checked before/after the run.

Explicit authorized run only::

    ATLAS_RUN_LIVE_BLENDER=1 .venv/Scripts/python.exe -m pytest \\
        tests/test_live_blender_w1_w1b_face_removal_gate.py -s

SCOPE — W1 + W1b ONLY. ``REPAIR_FACE_WINDING`` (W2) is deliberately NOT implemented here: it is a
separate milestone with its own authorization model, its own gate and its own PR. This gate asserts
that no W2 correction, case, driver path or WC-P*/WC-Q* vocabulary is present.

RELATION BETWEEN THE TWO CAPABILITIES (red-team m-1): the two capabilities SHARE the live harness
(one real engine, one real planner, one real executor path, no authorization artifact, exactly one
mutation, fresh extraction, canonical postconditions from the existing executor), but their evidence
is parameterized separately and never substituted. This gate asserts NOTHING about the W1b cases on
the basis of the W1 cases and vice versa: the W1 assertions never justify a W1b claim, and no W1b
assertion depends on a W1 fixture. Where a case belongs to one capability, the other capability is
explicitly out of scope for that assertion.

REQUIRED NON-CLAIM (design §G) — repeated in gate documentation exactly as §G/F.1 mandate::

    Pattern B rebuild resets polygon.material_index. mesh.clear_geometry() followed by
    mesh.from_pydata(...) reconstructs every polygon with material_index == 0; per-face material
    assignment does NOT survive a geometry rebuild. Polygon material assignment is OUTSIDE the frozen
    Atlas representation contract. This gate makes NO claim that per-face material assignment
    survives, and it must never assert material_index preservation.

RAW-EVIDENCE CONTAINMENT (design §F.1, red-team F-4): every raw Blender assertion in this module
(raw slot tables, datablock identity/inventory, orphan detection, unrelated-object material state) is
TEST-ONLY boundary evidence. It lives only in test/gate code, is not imported by production code, is
not promoted into a shared production assertion/validator library, and creates no hidden canonical
Atlas contract. Raw evidence records what a specific engine run did; it does not extend the canonical
model. The canonical executors exercised here carry no material or datablock clause at all, so the
material/datablock assertions in this module are gate-side obligations only.

KNOWN, DOCUMENTED LIMITATIONS carried into this gate (not silently claimed away):
  * repeated-index polygons — Blender persists them, extraction emits them, and the canonical parser
    refuses them (``scene_model.py`` ``_canon_face``); they are recorded as a parser limitation and
    are NEVER a live-positive case;
  * the canonical postcondition is a face MULTISET delta, so a hostile mutator that removes two
    identical faces and adds one copy back is state-indistinguishable from the authorized single
    removal (measured live in this gate as a documented limitation);
  * ``polygon.material_index`` — non-claim (above);
  * W1's unrelated-material limitation — documented limitation, not a new canonical guarantee.
"""

import hashlib
import json
import os
import subprocess

import pytest

FROZEN_ASSET = os.path.join("tests", "assets", "blender", "atlas_transform_validation.blend")
FROZEN_SHA256 = "cf618bdc1123734bf49bf6f22677ded3f2e6c3fa2803b97f7a6cf7c7c66f11aa"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "tests", "w1_w1b_face_removal_live_script.py")

W1 = "REMOVE_DUPLICATE_FACE"
W1B = "REMOVE_DEGENERATE_FACE"
DV = "MESH_DUPLICATE_FACE"
DEG = "MESH_DEGENERATE_FACE"
WINDING = "MESH_WINDING_INCONSISTENT"
INVALID_INDEX = "MESH_INVALID_INDEX"

#: the frozen receipt skeleton for the shared face-removal pipeline (red-team m-2: pinned so
#: receipt-schema growth fails loudly instead of passing silently)
RECEIPT_FIELD_COUNT = 17

#: production modules that MUST NOT change (byte-identical before/after the live run); a runtime
#: rewrite by the driver would be a scope failure. The repo-level "no production semantic diff"
#: claim is verified against the base commit outside the gate.
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
    start = stdout.find("ATLAS_W1_W1B_LIVE_START")
    end = stdout.find("ATLAS_W1_W1B_LIVE_END")
    assert proc.returncode == 0, f"blender rc={proc.returncode}: {proc.stderr[-3000:]}"
    assert start != -1 and end != -1, f"live markers missing\n{stdout[-4000:]}"
    results = json.loads(stdout[start + len("ATLAS_W1_W1B_LIVE_START"):end].strip())

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


def _outcome(case):
    receipt = case["receipt"]
    return receipt["result"], receipt["failure_code"]


# --------------------------------------------------------------------------- assertion helpers
# These helpers carry the exhaustive comparison logic so that the SELF-TESTS below can prove every
# assertion is live (a deliberately wrong value must raise). No production code imports them.
def assert_equal(actual, expected, label):
    assert actual == expected, f"{label}: expected {expected!r}, got {actual!r}"


def assert_histogram(actual, expected, label):
    """Exact per-mesh finding-class histogram: same classes, same counts, same measured payloads."""
    normalised = {code: {"count": entry["count"], "measured": entry["measured"]}
                  for code, entry in actual.items()}
    assert normalised == expected, f"{label}: histogram mismatch\n actual={normalised}\nexpected={expected}"


def assert_multiset_delta(pre_faces, post_faces, removed_face, label):
    """The post face table must be EXACTLY the pre table minus one occurrence of `removed_face`."""
    from collections import Counter
    pre, post = Counter(tuple(f) for f in pre_faces), Counter(tuple(f) for f in post_faces)
    assert post == pre - Counter([tuple(removed_face)]), (
        f"{label}: face multiset delta is not exactly one recorded face\n"
        f" pre={sorted(pre.elements())}\npost={sorted(post.elements())}\nremoved={removed_face}")


def assert_survivor_payload(pre_measure, post_measure, expected_payload, label):
    """An unrelated finding must SURVIVE bit-identically; its disappearance must fail loudly."""
    assert expected_payload in pre_measure, f"{label}: expected survivor payload absent pre-mutation"
    assert post_measure == [expected_payload], (
        f"{label}: unrelated finding payload changed or disappeared\n"
        f"expected exactly [{expected_payload}]\n got {post_measure}")


def assert_identity_map(mapping, expected_map, label):
    """The renumbering map must equal the fixture policy (identity for the final-face fixture)."""
    assert mapping == expected_map, f"{label}: renumbering map {mapping} != policy {expected_map}"


def assert_material_key(expected_present, expected_value, view, label):
    """Canonical material evidence: key presence and value, checked explicitly (never vacuously)."""
    assert view["key_present"] is expected_present, (
        f"{label}: payload materials key presence {view['key_present']} != {expected_present}")
    assert view["payload_value"] == expected_value, (
        f"{label}: payload materials value {view['payload_value']!r} != {expected_value!r}")


def assert_anti_vacuity(view, label):
    """A material-bearing positive must REALLY carry material evidence in its pre-state."""
    assert view["key_present"] is True and view["payload_value"], (
        f"{label}: ANTI-VACUITY FAILURE - this case was supposed to be material-bearing but its "
        f"canonical materials evidence is {view!r}")


def assert_raw_slots(expected_table, actual_table, label):
    """RAW Blender slot table (link + material name), TEST-ONLY evidence (§F.1)."""
    assert actual_table == expected_table, (
        f"{label}: raw material slot table changed\n expected={expected_table}\n actual={actual_table}")


def assert_inventory(before, after, label):
    """RAW mesh-datablock inventory; growth means a new/orphaned datablock appeared."""
    assert after == before, f"{label}: datablock inventory changed {before} -> {after}"


# --------------------------------------------------------------------------- self-tests (non-vacuity)
# Every comparison helper above is exercised with a deliberately WRONG value and must raise. This is
# what makes the corresponding negative coverage real rather than assumed.
def test_selftest_histogram_assertion_is_live():
    observed = {DV: {"count": 1, "measured": [{"face_a": 2, "face_b": 3}]}}
    assert_histogram(observed, {DV: {"count": 1, "measured": [{"face_a": 2, "face_b": 3}]}}, "ok")
    with pytest.raises(AssertionError):   # histogram mismatch
        assert_histogram(observed, {DV: {"count": 2, "measured": [{"face_a": 2, "face_b": 3}]}}, "x")
    with pytest.raises(AssertionError):   # an extra finding class is a mismatch
        assert_histogram({**observed, WINDING: {"count": 1, "measured": []}},
                         {DV: {"count": 1, "measured": [{"face_a": 2, "face_b": 3}]}}, "x")
    with pytest.raises(AssertionError):   # a changed measured payload is a mismatch
        assert_histogram(observed, {DV: {"count": 1, "measured": [{"face_a": 2, "face_b": 2}]}}, "x")


def test_selftest_multiset_delta_assertion_is_live():
    pre = [(0, 1, 2), (0, 1, 3), (4, 5, 6), (4, 5, 6)]
    assert_multiset_delta(pre, [(0, 1, 2), (0, 1, 3), (4, 5, 6)], (4, 5, 6), "ok")
    with pytest.raises(AssertionError):   # nothing removed
        assert_multiset_delta(pre, pre, (4, 5, 6), "x")
    with pytest.raises(AssertionError):   # both duplicate members removed
        assert_multiset_delta(pre, [(0, 1, 2), (0, 1, 3)], (4, 5, 6), "x")
    with pytest.raises(AssertionError):   # a DIFFERENT single face was removed than recorded
        assert_multiset_delta(pre, [(0, 1, 2), (4, 5, 6), (4, 5, 6)], (0, 1, 2), "x")


def test_selftest_survivor_payload_assertion_is_live():
    payload = {"edge": [0, 1], "faces": [0, 1]}
    assert_survivor_payload([payload], [payload], payload, "ok")
    with pytest.raises(AssertionError):   # survivor disappeared
        assert_survivor_payload([payload], [], payload, "x")
    with pytest.raises(AssertionError):   # survivor payload altered
        assert_survivor_payload([payload], [{"edge": [0, 1], "faces": [1, 0]}], payload, "x")
    with pytest.raises(AssertionError):   # extra unrelated finding present post-mutation
        assert_survivor_payload([payload], [payload, payload], payload, "x")


def test_selftest_renumbering_assertion_is_live():
    assert_identity_map([[0, 0], [1, 1], [2, 2]], [[0, 0], [1, 1], [2, 2]], "ok")
    with pytest.raises(AssertionError):   # a follower face was renumbered
        assert_identity_map([[0, 0], [1, 1], [2, 2], [4, 3]], [[0, 0], [1, 1], [2, 2]], "x")
    with pytest.raises(AssertionError):   # nothing removed at all
        assert_identity_map([[0, 0], [1, 1], [2, 2], [3, 3]], [[0, 0], [1, 1], [2, 2]], "x")


def test_selftest_material_and_raw_assertions_are_live():
    view = {"key_present": True, "payload_value": ["turf", "line_markings"]}
    assert_material_key(True, ["turf", "line_markings"], view, "ok")
    assert_anti_vacuity(view, "ok")
    with pytest.raises(AssertionError):   # emptied canonical tuple = vacuous material evidence
        assert_anti_vacuity({"key_present": False, "payload_value": None}, "x")
    with pytest.raises(AssertionError):   # key presence drift
        assert_material_key(True, ["turf"], view, "x")
    assert_raw_slots([["DATA", "turf"]], [["DATA", "turf"]], "ok")
    with pytest.raises(AssertionError):   # destroyed slot table
        assert_raw_slots([["DATA", "turf"]], [], "x")
    with pytest.raises(AssertionError):   # OBJECT-linked slot turned into DATA
        assert_raw_slots([["DATA", "turf"], ["OBJECT", "m"]], [["DATA", "turf"], ["DATA", "m"]], "x")
    assert_inventory(["goal", "pitch"], ["goal", "pitch"], "ok")
    with pytest.raises(AssertionError):   # orphan/inventory gain
        assert_inventory(["goal", "pitch"], ["goal", "pitch", "pitch.001"], "x")


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
    assert live_results["session"]["is_dirty"] is True, "the in-memory scene WAS mutated"
    assert live_results["session"]["saved_anything"] is False
    assert live_results["_blend_snapshot_unchanged"] is True
    assert live_results["_frozen_before"] == FROZEN_SHA256
    assert live_results["_frozen_after"] == FROZEN_SHA256


def test_no_production_module_changed_during_the_live_run(live_results):
    before, after = live_results["_production_hashes_before"], live_results["_production_hashes_after"]
    assert set(before) == set(PRODUCTION_FILES)
    assert after == before, "a production module was rewritten by the live run"


def test_target_selection_is_identity_based_with_a_decoy_that_sorts_first(live_results):
    contract = live_results["environment"]["target_contract"]
    assert contract == {"target_object_id": "pitch", "target_mesh_id": "pitch",
                        "decoy_object_id": "goal", "decoy_sorts_before_target": True}
    # the decoy really does precede the target in extraction order, so positional selection would
    # silently retarget the fixture: the observed order proves the harness is not positional
    positive = _case(live_results, "w1-positive-duplicate-final-index")
    assert positive["target"]["resolved_by"] == "identity"
    assert _raw_object(positive["raw_before"], "goal") is not None
    assert positive["raw_before"]["object_names_in_extraction_order"] == ["goal", "pitch"]


def test_w2_is_not_implemented_here(live_results):
    """W2 is a separate milestone: this gate neither executes nor asserts anything for it.

    The frozen planner MAY still PROPOSE winding corrections for a fixture with winding findings
    (existing behaviour, owned by the W2 milestone). The requirement proven here is that such
    proposals are SKIPPED by this gate's executions and that no W2 case, capability, mutator or
    WC-P*/WC-Q* vocabulary exists in the driver or the gate.
    """
    assert live_results["environment"]["w2_not_implemented"] is True
    for case in live_results["cases"]:
        assert case["capability"] in (W1, W1B), f"unexpected capability {case['capability']}"
        for correction_id in case["receipt"]["executed_correction_ids"]:
            assert "WINDING" not in correction_id, (
                f"{case['case']}: this gate must never execute a winding correction")
            assert correction_id.startswith(DV) or correction_id.startswith(DEG), (
                f"{case['case']}: unexpected executed correction {correction_id!r}")
        for correction_id in case["receipt"]["skipped_correction_ids"]:
            assert correction_id not in case["receipt"]["executed_correction_ids"]
    # the forbidden tokens are ASSEMBLED here so that this assertion cannot match itself, and the
    # scan covers CODE ONLY (the module docstrings must be free to state the scope boundary)
    w2_entry_point = "execute_repair" + "_face_winding"
    w2_vocabulary = ("WC-" + "P", "WC-" + "Q")
    for path in (SCRIPT, os.path.abspath(__file__)):
        code = open(path, encoding="utf-8").read()
        parts = code.split('"""')          # drop the leading module docstring
        code = parts[2] if len(parts) >= 3 else code
        assert w2_entry_point not in code, f"the W2 executor entry point must not be used in {path}"
        for token in w2_vocabulary:
            assert token not in code, f"W2 vocabulary {token!r} must not appear in {path}"
    skipped_w2 = [case["case"] for case in live_results["cases"]
                  if any("WINDING" in cid for cid in case["receipt"]["skipped_correction_ids"])]
    assert skipped_w2, ("expected at least one case whose plan contains a planner-proposed winding "
                        "correction that this gate skips (evidence that W2 exists and is untouched)")


def test_every_case_matches_its_declared_expectation(live_results):
    assert len(live_results["cases"]) == 37
    for case in live_results["cases"]:
        expect = case["expect"]
        result, failure_code = _outcome(case)
        assert_equal(result, expect["result"], f"{case['case']} result")
        assert_equal(failure_code, expect["failure_code"], f"{case['case']} failure_code")
        assert_equal(case["mutator"]["invocations"], expect["mutations"],
                     f"{case['case']} mutator invocations")


def test_receipt_schema_is_pinned_and_has_no_authorization_field(live_results):
    for case in live_results["cases"]:
        receipt = case["receipt"]
        assert_equal(receipt["field_count"], RECEIPT_FIELD_COUNT, f"{case['case']} receipt field_count")
        assert receipt["has_authorization_verified_field"] is False, (
            f"{case['case']}: W1/W1b carry NO authorization artifact, so no authorization field "
            "may appear in the receipt")
        assert receipt["persisted"] is False
        assert receipt["rollback_performed"] is False
        assert receipt["plan_integrity_ok"] is True, f"{case['case']} plan integrity"


def test_plan_binding_is_content_verified(live_results):
    """Identity equality alone is insufficient: the plan must bind to the MEASURED defect."""
    binding = _case(live_results, "w1-positive-duplicate-final-index")["binding"]
    assert binding["proposal_count"] == 1, "exactly one capability proposal is required"
    assert binding["parameters"] == [{"mesh_id": "pitch", "face_ids": [2, 3],
                                      "duplicate_relationship": "exact_duplicate"}]
    assert binding["expected_finding"] == {"code": DV, "mesh_id": "pitch",
                                           "measured": {"face_a": 2, "face_b": 3,
                                                        "vertices": [4, 5, 6]}}
    assert binding["parameters"][0]["face_ids"] == [
        binding["expected_finding"]["measured"]["face_a"],
        binding["expected_finding"]["measured"]["face_b"]], "plan bound to a different pair"

    binding_b = _case(live_results, "w1b-positive-zero-area-collinear")["binding"]
    assert binding_b["proposal_count"] == 1
    assert binding_b["parameters"] == [{"mesh_id": "pitch", "face_id": 0,
                                        "reason": "degenerate_face"}]
    assert binding_b["expected_finding"] == {"code": DEG, "mesh_id": "pitch",
                                             "measured": {"face": 0, "signed_area": 0.0}}
    assert binding_b["parameters"][0]["face_id"] == binding_b["expected_finding"]["measured"]["face"]


def test_no_case_reports_a_new_invalid_index(live_results):
    for case in live_results["cases"]:
        for phase in ("pre", "post"):
            block = case.get(phase)
            if block is None:
                continue
            for code in block["histogram"]:
                assert code != INVALID_INDEX, f"{case['case']}: {INVALID_INDEX} in {phase}"
            for code in block["decoy_histogram"]:
                assert code != INVALID_INDEX, f"{case['case']}: {INVALID_INDEX} in decoy {phase}"


# --------------------------------------------------------------------------- W1 positive (F-1)
def test_w1_positive_exact_pre_and_post_histograms(live_results):
    case = _case(live_results, "w1-positive-duplicate-final-index")
    assert_equal(case["pre"]["histogram"], {
        DV: {"count": 1, "measured": [{"face_a": 2, "face_b": 3, "vertices": [4, 5, 6]}]},
        WINDING: {"count": 4, "measured": [
            {"edge": [0, 1], "faces": [0, 1]},
            {"edge": [4, 5], "faces": [2, 3]},
            {"edge": [5, 6], "faces": [2, 3]},
            {"edge": [4, 6], "faces": [2, 3]}]}}, "W1 pre histogram")
    assert_equal(case["post"]["histogram"], {
        WINDING: {"count": 1, "measured": [{"edge": [0, 1], "faces": [0, 1]}]}}, "W1 post histogram")


def test_w1_positive_clears_exactly_the_duplicate_induced_winding_findings(live_results):
    """F-1: the three co-emitted winding findings disappear, and ONLY because the duplicate went."""
    case = _case(live_results, "w1-positive-duplicate-final-index")
    pre_winding = case["pre"]["histogram"][WINDING]["measured"]
    post_winding = case["post"]["histogram"][WINDING]["measured"]
    induced = [entry for entry in pre_winding if entry["faces"] == [2, 3]]
    assert len(induced) == 3, f"expected the three duplicate-induced winding findings, got {induced}"
    for entry in induced:
        assert entry not in post_winding, f"duplicate-induced winding finding survived: {entry}"
    assert case["post"]["histogram"].get(DV) is None, "the duplicate finding itself must clear"


def test_w1_clearing_is_a_consequence_and_not_a_winding_repair(live_results):
    """No winding correction ran: the plan/execution is duplicate removal only."""
    case = _case(live_results, "w1-positive-duplicate-final-index")
    assert case["plan"]["all_correction_types"] == [W1]
    assert_equal(case["receipt"]["executed_correction_ids"], case["binding"]["correction_ids"],
                 "the executed correction is the bound duplicate-removal correction")
    assert case["receipt"]["executed_correction_ids"][0].startswith(DV)
    assert case["mutator"]["invocations"] == 1, "no second mutation may be inferred"


def test_w1_positive_unrelated_winding_survivor_is_bit_identical(live_results):
    case = _case(live_results, "w1-positive-duplicate-final-index")
    payload = {"edge": [0, 1], "faces": [0, 1]}
    assert_survivor_payload(case["pre"]["histogram"][WINDING]["measured"],
                            case["post"]["histogram"][WINDING]["measured"], payload,
                            "W1 unrelated winding survivor")


def test_w1_positive_exact_face_multiset_delta_and_raw_face_table(live_results):
    case = _case(live_results, "w1-positive-duplicate-final-index")
    pre_faces = [[0, 1, 2], [0, 1, 3], [4, 5, 6], [4, 5, 6]]
    post_faces = [[0, 1, 2], [0, 1, 3], [4, 5, 6]]
    assert_equal(case["pre"]["faces"], pre_faces, "W1 pre canonical faces")
    assert_equal(case["post"]["faces"], post_faces, "W1 post canonical faces")
    assert_multiset_delta(pre_faces, post_faces, [4, 5, 6], "W1 multiset delta")
    # RAW post face table must equal the expected EXACT subsequence of the raw pre table
    raw_before = _raw_object(case["raw_before"], "pitch")
    raw_after = _raw_object(case["raw_after"], "pitch")
    assert_equal(raw_before["faces"], pre_faces, "W1 raw pre face table")
    assert_equal(raw_after["faces"], post_faces, "W1 raw post face table")
    assert_equal(raw_after["faces"], raw_before["faces"][:-1], "W1 raw post must be pre without the "
                                                               "final face")
    assert_equal(raw_after["polygon_count"], 3, "W1 raw polygon count")
    assert_equal(raw_after["loops"], 9, "W1 raw loop count")
    assert_equal(raw_after["edge_count"], 8, "W1 raw edge count")


def test_w1_positive_vertex_table_unrelated_state_and_identity_unchanged(live_results):
    case = _case(live_results, "w1-positive-duplicate-final-index")
    assert_equal(case["pre"]["vertex_count"], case["post"]["vertex_count"],
                 "W1 vertex count must not change")
    raw_before = _raw_object(case["raw_before"], "pitch")
    raw_after = _raw_object(case["raw_after"], "pitch")
    assert_equal(raw_after["vertices"], raw_before["vertices"], "W1 raw vertex table")
    assert_equal(raw_after["data_block"], raw_before["data_block"], "target mesh identity")
    assert_equal(raw_after["collections"], raw_before["collections"], "target collections")
    # the unrelated object (decoy) must be unchanged at BOTH layers
    assert_equal(case["post"]["decoy_histogram"], case["pre"]["decoy_histogram"],
                 "unrelated object findings")
    assert_equal(_raw_object(case["raw_after"], "goal"), _raw_object(case["raw_before"], "goal"),
                 "unrelated object raw state")
    assert_equal(case["raw_after"]["material_datablocks"], case["raw_before"]["material_datablocks"],
                 "material datablock inventory")


def test_w1_positive_identity_renumbering_map_and_no_orphan(live_results):
    case = _case(live_results, "w1-positive-duplicate-final-index")
    assert case["identity_renumbering"] is True
    assert_identity_map(case["renumbering_map"], [[0, 0], [1, 1], [2, 2]], "W1 fixture policy")
    assert_inventory(["goal", "pitch"], case["raw_after"]["mesh_datablocks"], "W1 mesh datablocks")
    assert_equal(case["raw_after"]["objects"][0]["name"], "goal", "raw object order")


def test_w1_positive_single_mutation_and_receipt(live_results):
    case = _case(live_results, "w1-positive-duplicate-final-index")
    assert_equal(case["mutator"]["invocations"], 1, "exactly one real Blender mutation")
    assert_equal(case["mutator"]["engine_edits"], 1, "one engine edit")
    assert_equal(case["mutator"]["primitive"], "pattern_b_same_datablock", "Pattern B primitive")
    assert_equal(case["receipt"]["result"], "COMPLETED", "W1 outcome")
    assert_equal(case["receipt"]["field_count"], RECEIPT_FIELD_COUNT, "W1 receipt field count")
    assert_equal(case["receipt"]["executed_correction_ids"], case["binding"]["correction_ids"],
                 "W1 executed correction ids")
    assert_equal(case["receipt"]["skipped_correction_ids"], [], "W1 skipped correction ids")
    assert case["receipt"]["output_report_digest"] == case["post"]["digest"]
    assert case["receipt"]["source_report_digest_recomputed"] == case["plan"]["source_report_digest"]


# --------------------------------------------------------------------------- W1 material evidence
def test_w1_positive_material_evidence_is_non_vacuous_and_preserved(live_results):
    case = _case(live_results, "w1-positive-duplicate-final-index")
    assert_anti_vacuity(case["pre"]["materials"], "W1 positive")
    assert_material_key(True, ["turf", "line_markings"], case["pre"]["materials"], "W1 pre materials")
    assert_material_key(True, ["turf", "line_markings"], case["post"]["materials"], "W1 post materials")
    assert_equal(case["pre"]["materials"]["representation_state"], [],
                 "this fixture must not be in a materials-omitted representation state")
    assert_raw_slots([["DATA", "turf"], ["DATA", "line_markings"]],
                     _raw_object(case["raw_before"], "pitch")["material_slots"], "W1 pre raw slots")
    assert_raw_slots([["DATA", "turf"], ["DATA", "line_markings"]],
                     _raw_object(case["raw_after"], "pitch")["material_slots"], "W1 post raw slots")
    assert_raw_slots([["DATA", "banner"]], _raw_object(case["raw_after"], "goal")["material_slots"],
                     "unrelated object raw slots")


def test_w1_unassigned_slot_case_is_raw_only(live_results):
    """An unassigned slot is invisible canonically (key omitted) but must be preserved raw."""
    case = _case(live_results, "w1-positive-unassigned-slot-raw-only")
    assert_equal(case["receipt"]["result"], "COMPLETED", "unassigned-slot case outcome")
    assert_material_key(False, None, case["pre"]["materials"], "unassigned-slot pre canonical")
    assert_material_key(False, None, case["post"]["materials"], "unassigned-slot post canonical")
    assert_equal(case["pre"]["materials"]["representation_state"], ["materials:omitted"],
                 "the producer omits the key for unassigned slots (frozen behaviour)")
    assert_raw_slots([["DATA", "turf"], ["DATA", None], ["DATA", "goal_net"]],
                     _raw_object(case["raw_before"], "pitch")["material_slots"], "unassigned pre raw")
    assert_raw_slots([["DATA", "turf"], ["DATA", None], ["DATA", "goal_net"]],
                     _raw_object(case["raw_after"], "pitch")["material_slots"], "unassigned post raw")


def test_w1_object_linked_slot_case_is_raw_only(live_results):
    case = _case(live_results, "w1-positive-object-linked-slot-raw-only")
    assert_equal(case["receipt"]["result"], "COMPLETED", "OBJECT-linked case outcome")
    assert_material_key(False, None, case["pre"]["materials"], "OBJECT-linked pre canonical")
    assert_material_key(False, None, case["post"]["materials"], "OBJECT-linked post canonical")
    assert_raw_slots([["DATA", "turf"], ["OBJECT", "line_markings"]],
                     _raw_object(case["raw_before"], "pitch")["material_slots"], "obj-linked pre raw")
    assert_raw_slots([["DATA", "turf"], ["OBJECT", "line_markings"]],
                     _raw_object(case["raw_after"], "pitch")["material_slots"], "obj-linked post raw")


def test_w1_documented_material_index_non_claim_is_not_asserted(live_results):
    """§G: no case may claim per-face material assignment survived a geometry rebuild."""
    source = open(SCRIPT, encoding="utf-8").read()
    gate_source = open(os.path.abspath(__file__), encoding="utf-8").read()
    assert "polygon.material_index" in source and "polygon.material_index" in gate_source, (
        "the non-claim must be documented in both driver and gate")
    for case in live_results["cases"]:
        # no case records (let alone asserts) per-face material assignment, at either layer
        assert "material_index" not in json.dumps(case["raw_before"])
        assert "material_index" not in json.dumps(case["raw_after"])
        assert "material_index" not in json.dumps(case["pre"]["materials"])
        assert "material_index" not in json.dumps(case["post"]["materials"])


# --------------------------------------------------------------------------- W1 negatives
def test_w1_negative_both_members_removed_is_postcondition_failed(live_results):
    case = _case(live_results, "w1-negative-both-members-removed")
    assert_equal(case["receipt"]["result"], "POSTCONDITION_FAILED", "both-members outcome")
    assert_equal(case["receipt"]["failure_code"], "POSTCONDITION_FAILED", "both-members failure code")
    assert_equal(case["mutator"]["invocations"], 1, "the mutator did run")
    assert_equal(_raw_object(case["raw_after"], "pitch")["faces"], [[0, 1, 2], [0, 1, 3]],
                 "raw post state shows both members gone")
    assert case["receipt"]["output_report_digest"] is not None, "fresh extraction still happened"
    assert case["receipt"]["rollback_performed"] is False, "no rollback: fail-closed, not repaired"


def test_w1_negative_wrong_face_and_noop_and_liar(live_results):
    wrong = _case(live_results, "w1-negative-wrong-face-removed")
    assert_equal(_outcome(wrong), ("POSTCONDITION_FAILED", "POSTCONDITION_FAILED"), "wrong face")
    assert_equal(_raw_object(wrong["raw_after"], "pitch")["faces"],
                 [[0, 1, 3], [4, 5, 6], [4, 5, 6]], "wrong face removed raw state")
    for label in ("w1-negative-noop-mutator", "w1-negative-liar-mutator"):
        case = _case(live_results, label)
        assert_equal(_outcome(case), ("POSTCONDITION_FAILED", "POSTCONDITION_FAILED"), label)
        assert_equal(case["raw_after"], case["raw_before"], f"{label}: engine state unchanged")
        assert_equal(case["mutator"]["invocations"], 1, f"{label}: mutator was invoked")
        if "liar" in label:
            assert case["mutator"]["liar"] is True, "the liar claimed success"


def test_w1_negative_vertex_and_unrelated_object_mutation(live_results):
    vertex = _case(live_results, "w1-negative-vertex-mutation")
    assert_equal(_outcome(vertex), ("POSTCONDITION_FAILED", "POSTCONDITION_FAILED"), "vertex mutation")
    assert _raw_object(vertex["raw_after"], "pitch")["vertices"] != \
        _raw_object(vertex["raw_before"], "pitch")["vertices"], "the vertex really moved"
    unrelated = _case(live_results, "w1-negative-unrelated-object-mutation")
    assert_equal(_outcome(unrelated), ("POSTCONDITION_FAILED", "POSTCONDITION_FAILED"),
                 "unrelated object mutation")
    assert_equal(_raw_object(unrelated["raw_after"], "goal"),
                 {"name": "goal", "type": "MESH", "data_block": "goal", "vertex_count": 5,
                  "edge_count": 3, "polygon_count": 1, "loops": 3, "polygon_sizes": [3],
                  "vertices": [[99.0, 99.0, 99.0], [21.0, 20.0, 20.0], [20.0, 21.0, 20.0],
                               [20.0, 22.0, 20.0], [21.0, 22.0, 20.0]],
                  "faces": [[0, 1, 2]], "material_slots": [["DATA", "banner"]],
                  "collections": ["Goals"]},
                 "unrelated object raw state after the hostile mutation")


def test_w1_negative_survivor_pair_altered_is_refused(live_results):
    case = _case(live_results, "w1-negative-survivor-pair-altered")
    assert_equal(_outcome(case), ("POSTCONDITION_FAILED", "POSTCONDITION_FAILED"),
                 "altering the unrelated winding pair must be refused")
    assert_equal(_raw_object(case["raw_after"], "pitch")["faces"],
                 [[0, 1, 2], [3, 1, 0], [4, 5, 6]], "the survivor really was reversed")


def test_w1_negatives_that_never_touch_the_engine(live_results):
    for label, expected in (
        ("w1-negative-recorded-pair-not-duplicate", ("PRECONDITION_FAILED", "PRECONDITION_FAILED")),
        ("w1-negative-wrong-mesh", ("PRECONDITION_FAILED", "PRECONDITION_FAILED")),
        ("w1-negative-missing-target-object", ("PRECONDITION_FAILED", "PRECONDITION_FAILED")),
        ("w1-negative-stale-source-digest", ("SOURCE_MISMATCH", "SOURCE_DIGEST_MISMATCH")),
        ("w1-negative-malformed-parameters",
         ("PLAN_INVALID", "UNEXPECTED_PARAMETER:unexpected_key")),
    ):
        case = _case(live_results, label)
        assert_equal(_outcome(case), expected, label)
        assert_equal(case["mutator"]["invocations"], 0, f"{label}: ZERO mutator invocations")
        assert_equal(case["raw_after"], case["raw_before"], f"{label}: raw state bit-identical")
        assert_equal(case["post"]["faces"], case["pre"]["faces"], f"{label}: canonical faces equal")
        assert_equal(case["post"]["digest"], case["pre"]["digest"], f"{label}: same state digest")
        assert case["receipt"]["plan_integrity_ok"] is True, f"{label}: plan integrity was valid"


def test_w1_digest_first_engine_mutation_after_planning(live_results):
    """The plan is real, integrity-valid, and refused because the ENGINE state moved first."""
    case = _case(live_results, "w1-negative-digest-first-engine-mutated")
    receipt = case["receipt"]
    assert_equal(_outcome(case), ("SOURCE_MISMATCH", "SOURCE_DIGEST_MISMATCH"), "digest-first outcome")
    assert receipt["plan_integrity_ok"] is True, "plan integrity was valid"
    assert receipt["source_report_digest_recomputed"] != case["plan"]["source_report_digest"], (
        "the engine digest moved away from the plan's source digest")
    assert_equal(case["mutator"]["invocations"], 0, "ZERO mutator invocations")
    assert_equal(case["raw_after"], case["raw_before"], "the executor changed nothing")


# --------------------------------------------------------------------------- W1 evidence limits
def test_w1_middle_duplicate_renumbering_is_detected_by_the_policy_assertion(live_results):
    """A fixture-policy violation the canonical multiset delta ACCEPTS: only the map catches it."""
    case = _case(live_results, "w1-evidence-middle-duplicate-renumbering")
    assert_equal(case["receipt"]["result"], "COMPLETED",
                 "the one-face multiset delta still holds, so the canonical layer completes")
    assert_equal(case["renumbering_map"], [[0, 0], [1, 1], [2, 2], [4, 3]],
                 "the follower face 4 was renumbered to 3")
    assert case["identity_renumbering"] is False
    with pytest.raises(AssertionError):     # the identity policy assertion MUST fire here
        assert_identity_map(case["renumbering_map"], [[0, 0], [1, 1], [2, 2], [3, 3]], "policy")
    assert_equal(case["post"]["histogram"][WINDING]["measured"], [{"edge": [0, 1], "faces": [0, 1]}],
                 "the unrelated winding survivor payload is still stable")


def test_w1_net_multiset_equivalent_mutation_is_a_documented_limitation(live_results):
    """Measured limit: state comparison cannot distinguish a net-equivalent multi-face edit."""
    case = _case(live_results, "w1-evidence-net-multiset-equivalent-mutation")
    assert_equal(case["receipt"]["result"], "COMPLETED", "net-equivalent edit is accepted")
    assert_equal(case["mutator"]["invocations"], 1, "one invocations counter increment")
    assert_equal(case["mutator"]["engine_edits"], 2, "TWO engine rebuilds actually happened")
    assert_equal(_raw_object(case["raw_after"], "pitch")["faces"],
                 _raw_object(_case(live_results, "w1-positive-duplicate-final-index")
                             ["raw_after"], "pitch")["faces"],
                 "the resulting raw table is indistinguishable from the authorized one")


def test_w1_material_slot_destruction_is_invisible_to_the_canonical_postcondition(live_results):
    """The W1 postcondition has NO material clause: gate-side canonical+raw evidence is load-bearing."""
    case = _case(live_results, "w1-evidence-material-slot-destruction")
    assert_equal(case["receipt"]["result"], "COMPLETED", "the executor cannot see slot loss")
    assert_anti_vacuity(case["pre"]["materials"], "slot-destruction pre-state")
    assert_material_key(False, None, case["post"]["materials"], "post canonical materials")
    assert_equal(case["post"]["materials"]["canonical"], [], "canonical material tuple emptied")
    assert_raw_slots([["DATA", None]], _raw_object(case["raw_after"], "pitch")["material_slots"],
                     "destroyed raw slot table")
    assert_inventory(["goal", "pitch"], case["raw_after"]["mesh_datablocks"],
                     "no datablock was orphaned by in-place slot destruction")


def test_w1_datablock_replacement_is_caught_by_raw_evidence_only(live_results):
    case = _case(live_results, "w1-evidence-datablock-replacement")
    assert_equal(case["receipt"]["result"], "COMPLETED", "Pattern A is canonical-contract-legal")
    assert_material_key(True, [], case["post"]["materials"], "post canonical materials")
    assert_raw_slots([], _raw_object(case["raw_after"], "pitch")["material_slots"],
                     "Pattern A destroyed the slot table")
    assert_equal(case["raw_before"]["mesh_datablocks"], ["goal", "pitch"], "pre inventory")
    with pytest.raises(AssertionError):     # the inventory assertion MUST fire on this gain
        assert_inventory(case["raw_before"]["mesh_datablocks"],
                         case["raw_after"]["mesh_datablocks"], "datablock inventory")
    assert_equal(case["raw_after"]["mesh_datablocks"], ["goal", "pitch", "pitch.001"],
                 "post inventory gained the replacement datablock")
    assert_equal(_raw_object(case["raw_after"], "pitch")["data_block"], "pitch.001",
                 "the datablock was replaced")
    assert "pitch.001" in case["raw_after"]["mesh_datablocks"]


def test_w1_orphan_inventory_gain_is_caught_by_raw_evidence_only(live_results):
    case = _case(live_results, "w1-evidence-orphan-inventory-gain")
    assert_equal(case["receipt"]["result"], "COMPLETED", "the canonical layer sees nothing")
    assert_equal(case["raw_after"]["mesh_datablocks"], ["goal", "pitch", "w1_w1b_orphan_probe"],
                 "raw datablock inventory gained an orphan")
    assert_raw_slots([["DATA", "turf"], ["DATA", "line_markings"]],
                     _raw_object(case["raw_after"], "pitch")["material_slots"],
                     "slots survived while the orphan appeared")


# --------------------------------------------------------------------------- W1b positives
def test_w1b_positive_zero_area_collinear(live_results):
    case = _case(live_results, "w1b-positive-zero-area-collinear")
    assert_equal(case["pre"]["histogram"], {
        DEG: {"count": 1, "measured": [{"face": 0, "signed_area": 0.0}]},
        WINDING: {"count": 1, "measured": [{"edge": [0, 1], "faces": [0, 1]}]}},
        "W1b zero-area pre histogram")
    assert_equal(case["post"]["histogram"], {}, "W1b zero-area post histogram")
    assert_equal(case["pre"]["faces"], [[0, 1, 2], [0, 1, 3]], "W1b pre faces")
    assert_equal(case["post"]["faces"], [[0, 1, 3]], "W1b post faces")
    assert_multiset_delta(case["pre"]["faces"], case["post"]["faces"], [0, 1, 2], "W1b delta")
    assert_equal(case["mutator"]["invocations"], 1, "one mutation")
    assert_equal(case["receipt"]["result"], "COMPLETED", "W1b outcome")
    assert_anti_vacuity(case["pre"]["materials"], "W1b zero-area positive")
    assert_material_key(True, ["turf", "line_markings"], case["post"]["materials"], "W1b materials")
    assert_raw_slots([["DATA", "turf"], ["DATA", "line_markings"]],
                     _raw_object(case["raw_after"], "pitch")["material_slots"], "W1b raw slots")


def test_w1b_two_vertex_face_is_proven_at_the_raw_layer_and_through_the_real_path(live_results):
    """F-1 CASE A: a 2-vertex polygon is a REAL polygon, extracted, parsed and found degenerate."""
    case = _case(live_results, "w1b-positive-two-vertex-face")
    raw_before = _raw_object(case["raw_before"], "pitch")
    assert_equal(raw_before["vertex_count"], 2, "2 vertices")
    assert_equal(raw_before["polygon_count"], 1, "exactly 1 polygon")
    assert_equal(raw_before["loops"], 2, "2 loops")
    assert_equal(raw_before["polygon_sizes"], [2], "the polygon has two corners")
    assert_equal(raw_before["faces"], [[0, 1]], "raw polygon content")
    assert_equal(raw_before["edge_count"], 1, "1 edge")
    assert_equal(case["pre"]["faces"], [[0, 1]], "canonical face (0,1) reached the parser")
    assert_equal(case["pre"]["histogram"],
                 {DEG: {"count": 1, "measured": [{"face": 0, "vertex_count": 2}]}},
                 "MESH_DEGENERATE_FACE with vertex_count == 2")
    assert_equal(case["mutator"]["calls"][0]["face_tuple"], [0, 1], "mutator got the exact tuple")


def test_w1b_two_vertex_positive_post_state_is_the_canonical_zero_face_state(live_results):
    case = _case(live_results, "w1b-positive-two-vertex-face")
    assert_equal(case["receipt"]["result"], "COMPLETED", "two-vertex outcome")
    assert_equal(_raw_object(case["raw_after"], "pitch")["polygon_count"], 0, "0 polygons")
    assert_equal(_raw_object(case["raw_after"], "pitch")["loops"], 0, "0 loops")
    assert_equal(_raw_object(case["raw_after"], "pitch")["vertex_count"], 2, "2 vertices remain")
    assert_equal(case["post"]["faces"], [], "canonical faces == ()")
    assert_equal(case["post"]["histogram"], {}, "no degenerate finding remains")
    assert_equal(case["mutator"]["invocations"], 1, "exactly one mutation")
    assert_equal(case["renumbering_map"], [], "no face survives, so no renumbering")


def test_w1b_only_face_zero_face_post_state(live_results):
    case = _case(live_results, "w1b-positive-only-face-zero-face-post-state")
    assert_equal(case["receipt"]["result"], "COMPLETED", "zero-face outcome")
    assert_equal(case["pre"]["faces"], [[0, 1, 2]], "the single face is the degenerate one")
    assert_equal(case["post"]["faces"], [], "canonical faces == ()")
    assert_equal(case["post"]["vertex_count"], 3, "vertices are untouched")
    raw_after = _raw_object(case["raw_after"], "pitch")
    assert_equal([raw_after["polygon_count"], raw_after["vertex_count"]], [0, 3],
                 "raw zero-face state")
    assert_equal(case["post"]["histogram"], {}, "no findings remain")
    assert_equal(case["mutator"]["invocations"], 1, "exactly one mutation")
    assert_raw_slots([["DATA", "turf"], ["DATA", "line_markings"]], raw_after["material_slots"],
                     "zero-face post state keeps its slots")


def test_w1b_untargeted_degeneracy_remains_on_the_other_object(live_results):
    """No global degeneracy-clear requirement exists (contract docstring, proven live)."""
    case = _case(live_results, "w1b-evidence-untargeted-degeneracy-remains")
    assert_equal(case["receipt"]["result"], "COMPLETED", "untargeted-degeneracy outcome")
    assert_equal(case["pre"]["decoy_histogram"],
                 {DEG: {"count": 1, "measured": [{"face": 1, "signed_area": 0.0}]},
                  "MESH_SCALE_OUT_OF_RANGE": {"count": 1,
                                             "measured": [{"vertex": 0,
                                                           "world": [20.0, 20.0, 20.0]}]}},
                 "the decoy really carries a degenerate face")
    assert_equal(case["post"]["decoy_histogram"], case["pre"]["decoy_histogram"],
                 "the untargeted degeneracy must SURVIVE")
    assert_equal(case["post"]["histogram"], {}, "the targeted degeneracy is cleared")
    assert_equal(case["mutator"]["invocations"], 1, "exactly one mutation")


# --------------------------------------------------------------------------- W1b revalidation (F-2)
def test_w1b_same_digest_revalidation_refusal(live_results):
    """F-2: the recorded face EXISTS but is no longer degenerate; refused at PRECONDITION level."""
    case = _case(live_results, "w1b-negative-recorded-face-not-degenerate")
    receipt = case["receipt"]
    assert_equal((receipt["result"], receipt["failure_code"]),
                 ("PRECONDITION_FAILED", "PRECONDITION_FAILED"), "revalidation outcome")
    # the plan is the REAL planner's output with only the documented recorded-index remap
    assert_equal(case["binding"]["proposal_count"], 1, "one capability proposal")
    assert_equal(case["binding"]["parameters"],
                 [{"mesh_id": "pitch", "face_id": 1, "reason": "degenerate_face"}],
                 "only the recorded face_id was remapped")
    assert receipt["plan_integrity_ok"] is True, "the remapped plan is contract-valid"
    assert_equal(receipt["source_report_digest_recomputed"], case["plan"]["source_report_digest"],
                 "SAME digest: the failure is precondition revalidation, not a source change")
    assert_equal(case["pre"]["digest"], case["post"]["digest"], "the engine state did not change")
    assert_equal(case["mutator"]["invocations"], 0, "ZERO mutator invocations")
    assert_equal(case["raw_after"], case["raw_before"], "raw state bit-identical")
    assert_equal(case["pre"]["histogram"][DEG],
                 {"count": 1, "measured": [{"face": 0, "signed_area": 0.0}]},
                 "the real degeneracy is still present afterwards")
    # GLM m-3: the discriminator plan is the REAL planner's output; the ONLY difference from the
    # faithful case is the recorded face index (rationale/preconditions/expected postcondition, the
    # source digest and every other contract field are identical planner output)
    faithful = _case(live_results, "w1b-positive-zero-area-collinear")
    remapped, real = case["binding"]["correction_contract"], faithful["binding"]["correction_contract"]
    assert remapped is not None and real is not None
    for key in ("finding_code", "rationale", "preconditions", "expected_postcondition", "risk",
                "severity", "reversibility", "determinism", "requires_human_review"):
        assert_equal(remapped[key], real[key],
                     f"m-3: remapped plan field {key!r} must be the planner's own output")
    assert_equal(case["plan"]["source_report_digest"], faithful["plan"]["source_report_digest"],
                 "m-3: the remap did not touch the plan's source digest")
    assert_equal([p for p in case["binding"]["parameters"]], [{"mesh_id": "pitch", "face_id": 1,
                                                              "reason": "degenerate_face"}],
                 "m-3: only the recorded face_id was remapped")
    assert_equal(real["preconditions"][0]["source_report_digest"], case["pre"]["digest"],
                 "m-3: the planner's preconditions bind the REAL live digest")


def test_w1b_digest_first_engine_mutation_after_planning(live_results):
    case = _case(live_results, "w1b-negative-digest-first-engine-mutated")
    receipt = case["receipt"]
    assert_equal((receipt["result"], receipt["failure_code"]),
                 ("SOURCE_MISMATCH", "SOURCE_DIGEST_MISMATCH"), "digest-first outcome")
    assert receipt["source_report_digest_recomputed"] != case["plan"]["source_report_digest"], (
        "the engine digest must differ from the plan's source digest")
    assert_equal(receipt["plan_integrity_ok"], True, "plan integrity still valid")
    assert_equal(case["mutator"]["invocations"], 0, "ZERO mutations")
    assert_equal(case["raw_after"], case["raw_before"], "raw state untouched by the executor")


def test_w1b_negative_family(live_results):
    for label, expected in (
        ("w1b-negative-wrong-face-removed", ("POSTCONDITION_FAILED", "POSTCONDITION_FAILED")),
        ("w1b-negative-noop-mutator", ("POSTCONDITION_FAILED", "POSTCONDITION_FAILED")),
        ("w1b-negative-liar-mutator", ("POSTCONDITION_FAILED", "POSTCONDITION_FAILED")),
        ("w1b-negative-vertex-mutation", ("POSTCONDITION_FAILED", "POSTCONDITION_FAILED")),
        ("w1b-negative-unrelated-object-mutation", ("POSTCONDITION_FAILED", "POSTCONDITION_FAILED")),
        ("w1b-negative-ambiguous-multiple-degenerate-faces",
         ("PLAN_INVALID", "AMBIGUOUS_MULTIPLE_EXECUTABLE_CORRECTIONS")),
        ("w1b-negative-wrong-mesh", ("PRECONDITION_FAILED", "PRECONDITION_FAILED")),
        ("w1b-negative-malformed-parameters",
         ("PLAN_INVALID", "UNEXPECTED_PARAMETER:unexpected_key")),
        ("w1b-negative-stale-source-digest", ("SOURCE_MISMATCH", "SOURCE_DIGEST_MISMATCH")),
    ):
        case = _case(live_results, label)
        assert_equal(_outcome(case), expected, label)
        assert case["capability"] == W1B, f"{label}: capability parameterization"
        assert case["receipt"]["has_authorization_verified_field"] is False, (
            f"{label}: W1b has NO authorization artifact and no authorization check")
    # zero-invocation cases must not have touched the engine at all
    for label in ("w1b-negative-ambiguous-multiple-degenerate-faces", "w1b-negative-wrong-mesh",
                  "w1b-negative-malformed-parameters", "w1b-negative-stale-source-digest"):
        case = _case(live_results, label)
        assert_equal(case["mutator"]["invocations"], 0, f"{label}: zero mutations")
        assert_equal(case["raw_after"], case["raw_before"], f"{label}: raw state unchanged")


def test_w1b_wrong_face_and_vertex_mutation_raw_evidence(live_results):
    wrong = _case(live_results, "w1b-negative-wrong-face-removed")
    assert_equal(_raw_object(wrong["raw_after"], "pitch")["faces"], [[0, 1, 2]],
                 "the NON-degenerate face (1) was removed instead of the recorded degenerate face")
    assert_equal(wrong["pre"]["histogram"][DEG],
                 {"count": 1, "measured": [{"face": 0, "signed_area": 0.0}]}, "pre degeneracy")
    vertex = _case(live_results, "w1b-negative-vertex-mutation")
    assert_equal(vertex["post"]["histogram"].get(DEG),
                 {"count": 1, "measured": [{"face": 0, "signed_area": 0.0}]},
                 "the degenerate face survived the hostile vertex mutation")
    assert DV not in vertex["post"]["histogram"] and "MESH_DUPLICATE_VERTEX" in \
        vertex["post"]["histogram"], "the collateral damage is visible in the fresh report"


def test_w1b_material_slot_destruction_is_gate_side_only(live_results):
    case = _case(live_results, "w1b-evidence-material-slot-destruction")
    assert_equal(case["receipt"]["result"], "COMPLETED", "the executor cannot see slot loss")
    assert_anti_vacuity(case["pre"]["materials"], "W1b slot-destruction pre-state")
    assert_material_key(False, None, case["post"]["materials"], "W1b post canonical materials")
    assert_raw_slots([["DATA", None]], _raw_object(case["raw_after"], "pitch")["material_slots"],
                     "W1b destroyed raw slot table")


# --------------------------------------------------------------------------- parser limitation
def test_repeated_index_polygon_remains_a_parser_limitation(live_results):
    """Never a live-positive case: the canonical parser refuses repeated indices, unchanged."""
    limitation = live_results["repeated_index_limitation"]
    raw = limitation["raw_before_parse"]
    assert_equal(raw["faces"], [[0, 0, 1]], "Blender really persists the repeated-index polygon")
    assert_equal(raw["polygon_count"], 1, "it is a real polygon")
    assert_equal(limitation["payload_faces"], [[0, 0, 1]], "extraction emits it faithfully")
    assert_equal(limitation["parse_ok"], False, "the canonical parser must refuse it")
    assert_equal(limitation["failure_type"], "SceneReportInputError", "refusal type")
    assert_equal(limitation["failure_message"], "mesh face must not repeat a vertex index",
                 "refusal message")
    assert limitation["failure_site"].startswith("scene_model.py:"), "refusal site"
    assert_equal(limitation["live_positive_coverage"], "NOT_APPLICABLE",
                 "coverage classification")


# --------------------------------------------------------------------------- save attempt
def test_save_attempt_is_refused_and_creates_nothing(live_results):
    """A real save attempt happens, is refused by the engine, and writes NOTHING anywhere."""
    probe = live_results["save_attempt"]
    assert_equal(probe["filepath_before"], "", "no .blend was loaded, so there is no save target")
    assert_equal(probe["refused"], True, "the engine must refuse to save an unsaved file")
    assert_equal(probe["error_type"], "RuntimeError", "refusal type")
    assert "filepath" in probe["error_message"], (
        f"refusal must name the missing filepath: {probe['error_message']!r}")
    assert_equal(probe["files_created_in_sandbox"], [],
                 "the sandboxed save attempt created no file")
    assert_equal(probe["filepath_after"], "", "Blender still has no file bound after the attempt")
    assert_equal(probe["sandbox_removed"], True, "the sandbox directory was removed")
    assert_equal(live_results["session"]["filepath_at_end"], "", "session ends with no file bound")
    assert_equal(live_results["session"]["saved_anything"], False, "nothing was saved")
    assert live_results["_blend_snapshot_unchanged"] is True, "no .blend/.blend1 appeared in the repo"


# --------------------------------------------------------------------------- documented limitations
def test_documented_limitations_are_stated_in_the_gate_documentation():
    gate_source = open(os.path.abspath(__file__), encoding="utf-8").read()
    for required in ("polygon.material_index", "TEST-ONLY", "repeated-index", "MULTISET delta",
                     "REPAIR_FACE_WINDING", "NOT implemented here", "documented limitation"):
        assert required in gate_source, f"gate documentation must state: {required}"
