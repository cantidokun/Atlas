"""A-REF staged live driver — deterministic tests (no Blender required).

These tests exercise the CONTROLLER-side contract: marker parsing and transport classification,
handoff validation, controller binding verification (including every withholding tamper mode),
launch-withholding behavior with a faked launcher, and the two implementation-review findings.
Live pure/live parity is the live gate's job (test_aref_live_conformance.py).
"""

import json

import pytest

from tests.aref.aref_evidence import classify_outcome, outcome_normal_form
from tests.aref.aref_fixture import AUTH_GATED_OPS, FixtureError, validate_authorization_fixture
from tests.aref.aref_live_common import (EXEC_BEGIN, EXEC_END, LiveError, PROBE_BEGIN, PROBE_END,
                                         artifact, build_handoff, canonical_digest,
                                         fixture_spec_sha256, load_case_live, parse_marker,
                                         validate_handoff)
from tests.aref.aref_live_driver import (BindingMismatch, TransportFailure, run_live_case,
                                         verify_probe, _launch)
from tests.aref.aref_plan import (canonical_plan_bytes, plan_artifact_digest, plan_identity,
                                  raw_to_plan)
from tests.aref.aref_pure import (build_graph, fresh_graph, make_pure_extractor,
                                  make_pure_mutator)
from tests.aref.aref_witness import WitnessChannel
from tests.aref.fixtures import load_case

FIXTURE = "AREF-TEST-FX-C1-PAIR"


# ---------------------------------------------------------------------------------------------
# Marker transport (R4F 24 step 11)
# ---------------------------------------------------------------------------------------------

def test_marker_roundtrip_and_body_merge():
    record = artifact("AREF-LIVE-PROBE", {"status": "PROBED", "stage": "PROBE", "x": 1})
    stdout = f"noise\n{PROBE_BEGIN}\n{json.dumps(record)}\n{PROBE_END}\ntail\n"
    parsed = parse_marker(stdout, PROBE_BEGIN, PROBE_END)
    assert parsed["status"] == "PROBED" and parsed["x"] == 1
    assert parsed["artifact_sha256"] == record["artifact_sha256"]


def test_missing_marker_is_transport_failure():
    with pytest.raises(LiveError) as exc:
        parse_marker("no marker here", PROBE_BEGIN, PROBE_END)
    assert exc.value.category == "TRANSPORT-FAILURE"


def test_malformed_marker_json_is_malformed_evidence():
    stdout = f"{EXEC_BEGIN}\n{{not json\n{EXEC_END}\n"
    with pytest.raises(LiveError) as exc:
        parse_marker(stdout, EXEC_BEGIN, EXEC_END)
    assert exc.value.category == "MALFORMED-EVIDENCE"


def test_marker_without_status_is_malformed():
    stdout = f"{PROBE_BEGIN}\n{{\"stage\": \"PROBE\"}}\n{PROBE_END}\n"
    with pytest.raises(LiveError) as exc:
        parse_marker(stdout, PROBE_BEGIN, PROBE_END)
    assert exc.value.category == "MALFORMED-EVIDENCE"


# ---------------------------------------------------------------------------------------------
# Handoff validation (execution stage inputs)
# ---------------------------------------------------------------------------------------------

def _good_handoff():
    return build_handoff(
        fixture_id=FIXTURE, case="C1", operation="REMOVE_DUPLICATE_FACE",
        spec_digest=fixture_spec_sha256(FIXTURE), expected_sha256="a" * 64,
        plan_sha256="b" * 64, plan_path="x.json", declared_pre_digest="c" * 64,
        declared_report_digest="d" * 64, declared_plan_id="e" * 64,
        declared_correction_ids=["f" * 8], probe_artifact_sha256="1" * 64,
        probe_record_path="probe.json")


def test_handoff_valid_and_tamper_matrix():
    validate_handoff(_good_handoff())
    for drop in ("spec_digest", "plan_sha256", "declared_plan_id"):
        broken = _good_handoff()
        broken.pop(drop)
        with pytest.raises(LiveError) as exc:
            validate_handoff(broken)
        assert exc.value.category in ("MALFORMED-EVIDENCE",)
    wrong_version = dict(_good_handoff(), handoff_version="nope")
    with pytest.raises(LiveError, match="version/stage"):
        validate_handoff(wrong_version)
    unverified = dict(_good_handoff(), controller_verified=False)
    with pytest.raises(LiveError) as exc:
        validate_handoff(unverified)
    assert exc.value.category == "FIXTURE-BINDING-MISMATCH"
    short_digest = dict(_good_handoff(), plan_sha256="abc")
    with pytest.raises(LiveError, match="64-hex"):
        validate_handoff(short_digest)
    empty_ids = dict(_good_handoff(), declared_correction_ids=[])
    with pytest.raises(LiveError, match="correction_ids"):
        validate_handoff(empty_ids)


# ---------------------------------------------------------------------------------------------
# Controller binding verification (step 6) — synthetic probe record derived from the pure path
# ---------------------------------------------------------------------------------------------

def _synthetic_probe_record(fixture_id=FIXTURE):
    spec = load_case_live(fixture_id)
    graph = build_graph(spec)
    scene, report = make_pure_extractor(spec)(graph)
    from planning.blender.kernel import scene_input_digest

    declared_plan = spec.expected["plan"]
    raw_text = canonical_plan_bytes(json.loads(
        (json.dumps(_declared_raw(fixture_id))).encode())).decode()
    return {
        "status": "PROBED", "stage": "PROBE", "fixture_id": fixture_id,
        "spec_digest": fixture_spec_sha256(fixture_id),
        "expected_sha256": canonical_digest(spec.expected),
        "construct": {"objects": spec.expected["graph_witness"]["objects"],
                      "shared": spec.expected["graph_witness"]["shared"],
                      "material_slots": spec.expected["graph_witness"].get("material_slots", []),
                      "order": spec.expected["graph_witness"]["order"]},
        "pre": {"live_scene_digest": spec.expected["pre_digest"],
                "live_report_digest": declared_plan["source_report_digest"]},
        "plan": {"sha256": declared_plan["artifact_sha256"], "plan_id": declared_plan["plan_id"],
                 "source_report_digest": declared_plan["source_report_digest"],
                 "correction_ids": declared_plan["correction_ids"], "raw": raw_text},
    }


def _declared_raw(fixture_id=FIXTURE):
    from pathlib import Path
    path = Path(__file__).resolve().parent / "plan_artifacts" / f"{fixture_id}.plan.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_controller_verification_accepts_a_faithful_record():
    record = _synthetic_probe_record()
    verification = verify_probe(FIXTURE, record)
    assert verification["plan_identity_ok"] and verification["pure_eq_live"]


@pytest.mark.parametrize("tamper", ["WRONG_ARTIFACT_SHA", "WRONG_PLAN_ID", "WRONG_SOURCE_DIGEST"])
def test_controller_verification_withholds_on_tampered_plan_identity(tamper):
    with pytest.raises(BindingMismatch):
        verify_probe(FIXTURE, _synthetic_probe_record(), tamper=tamper)


def test_controller_verification_withholds_on_truncated_evidence():
    with pytest.raises(BindingMismatch):
        verify_probe(FIXTURE, _synthetic_probe_record(), tamper="TRUNCATED_EVIDENCE")


def test_controller_verification_withholds_on_stale_spec_digest():
    record = dict(_synthetic_probe_record(), spec_digest="0" * 64)
    with pytest.raises(BindingMismatch, match="spec digest"):
        verify_probe(FIXTURE, record)


def test_controller_verification_withholds_on_wrong_pure_or_live_digest():
    record = _synthetic_probe_record()
    record["pre"] = dict(record["pre"], live_scene_digest="0" * 64)
    with pytest.raises(BindingMismatch, match="EV-PRE live scene digest"):
        verify_probe(FIXTURE, record)


# ---------------------------------------------------------------------------------------------
# Withholding behavior: a failed verification must never reach an execution launch
# ---------------------------------------------------------------------------------------------

def test_failed_verification_withholds_the_execution_launch(monkeypatch):
    launches = []

    def fake_probe_launch(mode, arg, timeout=300):
        launches.append(mode)
        if mode == "probe":
            record = artifact("AREF-LIVE-PROBE", dict(_synthetic_probe_record(),
                                                      plan=dict(_synthetic_probe_record()["plan"],
                                                                plan_id="0" * 64)))
            return 0, parse_marker(f"{PROBE_BEGIN}\n{json.dumps(record)}\n{PROBE_END}\n",
                                   PROBE_BEGIN, PROBE_END), ""
        raise AssertionError("the execution launch must never happen after a failed verification")

    monkeypatch.setattr("tests.aref.aref_live_driver._launch", fake_probe_launch)
    result = run_live_case(FIXTURE, save_evidence=False)
    assert result["execution_launched"] is False
    assert launches == ["probe"]
    assert result["controller_verification"]["status"] == "WITHHELD"
    assert result["controller_verification"]["category"] == "FIXTURE-BINDING-MISMATCH"
    assert result["outcome"]["executor_invocations"] == 0


def test_transport_failure_is_environment_limited(monkeypatch):
    def broken_launch(mode, arg, timeout=300):
        raise TransportFailure(f"stage {mode} produced no parseable evidence")

    monkeypatch.setattr("tests.aref.aref_live_driver._launch", broken_launch)
    result = run_live_case(FIXTURE, save_evidence=False)
    assert result["execution_launched"] is False
    assert result["outcome"]["disposition"] == "ENVIRONMENT_LIMITED"


# ---------------------------------------------------------------------------------------------
# Implementation-review findings (Slice 1 r2-m1/m2)
# ---------------------------------------------------------------------------------------------

def test_case_requires_auth_enforces_the_gated_operation_invariant():
    auth = {"authorization_version": "1", "authorization_policy_version": "1",
            "decision": "APPROVED", "correction_type": "REPAIR_FACE_WINDING",
            "correction_id": "mesh.duplicate_face-atlas-target-01234567",
            "plan_id": "a" * 64, "source_report_digest": "b" * 64,
            "authorized_by": "AREF-TEST-fixture", "authorized_at_utc": "2026-10-08T00:00:00Z"}
    # gated operation: accepted; null: accepted (the AUTHORIZATION_REQUIRED negative)
    assert validate_authorization_fixture(auth, case_requires_auth=True) is not None
    assert validate_authorization_fixture(None, case_requires_auth=True) is None
    # non-gated operation declaring an authorization artifact: refused
    with pytest.raises(FixtureError, match="non-authorization-gated"):
        validate_authorization_fixture(auth, case_requires_auth=False)
    assert validate_authorization_fixture(None, case_requires_auth=False) is None
    assert AUTH_GATED_OPS == frozenset({"REPAIR_FACE_WINDING", "REPAIR_MERGE_VERTEX"})


def test_merge_mirror_coerces_faces_exactly_like_the_live_rebuild():
    """r2-m1: the mirror applies live's int() coercion and invents no extra validation."""
    from tests.aref.aref_pure import make_pure_mutator

    spec = load_case("AREF-TEST-FX-C1-PAIR")
    graph = build_graph(spec)
    graph.datablocks["DB1"].faces = [[4, 5, 6], [0, 1, 2], [4, 5, 6]]
    mutator = make_pure_mutator("REPAIR_MERGE_VERTEX")
    mutator(graph, object_id="atlas-target", mesh_id="atlas-target",
            vertices=[[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]], faces=[[0, 1, 0]], old_to_new_mapping=[0, 1])
    # int() coercion applied exactly as the live _same_datablock_rebuild does
    assert graph.datablocks["DB1"].faces == [[0, 1, 0]]
    assert graph.datablocks["DB1"].vertices == [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]]


def test_executor_refuses_bool_indices_in_a_merge_plan_before_invocation():
    """Exact-int vs bool validation lives in the shared EXECUTOR (which both paths reuse).

    A merge plan whose survivor table carries a BOOLEAN is not a legal exact-int table: the
    mutation of the declared merge artifact is a binding-negative on purpose, and the executor
    must refuse it (or the binding must fail) WITHOUT any invocation.
    """
    import copy

    from tests.aref.aref_harness import load_plan_artifact

    from planning.blender.correction_executor import execute_merge_vertex

    spec = load_case("AREF-TEST-FX-C4-MERGE")
    raw = copy.deepcopy(load_plan_artifact("AREF-TEST-FX-C4-MERGE"))
    params = raw["corrections"][0]["parameters"]
    assert "survivor_indices" in params, "merge plan parameter shape changed"
    params["survivor_indices"] = [True]          # a BOOLEAN is not an exact int
    raw["corrections"][0]["correction_id"] = ""  # let the contract re-commit the tampered body
    raw["plan_id"] = ""                          # ... and re-commit the plan over it
    plan = raw_to_plan(raw)

    # invoke the EXISTING executor directly (the fixture binding gate is deliberately bypassed: this
    # test is about the executor's own exact-int validation, which both paths share)
    invocations = []
    inner = make_pure_mutator(spec.operation)

    def recording(engine_state, **kwargs):
        invocations.append(kwargs)
        return inner(engine_state, **kwargs)

    receipt = execute_merge_vertex(engine_state=fresh_graph(spec), plan=plan,
                                   authorization=spec.authorization_fixture, mutator=recording,
                                   extractor=make_pure_extractor(spec))
    assert invocations == [], receipt
    assert receipt["result"] in ("PLAN_INVALID", "PRECONDITION_FAILED", "SOURCE_MISMATCH"), receipt
    assert receipt["failure_code"], receipt


def test_controller_verification_withholds_on_wrong_pure_report_digest():
    """M1: the PURE report digest is bound too (not only the live one)."""
    record = _synthetic_probe_record()
    pure = {"scene_digest": record["pre"]["live_scene_digest"], "report_digest": "0" * 64,
            "plan_id": record["plan"]["plan_id"]}
    with pytest.raises(BindingMismatch, match="pure pre-report digest != declared"):
        verify_probe(FIXTURE, record, pure)


def test_controller_verification_withholds_on_wrong_pure_report_vs_live():
    record = _synthetic_probe_record()
    pure = {"scene_digest": record["pre"]["live_scene_digest"],
            "report_digest": record["pre"]["live_report_digest"], "plan_id": record["plan"]["plan_id"]}
    # a faithful pure record passes both new checks
    verify_probe(FIXTURE, record, pure)
    record2 = _synthetic_probe_record()
    record2["pre"] = dict(record2["pre"], live_report_digest="a" * 64)
    with pytest.raises(BindingMismatch):
        verify_probe(FIXTURE, record2, pure)


def test_controller_verification_withholds_on_wrong_pure_plan_identity():
    """M1: the pure run's plan identity must equal the declared literal as well."""
    record = _synthetic_probe_record()
    pure = {"scene_digest": record["pre"]["live_scene_digest"],
            "report_digest": record["pre"]["live_report_digest"], "plan_id": "0" * 64}
    with pytest.raises(BindingMismatch, match="pure plan identity"):
        verify_probe(FIXTURE, record, pure)


def test_graph_witness_pure_eq_live_is_a_real_dimension():
    """M2: the pure witness is compared DIRECTLY to the live pre-mutation witness."""
    from tests.aref.aref_live_driver import compare_live, pure_graph_witness

    spec = load_case(FIXTURE)
    from tests.aref.aref_harness import load_plan_artifact, run_pure_case

    run = run_pure_case(spec, load_plan_artifact(FIXTURE))
    live_evidence = {"normal_form": dict(run.normal_form),
                     "child_digest": run.scene_digest_child,
                     "witness": [dict(ev, side="live") for ev in run.witness.trace()]}
    exec_raw = {"recheck": {"construct_assertions_passed": ["witness:objects"]},
                "child": {"graph_unchanged": True}}
    construct = pure_graph_witness(FIXTURE)
    ok = compare_live(run, live_evidence, exec_raw, probe_construct=construct, fixture_id=FIXTURE)
    assert ok.dimensions["graph_witness_pure_eq_live"] is True
    assert ok.verdict == "PARITY"
    tampered = dict(construct, order=["zzz"])
    bad = compare_live(run, live_evidence, exec_raw, probe_construct=tampered, fixture_id=FIXTURE)
    assert bad.dimensions["graph_witness_pure_eq_live"] is False
    assert bad.verdict == "DIVERGENCE"


def test_probe_record_verification_rejects_stale_or_wrong_artifacts(tmp_path):
    """M-d: the execution stage verifies the controller-verified probe artifact itself."""
    from tests.aref.aref_live_common import verify_probe_record_file

    record = _synthetic_probe_record()
    body = dict(record)
    body["artifact_sha256"] = canonical_digest({k: v for k, v in record.items()
                                                if k != "artifact_sha256"})
    path = tmp_path / "probe_artifact.json"
    path.write_text(json.dumps(body, sort_keys=True), encoding="utf-8")
    verify_probe_record_file(str(path), body["artifact_sha256"], FIXTURE)  # faithful: accepted
    with pytest.raises(LiveError) as exc:
        verify_probe_record_file(str(path), "0" * 64, FIXTURE)
    assert exc.value.category == "FIXTURE-BINDING-MISMATCH"
    with pytest.raises(LiveError):
        verify_probe_record_file(str(path), body["artifact_sha256"], "AREF-TEST-FX-OTHER")
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(LiveError) as exc2:
        verify_probe_record_file(str(path), body["artifact_sha256"], FIXTURE)
    assert exc2.value.category == "MALFORMED-EVIDENCE"


def test_execution_stage_verifies_the_probe_artifact_before_the_executor():
    """The execution launch's probe-artifact verification is a real, ordered CALL SITE.

    Headless-safe proof: the stage module cannot be imported outside Blender, so the call site is
    asserted against the source text — it must invoke the SAME verifier the deterministic test
    exercises, with the handoff's recorded path and digest, and it must appear BEFORE the
    _run_executor call. The dynamic behaviour is proven live by the TAMPERED_PROBE_ARTIFACT
    negative in the gated conformance suite.
    """
    from pathlib import Path as _Path

    from tests.aref.aref_live_common import verify_probe_record_file  # the exercised verifier

    source = (_Path(__file__).resolve().parent / "aref_live_execute.py").read_text(encoding="utf-8")
    lines = source.splitlines()
    occurrence = source.count("verify_probe_record_file(handoff[")
    assert occurrence == 1, (
        f"expected exactly ONE execution-side probe-artifact call, found {occurrence}")
    call_index = next((i for i, line in enumerate(lines)
                       if "verify_probe_record_file(handoff[" in line), None)
    assert call_index is not None, "the execution stage no longer verifies the probe artifact"
    assert lines[call_index].strip().startswith("verify_probe_record_file("), (
        "the probe-artifact verification must be a live call statement, not a comment or a copy")
    assert 'handoff["probe_record_path"]' in lines[call_index]
    assert 'handoff["probe_artifact_sha256"]' in lines[call_index]
    executor_index = next(i for i, line in enumerate(lines) if "_run_executor(plan, request)" in line)
    assert call_index < executor_index, "the probe-artifact check must precede the executor call"
    assert callable(verify_probe_record_file)
