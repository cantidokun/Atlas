"""A-REF harness binding-gate, witness-channel, and evidence tests (R4F 10.6, 24; negative probes)."""

import copy

import pytest

from tests.aref.aref_evidence import (EvidenceError, classify_outcome, compare_normal_forms,
                                      evidence_artifact, outcome_normal_form)
from tests.aref.aref_harness import (BindingError, compare_runs, load_plan_artifact,
                                  run_pure_case)
from tests.aref.aref_pure import EnvelopeRefusal, fresh_graph
from tests.aref.aref_witness import WitnessChannel
from tests.aref.fixtures import load_case


def _run(fixture_id):
    spec = load_case(fixture_id)
    raw = load_plan_artifact(fixture_id)
    return spec, raw, run_pure_case(spec, raw)


# --- binding gate: fail closed BEFORE mutation -------------------------------------------------

def test_tampered_pre_digest_fails_closed_without_mutation(monkeypatch):
    """Gate ORDER proof: with the executor entry replaced by a tripwire, the binding raises first."""
    import tests.aref.aref_harness as H

    spec, raw, _ = _run("AREF-TEST-FX-C1-PAIR")
    called = []

    def tripwire(**kwargs):
        called.append(kwargs)
        raise AssertionError("executor must never be reached with a failed binding")

    monkeypatch.setitem(H.EXECUTORS, spec.operation, tripwire)
    bad = copy.deepcopy(spec)
    bad.expected["pre_digest"] = "0" * 64
    with pytest.raises(BindingError, match="pre-state digest"):
        run_pure_case(bad, raw)
    assert called == []                      # the executor was NEVER invoked
    # and the pristine spec still runs through the same instrumented entry point
    with pytest.raises(AssertionError, match="must never be reached"):
        run_pure_case(spec, raw)
    assert len(called) == 1                  # reachability of the tripwire itself is demonstrated


def test_tampered_plan_digest_fails_closed_before_invocation():
    spec, raw, _ = _run("AREF-TEST-FX-C1-PAIR")
    bad = copy.deepcopy(spec)
    bad.expected["plan"]["artifact_sha256"] = "f" * 64
    with pytest.raises(BindingError, match="plan artifact digest"):
        run_pure_case(bad, raw)


def test_tampered_witness_fails_closed():
    spec, raw, _ = _run("AREF-TEST-FX-AL-C1")
    bad = copy.deepcopy(spec)
    bad.expected["graph_witness"]["shared"] = {"atlas-target": ["atlas-target"]}
    with pytest.raises(BindingError, match="graph witness"):
        run_pure_case(bad, raw)


# --- witness channel classification ------------------------------------------------------------

def test_witness_classifies_envelope_refusal():
    ch = WitnessChannel()

    def boom():
        raise EnvelopeRefusal("RC-EXACT-INDEX", "test")

    wrapped = ch.wrap("pure", "mutator", boom)
    with pytest.raises(EnvelopeRefusal):
        wrapped()
    assert ch.envelope_refusal_classes("pure") == ["ENVELOPE_REFUSAL"]
    assert not ch.has_unexpected_fault("pure")


def test_witness_classifies_unexpected_fault():
    ch = WitnessChannel()

    def boom():
        raise RuntimeError("harness bug")

    with pytest.raises(RuntimeError):
        ch.wrap("pure", "extractor", boom)()
    assert ch.has_unexpected_fault("pure")
    assert ch.envelope_refusal_classes("pure") == []


def test_witness_pre_event_carries_serialized_arguments_digest():
    ch = WitnessChannel()

    def seam(**kwargs):
        return kwargs

    ch.wrap("pure", "mutator", seam)(selected_face_index=2, expected_face_tuple=(4, 5, 6))
    pre = ch.events[0]
    assert pre.kind == "pre" and pre.args_digest is not None and len(pre.args_digest) == 64
    # the digest is argument-sensitive: a different selection changes it
    ch2 = WitnessChannel()
    ch2.wrap("pure", "mutator", seam)(selected_face_index=3, expected_face_tuple=(4, 5, 6))
    assert ch2.events[0].args_digest != pre.args_digest
    # and the raise/return event carries the SAME pre-invocation digest
    assert ch.events[1].args_digest == pre.args_digest


def test_witness_raise_event_carries_qualified_name_and_message():
    ch = WitnessChannel()

    def boom():
        raise EnvelopeRefusal("RC-TUPLE-MISMATCH", "faces[2] != expected")

    with pytest.raises(EnvelopeRefusal):
        ch.wrap("pure", "mutator", boom)()
    raise_ev = ch.raises("pure", "mutator")[0]
    assert raise_ev.exception_type == "EnvelopeRefusal"
    assert raise_ev.exception_qualified == "tests.aref.aref_pure.EnvelopeRefusal"
    assert raise_ev.exception_message == "RC-TUPLE-MISMATCH: faces[2] != expected"


def test_witness_material_slots_dimension_is_real_and_compared():
    ch = WitnessChannel()
    spec = load_case("AREF-TEST-FX-C1-PAIR")
    from tests.aref.aref_harness import check_graph_witness, graph_witness
    from tests.aref.aref_pure import fresh_graph

    graph = fresh_graph(spec)
    w = graph_witness(graph)
    assert w["material_slots"] == []            # no slots declared by this fixture
    check_graph_witness(spec, w)                # declared dimension participates in the binding
    import copy as _copy
    bad = _copy.deepcopy(spec)
    bad.expected["graph_witness"] = dict(bad.expected["graph_witness"], material_slots=[["OBJECT", "slotx"]])
    with pytest.raises(BindingError, match="material_slots"):
        check_graph_witness(bad, w)


def test_evidence_carries_field_binding_class_map():
    """A REAL run's evidence carries the closed map, and the artifact digest verifies."""
    from tests.aref.aref_evidence import canonical_bytes
    from tests.aref.aref_fixture import FIELD_BINDING_CLASSES

    spec, raw, run = _run("AREF-TEST-FX-C1-PAIR")
    cpf = run.evidence["body"]["field_binding"]["class_per_field"]
    assert cpf == FIELD_BINDING_CLASSES
    assert run.evidence["body"]["plan_artifact"]["digest_binding_ok"] is True
    import hashlib
    recomputed = hashlib.sha256(canonical_bytes(run.evidence["body"])).hexdigest()
    assert recomputed == run.evidence["artifact_sha256"]


def test_marker_refusal_holds_at_the_runner_not_only_the_loader():
    """m1: a spec mutated AFTER load (marker stripped) must still fail closed in run_pure_case."""
    from tests.aref.aref_fixture import FixtureError

    spec, raw, _ = _run("AREF-TEST-FX-C3-POS")
    bad = copy.deepcopy(spec)
    bad.authorization_fixture = dict(bad.authorization_fixture, authorized_by="operator")
    with pytest.raises(FixtureError, match="AREF-TEST-"):
        run_pure_case(bad, raw)


def test_witness_live_bridge_runtime_error_is_envelope_refusal():
    ch = WitnessChannel()

    class BridgeRuntimeError(Exception):  # name-matched to the production refusal type
        pass

    def boom():
        raise BridgeRuntimeError("same-datablock rebuild refused")

    with pytest.raises(BridgeRuntimeError):
        ch.wrap("live", "mutator", boom)()
    assert not ch.has_unexpected_fault("live")
    assert ch.envelope_refusal_classes("live") == ["ENVELOPE_REFUSAL"]


# --- outcome classification and normal form ----------------------------------------------------

def test_oc7_dominates_even_with_matching_code():
    ch = WitnessChannel()

    def boom():
        raise RuntimeError("pure seam defect")

    with pytest.raises(RuntimeError):
        ch.wrap("pure", "mutator", boom)()
    oc = classify_outcome({"result": "MUTATION_FAILED", "failure_code": "MUTATION_FAILED"},
                          invocation_count=1, witness=ch, side="pure")
    assert oc == "OC7"  # infrastructure evidence, never parity (R4F 10.4g)


def test_oc1_requires_zero_invocations():
    ch = WitnessChannel()
    oc = classify_outcome({"result": "PLAN_INVALID", "failure_code": "AMBIGUOUS_MULTIPLE_EXECUTABLE_CORRECTIONS"},
                          invocation_count=0, witness=ch, side="pure")
    assert oc == "OC1"
    with pytest.raises(EvidenceError):
        classify_outcome({"result": "PLAN_INVALID", "failure_code": "AMBIGUOUS_MULTIPLE_EXECUTABLE_CORRECTIONS"},
                         invocation_count=1, witness=ch, side="pure")


def test_oc6_new_invalid_index_branch():
    ch = WitnessChannel()
    oc = classify_outcome({"result": "POSTCONDITION_FAILED", "failure_code": "NEW_INVALID_INDEX"},
                          invocation_count=1, witness=ch, side="pure")
    assert oc == "OC6"


def test_normal_form_fields():
    ch = WitnessChannel()
    nf = outcome_normal_form({"result": "POSTCONDITION_FAILED", "failure_code": "POSTCONDITION_FAILED",
                              "postcondition_results": [{"ok": False, "reason": "unrelated"}]},
                             invocation_count=1, witness=ch, side="pure")
    assert nf["oc_class"] == "OC5"
    assert nf["phase"] == "POST"
    assert nf["postcondition_results"] == [{"ok": False, "reason": "unrelated"}]


def test_comparator_divergence_and_parity():
    ch = WitnessChannel()
    nf_ok = {"oc_class": "OC2", "executor_outcome": "COMPLETED", "failure_code": None,
             "phase": "POST", "invocation_count": 1}
    nf_bad = dict(nf_ok, failure_code="POSTCONDITION_FAILED")
    assert compare_normal_forms(nf_ok, dict(nf_ok)).verdict == "PARITY"
    assert compare_normal_forms(nf_ok, nf_bad).verdict == "DIVERGENCE"


def test_evidence_artifact_is_digest_pinned():
    art = evidence_artifact({"case": "C1", "n": 1})
    art2 = evidence_artifact({"case": "C1", "n": 1})
    assert art["artifact_sha256"] == art2["artifact_sha256"]
    assert art["authority"] == "none"


def test_oc4_extraction_pairs_are_classified_oc4():
    """M1: the OC4 pairs are the executor's real tokens, with stage-consistent invocation counts."""
    ch = WitnessChannel()
    assert classify_outcome({"result": "SOURCE_MISMATCH", "failure_code": "EXTRACTION_FAILED"},
                            invocation_count=0, witness=ch, side="pure") == "OC4"
    assert classify_outcome({"result": "MUTATION_FAILED", "failure_code": "POST_EXTRACTION_FAILED"},
                            invocation_count=1, witness=ch, side="pure") == "OC4"
    # stage invariants: the extraction pair cannot follow an invocation; the post-extraction pair
    # cannot precede one
    with pytest.raises(EvidenceError):
        classify_outcome({"result": "SOURCE_MISMATCH", "failure_code": "EXTRACTION_FAILED"},
                         invocation_count=1, witness=ch, side="pure")
    with pytest.raises(EvidenceError):
        classify_outcome({"result": "MUTATION_FAILED", "failure_code": "POST_EXTRACTION_FAILED"},
                         invocation_count=0, witness=ch, side="pure")


def test_source_digest_mismatch_stays_oc1_and_wave2_tokens_classify():
    ch = WitnessChannel()
    assert classify_outcome({"result": "SOURCE_MISMATCH", "failure_code": "SOURCE_DIGEST_MISMATCH"},
                            invocation_count=0, witness=ch, side="pure") == "OC1"
    assert classify_outcome({"result": "AUTHORIZATION_SCOPE_MISMATCH",
                             "failure_code": "AUTHORIZATION_SCOPE_MISMATCH"},
                            invocation_count=0, witness=ch, side="pure") == "OC1"
    with pytest.raises(EvidenceError, match="PARTIAL_FAILURE"):
        classify_outcome({"result": "PARTIAL_FAILURE", "failure_code": "PARTIAL_FAILURE"},
                         invocation_count=0, witness=ch, side="pure")


def test_compare_runs_activates_the_witness_dimension():
    """m4: compare_runs must carry the witness-class comparison, not leave it inert."""
    spec, raw, run = _run("AREF-TEST-FX-MM-C1")
    # a live record's trace carries side="live" events; mirror the same refusal shape
    live_trace = [dict(ev, side="live") for ev in run.witness.trace()]
    live_ok = {"normal_form": dict(run.normal_form),
               "child_digest": run.scene_digest_child,
               "witness": live_trace}
    assert compare_runs(run, live_ok).verdict == "PARITY"
    live_bad = dict(live_ok, witness=[])       # live record with NO refusal witness
    result = compare_runs(run, live_bad)
    assert result.verdict == "DIVERGENCE"
    assert result.dimensions["witness_classes_match"] is False
