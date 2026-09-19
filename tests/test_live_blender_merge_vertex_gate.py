"""LIVE Blender gate for REPAIR_MERGE_VERTEX (Wave-3 Slice 3). Operator-gated; NOT run in CI.

Runs the real Blender 4.4.3 process against the disposable in-memory fixtures built by
``tests/merge_vertex_live_script.py`` and asserts the complete live path:

    live Blender scene -> extraction -> SceneModel/SceneReport -> plan
    -> human-authored authorization -> execute_merge_vertex -> REAL Blender mutation
    -> fresh extraction -> MQ-1..MQ-7 -> receipt

It never opens or writes a ``.blend``: Blender is started WITHOUT a file argument, all fixtures are
built in memory, and the frozen validation asset is hash-checked before/after and must stay
byte-identical. No workflow/action-runner tests are involved.

Explicit authorized run only::

    ATLAS_RUN_LIVE_BLENDER=1 .venv/Scripts/python.exe -m pytest \
        tests/test_live_blender_merge_vertex_gate.py -s
"""

import hashlib
import json
import os
import subprocess

import pytest

FROZEN_ASSET = os.path.join("tests", "assets", "blender", "atlas_transform_validation.blend")
FROZEN_SHA256 = "cf618bdc1123734bf49bf6f22677ded3f2e6c3fa2803b97f7a6cf7c7c66f11aa"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "tests", "merge_vertex_live_script.py")


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

    env = dict(os.environ)
    env["PYTHONPATH"] = REPO
    proc = subprocess.run(
        [tb.BLENDER, "--background", "--python", SCRIPT],
        capture_output=True, text=True, timeout=600, cwd=REPO, env=env,
    )
    stdout = proc.stdout
    start = stdout.find("ATLAS_MERGE_LIVE_START")
    end = stdout.find("ATLAS_MERGE_LIVE_END")
    assert proc.returncode == 0, f"blender rc={proc.returncode}: {proc.stderr[-3000:]}"
    assert start != -1 and end != -1, f"live markers missing\n{stdout[-4000:]}"
    results = json.loads(stdout[start + len("ATLAS_MERGE_LIVE_START"):end].strip())

    blends_after = _blend_files()
    assert blends_after == blends_before, "a .blend/.blend1 file was created or modified"
    assert _sha256(os.path.join(REPO, FROZEN_ASSET)) == FROZEN_SHA256, "frozen asset changed"
    results["_blend_snapshot_unchanged"] = True
    return results


def _case(results, label):
    for case in results["cases"]:
        if case["case"] == label:
            return case
    raise AssertionError(f"case {label} missing; errors={results['errors']}")


def test_environment_and_no_persistence(live_results):
    env = live_results["environment"]
    assert env["blender_version"] == "4.4.3"
    assert env["build_hash"] == "802179c51ccc"
    assert env["build_date"] == "2025-04-29"
    assert env["frozen_asset_sha256"] == FROZEN_SHA256
    assert env["filepath_at_start"] == "", "Blender must start with NO .blend loaded"
    assert live_results["errors"] == []
    assert live_results["session"]["filepath_at_end"] == ""
    assert live_results["session"]["saved_anything"] is False
    assert live_results["_blend_snapshot_unchanged"] is True


def test_positive_b1_live_merge_completes(live_results):
    case = _case(live_results, "positive-B1-live")
    assert case["mode"] == "real_planner", "this case must take its plan from the real planner"
    receipt = case["receipt"]
    assert case["mutator_invocations"] == 1, "exactly one real Blender mutation"
    assert receipt["result"] == "COMPLETED" and receipt["failure_code"] is None
    assert receipt["field_count"] == 44
    assert receipt["pre_vertex_count"] == 6 and receipt["post_vertex_count"] == 4
    assert receipt["duplicate_groups"] == [[0, 1], [3, 4]]
    assert receipt["survivor_indices"] == [0, 3]
    assert receipt["removed_vertex_indices"] == [1, 4]
    assert receipt["changed_face_indices"] == [0, 1]
    assert receipt["authorization_verified"] is True
    assert receipt["target_object_mesh"] == {"object_id": "pitch", "mesh_id": "pitch"}

    # the merge really happened in Blender and the renumbering is visible in the RAW state
    before, after = case["raw_before"], case["raw_after"]
    target_before = next(o for o in before["objects"] if o["name"] == "pitch")
    target_after = next(o for o in after["objects"] if o["name"] == "pitch")
    assert target_before["vertex_count"] == 6 and target_after["vertex_count"] == 4
    assert target_before["faces"] == [[0, 2, 3], [5, 2, 3]]
    assert target_after["faces"] == [[0, 1, 2], [3, 1, 2]]
    assert [v[0] for v in target_after["vertices"]] == [0.0, 7.0, 3.0, 4.0]
    # the datablock is REPLACED (design §9) - identity is proven by the model, not the block name
    assert target_before["data_block"] != target_after["data_block"]
    assert target_before["name"] == target_after["name"]

    # exact post tables, checked against the fixture + the derived kept set (independent here)
    derived = case["derived"]
    kept = derived["kept"]
    mapping = derived["mapping"]
    expected_vertices = [[float(c) for c in case["fixture"]["vertices"][k]] for k in kept]
    expected_faces = [[mapping[i] for i in f] for f in case["fixture"]["faces"]]
    assert case["post"]["vertices"] == expected_vertices
    assert case["post"]["faces"] == expected_faces
    assert receipt["old_to_new_mapping"] == mapping


def test_positive_b1_live_is_the_B1_class_and_MQ_all_pass(live_results):
    case = _case(live_results, "positive-B1-live")
    receipt = case["receipt"]
    assert case["pre"]["winding"] == [{"edge": [2, 3], "faces": [0, 1]}]
    assert case["pre"]["duplicate_vertex"] and len(case["pre"]["duplicate_vertex"]) == 2
    # B-1 live analogue: the class stays PRESENT, only its measured index payload renumbers
    assert case["post"]["winding"] == [{"edge": [1, 2], "faces": [0, 1]}]
    assert case["post"]["winding"] != case["pre"]["winding"]
    assert case["post"]["duplicate_vertex"] == []
    assert [e["reason"].split(":")[0] for e in receipt["postcondition_results"]] == [
        "MQ-1", "MQ-2", "MQ-3", "MQ-4", "MQ-5", "MQ-6", "MQ-7"]
    assert all(e["ok"] is True for e in receipt["postcondition_results"])
    assert all(e["ok"] is True for e in receipt["precondition_results"])
    assert receipt["pre_winding_findings"][0]["measured"] == {"edge": [2, 3], "faces": [0, 1]}
    assert receipt["post_winding_findings"][0]["measured"] == {"edge": [1, 2], "faces": [0, 1]}
    assert receipt["output_report_digest"] == case["post"]["digest"]
    assert receipt["source_report_digest_recomputed"] == case["pre"]["digest"]
    assert receipt["executed_correction_ids"] == [receipt["executed_correction_ids"][0]]
    assert receipt["vertex_merge_only"] is True and receipt["index_renumbering_only"] is True
    assert receipt["geometry_unverifiable"] is False
    assert receipt["normal_agreement_not_verified"] is True
    assert receipt["persisted"] is False and receipt["rollback_performed"] is False


def test_unrelated_live_state_is_bit_identical(live_results):
    for label in ("positive-B1-live", "positive-tail-real-planner", "positive-transitive-3",
                  "positive-middle-table-real-planner"):
        case = _case(live_results, label)
        before, after = case["raw_before"], case["raw_after"]
        assert after["object_count"] == before["object_count"]
        assert [o["name"] for o in after["objects"]] == [o["name"] for o in before["objects"]]
        assert after["collections"] == before["collections"]
        for other in ("goal", "marker"):
            b = next(o for o in before["objects"] if o["name"] == other)
            a = next(o for o in after["objects"] if o["name"] == other)
            assert a == b, f"{label}: unrelated object {other} changed"
        # the second mesh datablock (goal) is untouched
        assert ("goal" in after["mesh_datablocks"]) == ("goal" in before["mesh_datablocks"])


def test_positive_tail_case_through_the_real_planner(live_results):
    case = _case(live_results, "positive-tail-real-planner")
    assert case["planner"]["merge_corrections"] == 1
    assert case["receipt"]["result"] == "COMPLETED"
    assert case["mutator_invocations"] == 1
    assert case["derived"]["kept"] == [0, 1, 2, 3]
    assert case["receipt"]["changed_face_indices"] == []
    assert case["post"]["vertex_count"] == 4
    assert case["post"]["duplicate_vertex"] == []


def test_positive_middle_table_real_planner_preserves_pre_state_survivors(live_results):
    """Wave 13 live closure: a duplicate group whose removed member is NOT a suffix of the vertex table
    must pass through the REAL planner and execute into exactly the post-state the planner authorized.

    The pre-fix planner derived its predicted kept set from ``set(old_to_new_mapping)`` - the POST index
    range - and indexed the PRE-state table with it. For this fixture that predicts the vertices
    (0,0,0), (5,0,0), (0,0,0): a post-state that still contains the duplicate, so the planner refused
    with PARTIAL_GROUP_COVERAGE and no middle-table case could ever reach the engine. The authorized
    post-state is the surviving PRE-state subsequence [0, 1, 3].
    """
    case = _case(live_results, "positive-middle-table-real-planner")
    assert case["mode"] == "real_planner"
    assert case["planner"]["merge_corrections"] == 1, "the real planner must authorize this merge"

    # (1) the planner's OWN emitted parameters (not the harness derivation)
    params = case["planner"]["parameters"][0]
    assert params["duplicate_groups"] == [[0, 2]]
    assert params["survivor_indices"] == [0]
    assert params["old_to_new_mapping"] == [0, 1, 0, 2]
    assert params["all_groups_exact"] is True
    assert params["predicted_topology_unchanged"] is True

    # (2) the harness's independent derivation agrees, and the kept set is the PRE-state subsequence
    assert case["derived"]["groups"] == [[0, 2]]
    assert case["derived"]["survivors"] == [0]
    assert case["derived"]["kept"] == [0, 1, 3]
    assert case["derived"]["mapping"] == [0, 1, 0, 2]

    # (3) exactly one REAL Blender mutation, from the executor's own re-derivation of the same facts
    assert case["mutator_invocations"] == 1
    receipt = case["receipt"]
    assert receipt["result"] == "COMPLETED" and receipt["failure_code"] is None
    assert receipt["authorization_verified"] is True
    assert receipt["duplicate_groups"] == [[0, 2]]
    assert receipt["survivor_indices"] == [0]
    assert receipt["removed_vertex_indices"] == [2]
    assert receipt["old_to_new_mapping"] == [0, 1, 0, 2]
    assert receipt["old_to_new_mapping_digest"] == params["mapping_digest"]
    assert receipt["pre_vertex_count"] == 4 and receipt["post_vertex_count"] == 3
    assert receipt["changed_face_indices"] == [0]
    assert receipt["vertex_merge_only"] is True and receipt["index_renumbering_only"] is True
    assert receipt["persisted"] is False and receipt["rollback_performed"] is False
    assert [e["reason"].split(":")[0] for e in receipt["postcondition_results"]] == [
        "MQ-1", "MQ-2", "MQ-3", "MQ-4", "MQ-5", "MQ-6", "MQ-7"]
    assert all(e["ok"] is True for e in receipt["postcondition_results"])

    # (4) the fresh post-extraction: the duplicate is cleared and post vertex 2 is PRE vertex 3
    assert case["post"]["duplicate_vertex"] == []
    assert case["post"]["vertex_count"] == 3
    assert case["post"]["vertices"] == [[0.0, 0.0, 0.0], [5.0, 0.0, 0.0], [0.0, 5.0, 0.0]]
    assert case["post"]["faces"] == [[0, 1, 2]]

    # (5) the RAW Blender datablock really holds the authorized tables (independent of extraction)
    raw_before = next(o for o in case["raw_before"]["objects"] if o["name"] == "pitch")
    raw_after = next(o for o in case["raw_after"]["objects"] if o["name"] == "pitch")
    assert raw_before["vertex_count"] == 4 and raw_before["faces"] == [[0, 1, 3]]
    assert raw_after["vertex_count"] == 3 and raw_after["faces"] == [[0, 1, 2]]
    assert raw_after["vertices"] == [[0.0, 0.0, 0.0], [5.0, 0.0, 0.0], [0.0, 5.0, 0.0]]


def test_positive_transitive_group_live(live_results):
    case = _case(live_results, "positive-transitive-3")
    assert case["mode"] == "real_planner", "this case must take its plan from the real planner"
    assert case["receipt"]["result"] == "COMPLETED"
    assert case["mutator_invocations"] == 1
    assert case["derived"]["groups"] == [[0, 1, 2]]
    assert case["receipt"]["removed_vertex_indices"] == [1, 2]
    assert case["post"]["vertex_count"] == 4
    assert case["pre"]["winding"] == [{"edge": [0, 3], "faces": [0, 1]}]
    assert case["post"]["winding"] == [{"edge": [0, 1], "faces": [0, 1]}]


KNOWN_REFUSALS = ("PRECONDITION_FAILED", "AUTHORIZATION_REQUIRED", "AUTHORIZATION_INVALID",
                  "AUTHORIZATION_SCOPE_MISMATCH", "PLAN_INVALID", "SOURCE_MISMATCH")


@pytest.mark.parametrize("label,failure_code", [
    ("negative-missing-authorization", "AUTHORIZATION_REQUIRED"),
    ("negative-no-artifact-string", "MALFORMED_JSON"),
    ("negative-wrong-target-mesh", "MP-1"),
    ("negative-mapping-digest-mismatch", "MP-8"),
    ("negative-subgrid-declared", "SUB_GRID_COLLAPSE_UNSUPPORTED"),
    ("negative-topology-hazard", "MP-9"),
])
def test_negative_live_cases_mutate_nothing(live_results, label, failure_code):
    case = _case(live_results, label)
    assert case["mutator_invocations"] == 0, f"{label}: a mutation reached the engine"
    assert case["receipt"]["result"] in KNOWN_REFUSALS
    assert case["receipt"]["failure_code"] == failure_code
    assert case["receipt"]["authorization_verified"] is False or failure_code.startswith("MP-")
    assert case["receipt"]["persisted"] is False
    assert case["receipt"]["rollback_performed"] is False
    # the RAW Blender state is untouched (stronger than the counter)
    before = next(o for o in case["raw_before"]["objects"] if o["name"] == "pitch")
    after = next(o for o in case["raw_after"]["objects"] if o["name"] == "pitch")
    assert after == before, f"{label}: the live target was modified on a refusal path"


def test_negative_cross_plan_artifact_refused(live_results):
    case = _case(live_results, "negative-cross-plan-artifact")
    assert case["mutator_invocations"] == 0
    assert case["receipt"]["result"] in KNOWN_REFUSALS
    assert case["receipt"]["failure_code"] in ("PLAN_ID_MISMATCH", "CORRECTION_ID_MISMATCH",
                                               "AUTHORIZATION_SCOPE_MISMATCH", "MP-10")


def test_signed_zero_is_numerically_exact_live(live_results):
    """Live analogue of the disclosed F-3 behaviour: the only sub-grid shape the live extraction
    can express is IEEE signed zero, and the contract's numeric EXACT rule accepts it."""
    case = _case(live_results, "positive-signed-zero-numeric-exact")
    assert case["receipt"]["result"] == "COMPLETED"
    assert case["mutator_invocations"] == 1
    assert case["receipt"]["index_renumbering_only"] is True
    raw = next(o for o in case["raw_before"]["objects"] if o["name"] == "pitch")
    assert raw["vertices"][0] == [0.0, 0.0, 0.0] and raw["vertices"][1] == [0.0, 0.0, 0.0]


@pytest.mark.parametrize("label,failure_code,mutations", [
    ("negative-corrupt-mutator-drops-face", "MQ-3", 1),
    ("negative-corrupt-mutator-shifts-coord", "MQ-1", 1),
])
def test_corrupt_live_mutator_fails_structurally(live_results, label, failure_code, mutations):
    case = _case(live_results, label)
    assert case["mutator_invocations"] == mutations
    assert case["receipt"]["result"] == "POSTCONDITION_FAILED"
    assert case["receipt"]["failure_code"] == failure_code
    assert case["receipt"]["postcondition_results"][-1]["ok"] is False
    assert case["receipt"]["rollback_performed"] is False
    # no automatic cleanup: the engine keeps exactly the state the corrupt mutator left
    after = next(o for o in case["raw_after"]["objects"] if o["name"] == "pitch")
    if failure_code == "MQ-3":                     # a face was dropped and stays dropped
        assert after["face_count"] == 1
    else:                                          # a coordinate was shifted and stays shifted
        assert after["vertices"][0] == [1.0, 0.0, 0.0] and after["face_count"] == 2


def test_liar_live_mutator_return_value_is_not_authority(live_results):
    case = _case(live_results, "negative-liar-mutator")
    assert case["mutator_invocations"] == 1
    assert case["receipt"]["result"] == "COMPLETED"
    assert case["receipt"]["output_report_digest"] == case["post"]["digest"]
