"""A-REF conformance case matrix: every catalog case on the pure path (R4F 16, 24)."""

import pytest

from tests.aref.aref_harness import load_plan_artifact, run_pure_case
from tests.aref.fixtures import case_names, load_case


@pytest.mark.parametrize("fixture_id", case_names())
def test_case_matches_declared_expectation(fixture_id):
    spec = load_case(fixture_id)
    raw = load_plan_artifact(fixture_id)
    run = run_pure_case(spec, raw)
    exp = spec.expected
    assert run.receipt.get("result") == exp["outcomes"]["pure"], f"{fixture_id}: {run.receipt}"
    assert run.normal_form["oc_class"] == exp["oc_class"], fixture_id
    if exp.get("child_digest"):
        assert run.scene_digest_child == exp["child_digest"], fixture_id
    n = run.normal_form["invocation_count"]
    if exp["oc_class"] == "OC1":
        assert n == 0, fixture_id
        # a pre-mutation refusal mutates NOTHING: the child state equals the pre-state
        assert run.scene_digest_child == run.scene_digest_pre, fixture_id
    else:
        assert n == 1, fixture_id
    # the executor's own plan self-commit check agrees with the declared identity
    assert run.receipt.get("plan_id_recomputed") == exp["plan"]["plan_id"]


def test_aliased_verbatim_is_refusal_parity_not_post_mutation():
    run = run_pure_case(load_case("AREF-TEST-FX-AL-C1"), load_plan_artifact("AREF-TEST-FX-AL-C1"))
    assert run.receipt["result"] == "PLAN_INVALID"
    assert run.receipt["failure_code"] == "AMBIGUOUS_MULTIPLE_EXECUTABLE_CORRECTIONS"
    assert run.normal_form["invocation_count"] == 0
    assert run.normal_form["oc_class"] == "OC1"


def test_aliased_reduced_reaches_postcondition_with_shared_mutation():
    spec = load_case("AREF-TEST-FX-AL-C1-R")
    run = run_pure_case(spec, load_plan_artifact("AREF-TEST-FX-AL-C1-R"))
    assert run.receipt["result"] == "POSTCONDITION_FAILED"
    assert run.normal_form["oc_class"] == "OC5"
    assert run.normal_form["invocation_count"] == 1
    assert run.invocations[0]["selected_face_index"] == 2
    # one shared datablock record: the unrelated object's faces changed too
    db = fresh_shared_db(run)
    assert db == [[4, 5, 6], [0, 1, 2]]


def fresh_shared_db(run):
    """Recompute the shared datablock state by replaying the recorded invocation (evidence check)."""
    spec = load_case("AREF-TEST-FX-AL-C1-R")
    from tests.aref.aref_pure import fresh_graph, make_pure_mutator

    graph = fresh_graph(spec)
    kwargs = run.invocations[0]
    make_pure_mutator(spec.operation)(graph, **kwargs)
    return graph.datablocks["DB1"].faces


def test_reversed_pair_removes_face_ids_1():
    run = run_pure_case(load_case("AREF-TEST-FX-C1-REVERSED"),
                        load_plan_artifact("AREF-TEST-FX-C1-REVERSED"))
    assert run.receipt["result"] == "COMPLETED"
    kwargs = run.invocations[0]
    assert kwargs["selected_face_index"] == 0          # face_ids[1] of the recorded (2,0)
    assert tuple(kwargs["expected_face_tuple"]) == (4, 5, 6)


def test_identical_tuple_cases_have_identical_children():
    r2 = run_pure_case(load_case("AREF-TEST-FX-C1-TRIPLE-S2"), load_plan_artifact("AREF-TEST-FX-C1-TRIPLE-S2"))
    r3 = run_pure_case(load_case("AREF-TEST-FX-C1-TRIPLE-S3"), load_plan_artifact("AREF-TEST-FX-C1-TRIPLE-S3"))
    assert r2.receipt["result"] == r3.receipt["result"] == "COMPLETED"
    assert r2.scene_digest_child == r3.scene_digest_child
    assert r2.invocations[0]["selected_face_index"] == 2
    assert r3.invocations[0]["selected_face_index"] == 3
    # the RECORD establishes the request only; the children are indistinguishable (R4F 16.2(d)/(e))


def test_naming_mismatch_is_oc3_with_envelope_refusal_witness():
    run = run_pure_case(load_case("AREF-TEST-FX-MM-C1"), load_plan_artifact("AREF-TEST-FX-MM-C1"))
    assert run.receipt["result"] == "MUTATION_FAILED"
    assert run.normal_form["oc_class"] == "OC3"
    assert run.normal_form["invocation_count"] == 1
    assert run.witness.envelope_refusal_classes("pure") == ["ENVELOPE_REFUSAL"]


def test_authorization_required_negative_uses_null_fixture():
    spec = load_case("AREF-TEST-FX-C3-AUTHREQ")
    assert spec.authorization_fixture is None  # the null case is explicit
    run = run_pure_case(spec, load_plan_artifact("AREF-TEST-FX-C3-AUTHREQ"))
    assert run.receipt["result"] == "AUTHORIZATION_REQUIRED"
    assert run.normal_form["oc_class"] == "OC1"
    assert run.normal_form["invocation_count"] == 0


def test_c3_positive_executes_with_marked_authorization_fixture():
    spec = load_case("AREF-TEST-FX-C3-POS")
    auth = spec.authorization_fixture
    assert auth is not None
    assert auth["authorized_by"].startswith("AREF-TEST-")
    assert not auth["plan_id"].startswith("AREF-TEST-")  # immutable identifier untouched
    run = run_pure_case(spec, load_plan_artifact("AREF-TEST-FX-C3-POS"))
    assert run.receipt["result"] == "COMPLETED"
    assert run.normal_form["oc_class"] == "OC2"
