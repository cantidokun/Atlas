"""M12.6 R2-A refusal-only machinery tests (normative input: ATLAS_M12_6_R1_NORMATIVE_DESIGN_REV18.md).

Every test exercises the implementation path (resolver/verifier/classifier), not disconnected constants.
"""

import copy
import sys


def _INT_DIGIT_LIMIT():
    """The declared integer-to-decimal bound of the running interpreter (XI.3); 0 when it has none."""
    return getattr(sys, "get_int_max_str_digits", lambda: 0)()
from dataclasses import replace

import contextlib


class _Raises:
    """Minimal ``raises`` context manager so the suite runs under the pinned CPython 3.11.16 runtime."""

    def __init__(self, expected):
        self.expected = expected

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            raise AssertionError(f"expected {self.expected.__name__} to be raised")
        return issubclass(exc_type, self.expected)


def raises(expected):
    return _Raises(expected)

from planning.m12 import DEFAULT_UNREAL_CATALOG, generate_execution_plan
from planning.m12 import expectation as ex


def _task_and_plan(task_name="unreal.sequence-configure", **overrides):
    parameters = {"twin_id": "twin-1", "sequence_name": "main", "frame_start": 1, "frame_end": 24}
    parameters.update(overrides)
    task = DEFAULT_UNREAL_CATALOG.resolve(task_name, parameters, digital_twin_id="twin-1")
    return task, generate_execution_plan(task)


def _task_for(entry_name, **overrides):
    """Build a validated task for any declared entry, using the entry's own parameter kinds."""
    entry = next(e for e in ex.EXPECTATION_VOCABULARY if e.entry_name == entry_name)
    kinds = dict(entry.parameter_kinds)
    parameters = {}
    for name in entry.parameter_names:
        kind = kinds[name]
        parameters[name] = {"string": "twin-1", "int": 1, "json": {}}[kind]
    parameters.update(overrides)
    task = DEFAULT_UNREAL_CATALOG.resolve(entry_name, parameters, digital_twin_id="twin-1")
    return task, generate_execution_plan(task)


def _schema_valid_expectation(task, plan, **changes):
    """A structurally valid supplied expectation (schema-valid, no null target member)."""
    claim = {
        "expectation_contract_revision": ex.EXPECTATION_CONTRACT_REVISION,
        "resolver_revision": ex.RESOLVER_REVISION,
        "registry_revision": ex.REGISTRY_REVISION,
        "registry_digest": ex.REGISTRY_SOURCE_DIGEST,
        "target_table_revision": ex.TARGET_TABLE_REVISION,
        "target_table_digest": ex.TARGET_TABLE_DIGEST,
        "production_target_id": "target-1",
        "target_revision": 1,
        "target_digest": "b" * 64,
        "task_identity": task.canonical_task_id,
        "task_version": task.task_version,
        "digital_twin_id": task.digital_twin_id,
        "catalog_entry_name": task.canonical_task_id,
        "catalog_entry_version": task.task_version,
        "vocabulary_digest": "c" * 64,
        "source_content_digest": plan.source_content_digest,
        "plan_id": plan.plan_id,
        "plan_content_digest": ex.compute_plan_content_digest(plan),
        "render_task": False,
        "required_invariant_names": sorted(task.target_state.to_invariant_names()),
        "invariant_expectations": [{"invariant_name": n} for n in sorted(task.target_state.to_invariant_names())],
        "origin_status": ex.ORIGIN_STATUS,
        "expectation_digest": "d" * 64,
    }
    claim.update(changes)
    if "expectation_digest" not in changes:
        claim["expectation_digest"] = ex.compute_expectation_digest(claim)
    return claim


# ------------------------------------------------------------------ the R2-A authoritative S4 result

def test_r2a_authoritative_s4_result_is_fixed_member_by_member():
    task, plan = _task_and_plan()
    result = ex.verify_semantic_target_r2a(task, plan)
    m = result.members
    assert m["deciding_stage"] == "S4"
    assert m["primary_failure_code"] == "EXPECTED_VALUE_UNAVAILABLE"
    assert m["outcome_reason_class"] == "AUTHORITY_ABSENT"
    assert m["failure_codes"] == ("EXPECTED_VALUE_UNAVAILABLE", "PRODUCTION_TARGET_NOT_ESTABLISHED")
    assert m["semantic_state"] == "NOT_ESTABLISHED"
    assert m["overall_state"] == "NOT_ESTABLISHED"
    assert m["render_state"] == "NOT_REQUIRED"
    assert (m["production_target_id"], m["target_revision"], m["target_digest"]) == (None, None, None)
    assert m["target_table_digest"] == ex.TARGET_TABLE_DIGEST
    assert m["registry_digest"] == ex.REGISTRY_SOURCE_DIGEST
    assert m["expectation_identity"] is None and m["expectation_digest"] is None
    assert m["observation_identity"] is None and m["observation_digests"] == ()
    assert m["evidence_trust_basis"] == {
        "semantic_observation": "NOT_ESTABLISHED", "render_evidence": "NOT_APPLICABLE"}
    assert m["origin_status"] == "NOT_ESTABLISHED"
    assert all(e.invariant_state == "UNKNOWN" for e in m["invariant_results"])
    assert all(e.value_state == "ABSENT" and e.observation_bound is False for e in m["invariant_results"])
    assert len(m["invariant_results"]) == len(m["required_invariant_names"])


def test_row_22_is_reachable_and_aggregate_only_in_r2a():
    """V.4.9 ships the lookup against an empty reviewed table: the miss is reported, never primary in R2-A."""
    task, plan = _task_and_plan()
    resolution = ex.resolve(task, plan)
    assert 22 in resolution.applicable_rows
    assert resolution.target is None
    result = ex.verify_semantic_target_r2a(task, plan)
    assert "PRODUCTION_TARGET_NOT_ESTABLISHED" in result.members["failure_codes"]
    assert result.members["primary_failure_code"] != "PRODUCTION_TARGET_NOT_ESTABLISHED"
    assert ex.lookup_production_target(("nope", 1, "scene-prepare")) is None


def test_case_8_shape_has_no_supplied_expectation_and_entries_are_unresolved():
    """Case 8: no expectation object, non-empty required set, intact empty table, miss at S4, resolver-owned."""
    task, plan = _task_and_plan()
    resolution = ex.resolve(task, plan, None)
    assert resolution.applicable_rows & {3, 6, 22}
    result = ex.verify_semantic_target_r2a(task, plan, None)
    for entry in result.members["invariant_results"]:
        assert entry.resolved is False
        assert entry.definition_id is None and entry.expected_value_identity is None


# ------------------------------------------------------------------ the nine-case matrix (Part XX group 2)

def test_cases_2_to_6_and_9_null_target_member_is_row_5():
    task, plan = _task_and_plan()
    cases = {
        2: {"production_target_id": None},
        3: {"target_revision": None},
        4: {"target_digest": None},
        5: {"production_target_id": None, "target_revision": None, "target_digest": None},
        6: {"production_target_id": None},
        9: {"production_target_id": None},
    }
    for case, changes in cases.items():
        claim = _schema_valid_expectation(task, plan, **changes)
        classification = ex.classify_supplied_expectation(claim, task=task, plan=plan)
        assert classification.rows == frozenset({5}), case
        assert classification.target_members_null is True
        result = ex.verify_semantic_target_r2a(task, plan, claim)
        assert result.members["deciding_stage"] == "S3", case
        assert result.members["primary_failure_code"] == "EXPECTATION_INCOMPLETE", case
        assert result.members["failure_codes"] == ("EXPECTATION_INCOMPLETE",), case
        assert result.members["semantic_state"] == "NOT_ESTABLISHED", case


def test_case_relative_typing_binds_only_the_members_the_case_does_not_designate_null():
    """The case-relative rule: a non-designated member keeps its declared type; only the named defect is null."""
    task, plan = _task_and_plan()
    claim = _schema_valid_expectation(task, plan, production_target_id=None)
    classification = ex.classify_supplied_expectation(claim, task=task, plan=plan)
    assert classification.rows == frozenset({5})
    # the two non-designated members are still non-null in the supplied object (no second defect)
    assert claim["target_revision"] == 1 and claim["target_digest"] == "b" * 64


def test_case_1_and_7_schema_valid_supplied_expectation_decides_at_s3():
    task, plan = _task_and_plan()
    claim = _schema_valid_expectation(task, plan)
    classification = ex.classify_supplied_expectation(claim, task=task, plan=plan)
    assert classification.rows == frozenset({4, 7})
    result = ex.verify_semantic_target_r2a(task, plan, claim)
    assert result.members["deciding_stage"] == "S3"
    assert result.members["primary_failure_code"] == "EXPECTATION_IDENTITY_MISMATCH"
    assert result.members["failure_codes"] == ("EXPECTATION_IDENTITY_MISMATCH",)
    # no expectation identity is ever established in R2-A
    assert result.members["expectation_identity"] is None
    assert classification.admissible is False

    bad_digest = _schema_valid_expectation(task, plan, expectation_digest="e" * 64)
    result7 = ex.verify_semantic_target_r2a(task, plan, bad_digest)
    assert result7.members["deciding_stage"] == "S3"
    assert result7.members["failure_codes"] == (
        "EXPECTATION_DIGEST_MISMATCH", "EXPECTATION_IDENTITY_MISMATCH")
    assert result7.members["primary_failure_code"] == "EXPECTATION_IDENTITY_MISMATCH"


def test_supplied_expectation_never_preempts_with_a_claim_only():
    """A supplied expectation that fails S1/S3 preempts the resolver's S4 coverage refusal (XIV.7.3)."""
    task, plan = _task_and_plan()
    claim = _schema_valid_expectation(task, plan)
    assert 22 in ex.resolve(task, plan).applicable_rows
    result = ex.verify_semantic_target_r2a(task, plan, claim)
    assert result.members["deciding_stage"] == "S3"
    assert "PRODUCTION_TARGET_NOT_ESTABLISHED" not in result.members["failure_codes"]


def test_expectation_value_content_failure_is_s1_row_28():
    """XIV.5: an expectation-side float is a value-content structural failure carried by row 28 at S1."""
    task, plan = _task_and_plan()
    claim = _schema_valid_expectation(task, plan)
    claim["render_task"] = 1  # wrong type -> closed schema (row 5); replaced below by the float variant
    result_wrong_type = ex.verify_semantic_target_r2a(task, plan, claim)
    assert result_wrong_type.members["deciding_stage"] == "S3"
    assert result_wrong_type.members["primary_failure_code"] == "EXPECTATION_INCOMPLETE"

    floating = _schema_valid_expectation(task, plan)
    floating["invariant_expectations"] = [{"invariant_name": "x", "expected_value": 1.5}]
    # Domain A refuses a float, so no digest can be recomputed for this claim: the S1 preflight decides first
    with raises(Exception):
        ex.compute_expectation_digest(floating)
    result = ex.verify_semantic_target_r2a(task, plan, floating)
    assert result.members["deciding_stage"] == "S1"
    assert result.members["primary_failure_code"] == "RESOLVER_INPUT_STRUCTURE_INVALID"


def test_case_5_all_three_null_is_one_row_5_occurrence():
    task, plan = _task_and_plan()
    claim = _schema_valid_expectation(task, plan, production_target_id=None, target_revision=None, target_digest=None)
    result = ex.verify_semantic_target_r2a(task, plan, claim)
    assert result.members["deciding_stage"] == "S3"
    assert result.members["primary_failure_code"] == "EXPECTATION_INCOMPLETE"
    assert result.members["failure_codes"] == ("EXPECTATION_INCOMPLETE",)


# ------------------------------------------------------------------ resolver rows

def test_row_13_task_mismatch():
    task, plan = _task_and_plan()
    tampered = copy.deepcopy(plan)
    object.__setattr__(tampered, "source_content_digest", "0" * 64)
    result = ex.verify_semantic_target_r2a(task, tampered)
    assert result.members["primary_failure_code"] == "IDENTITY_MISMATCH"
    assert result.members["deciding_stage"] == "S3"


def test_row_29_structurally_valid_float_bearing_plan():
    task, plan = _task_and_plan()
    tampered = copy.deepcopy(plan)
    object.__setattr__(tampered, "provenance", {"float_probe": 1.5})
    result = ex.verify_semantic_target_r2a(task, tampered)
    assert result.members["deciding_stage"] == "S1"
    assert result.members["primary_failure_code"] == "PLAN_CONTENT_UNSUPPORTED"
    assert result.members["failure_codes"] == ("PLAN_CONTENT_UNSUPPORTED",)


def test_row_26_unknown_required_name_is_preserved_verbatim():
    task, plan = _task_and_plan()
    tampered = copy.deepcopy(task)
    original = tampered.target_state
    new_state = replace(original, invariant_names=frozenset(set(original.invariant_names) | {"not_a_real_invariant"}))
    object.__setattr__(tampered, "target_state", new_state)
    # the plan must be regenerated for the tampered task: a stale pair is row 13 (a lower-numbered row), which
    # would legitimately preempt the vocabulary row this test asserts
    tampered_plan = generate_execution_plan(tampered)
    result = ex.verify_semantic_target_r2a(tampered, tampered_plan)
    assert result.members["primary_failure_code"] == "EXPECTATION_VOCABULARY_MISMATCH"
    assert "not_a_real_invariant" in result.members["required_invariant_names"]
    assert any(e.invariant_name == "not_a_real_invariant" for e in result.members["invariant_results"])


def test_row_31_plan_render_classification_mismatch():
    task, plan = _task_and_plan()
    tampered = copy.deepcopy(plan)
    object.__setattr__(tampered, "render_plan", True)
    result = ex.verify_semantic_target_r2a(task, tampered)
    assert result.members["primary_failure_code"] == "PLAN_RENDER_CLASSIFICATION_MISMATCH"


def test_render_bearing_task_reports_the_v1_render_dimension():
    task, plan = _task_for("unreal.render-execute")
    result = ex.verify_semantic_target_r2a(task, plan)
    codes = result.members["failure_codes"]
    assert result.members["deciding_stage"] == "S4"
    assert "RENDER_TASK_CORRESPONDENCE_NOT_DECIDED" in codes
    assert "REQUEST_DIGEST_AGREEMENT_NOT_ESTABLISHED" in codes
    assert "SEQUENCE_AGREEMENT_NOT_ESTABLISHED" in codes
    assert "RENDER_EVIDENCE_MISSING" in codes
    assert result.members["render_state"] == "NOT_VERIFIED"


def test_empty_required_set_is_row_30_at_s3():
    task, plan = _task_and_plan()
    tampered = copy.deepcopy(task)
    object.__setattr__(tampered, "target_state", replace(task.target_state, invariant_names=frozenset()))
    tampered_plan = generate_execution_plan(tampered)   # keep the pair consistent (row 13 stays out)
    result = ex.verify_semantic_target_r2a(tampered, tampered_plan)
    assert result.members["deciding_stage"] == "S3"
    assert result.members["primary_failure_code"] == "EMPTY_REQUIRED_INVARIANT_SET"
    assert result.members["invariant_results"] == ()      # internal immutable form
    assert result.members["required_invariant_names"] == ()
    # the canonical (serialized) form is a JSON array on both paths (XIV.4.1.1 clause 1)
    assert result.canonical_dict()["invariant_results"] == []
    assert result.canonical_dict()["required_invariant_names"] == []


# ------------------------------------------------------------------ classifier, mapper, reachability

def test_part_xv_census_and_classifier_totality():
    rows, tokens = ex.row_census()
    assert (rows, tokens) == (42, 35)
    ex.assert_stage_class_homogeneity()
    for row_id, _token, stage, reason_class in ex.PART_XV_ROWS:
        assert ex.classify_failure_row(row_id) == (stage, reason_class)
        assert ex.failure_token(row_id) == _token
    for retired in (34, 35):
        with raises(ex.M126ContractError):
            ex.classify_failure_row(retired)
    with raises(ex.M126ContractError):
        ex.classify_failure_row(99)


def test_no_code_keyed_mapping_exists():
    """XIV.7.1: the classifier is row-keyed only; a code-keyed entry point must not exist."""
    source = (ex.__file__ and open(ex.__file__, encoding="utf-8").read()) or ""
    assert "def classify_failure_code" not in source
    for name in dir(ex):
        assert not name.startswith("classify_") or name in {"classify_failure_row", "classify_supplied_expectation"}


def test_within_stage_precedence_and_aggregation():
    outcome = ex.decisive_outcome([22, 32, 42, 43, 44])
    assert outcome.stage == "S4"
    assert outcome.primary_row == 22
    assert outcome.primary_code == "PRODUCTION_TARGET_NOT_ESTABLISHED"
    assert outcome.failure_codes == tuple(sorted({
        "PRODUCTION_TARGET_NOT_ESTABLISHED", "RENDER_TASK_CORRESPONDENCE_NOT_DECIDED",
        "REQUEST_DIGEST_AGREEMENT_NOT_ESTABLISHED", "SEQUENCE_AGREEMENT_NOT_ESTABLISHED",
        "RENDER_EVIDENCE_MISSING"}))

    mixed = ex.decisive_outcome([30, 4, 41])
    assert mixed.primary_row == 4
    assert mixed.failure_codes == ("EMPTY_REQUIRED_INVARIANT_SET", "EXPECTATION_IDENTITY_MISMATCH",
                                   "EXTRA_PLAN_VERIFICATION_REQUIREMENT")


def test_r2a_reachability_and_r2b_prohibition():
    task, plan = _task_and_plan()
    for claim in (None, _schema_valid_expectation(task, plan)):
        result = ex.verify_semantic_target_r2a(task, plan, claim)
        members = result.members
        assert members["semantic_state"] not in {"SATISFIED", "NOT_SATISFIED"}
        assert members["overall_state"] not in {"SATISFIED", "NOT_SATISFIED"}
        assert members["deciding_stage"] in {"S1", "S2", "S3", "S4"}
        assert members["outcome_reason_class"] not in {"SATISFIED", "EVALUATED_MISMATCH", "EVIDENCE_INSUFFICIENT"}
        assert members["render_state"] != "VERIFIED"
    # a hand-built R2-B-only member set is rejected by the same guard
    members = _result_members_for(task, plan)
    members["semantic_state"] = "SATISFIED"
    with raises(ex.M126ContractError):
        ex.M126Result(members=members)


def test_fault_result_is_not_stage_attributable():
    fault = ex.express_fault_result(fault_injected=True)
    assert fault.members["deciding_stage"] is None
    assert fault.members["outcome_reason_class"] == "INTERNAL_FAILURE"
    assert fault.members["failure_codes"] == ("RESOLVER_INTERNAL_FAILURE",)
    with raises(ex.M126ContractError):
        ex.express_fault_result()


def _result_members_for(task, plan):
    return dict(ex.verify_semantic_target_r2a(task, plan).members)


# ------------------------------------------------------------------ authority tables and isolation

def test_reviewed_authority_constants_recompute_from_the_same_objects():
    assert ex.REGISTERED_COUNT == 0
    assert ex.SEMANTIC_INVARIANT_DEFINITIONS == ()
    assert ex.PRODUCTION_TARGETS == () and ex.PRODUCTION_TARGET_BY_TASK == ()
    assert ex.registry_digest() == ex.REGISTRY_SOURCE_DIGEST
    assert ex.target_table_digest() == ex.TARGET_TABLE_DIGEST
    assert ex.revalidate_authority() is None
    # the target table digest is a Domain-A digest of the empty reviewed table
    assert ex.TARGET_TABLE_DIGEST == ex.domain_a_digest({"schema": "m12.6-target-table-v1", "targets": []})
    status = ex.production_target_status()
    assert status["table_entries"] == 0 and status["authoritative_reviewed_target_artifact"] is False


def test_authority_tables_are_immutable_and_unre_exportable():
    assert isinstance(ex.EXPECTATION_VOCABULARY, tuple)
    assert isinstance(ex.SEMANTIC_INVARIANT_DEFINITIONS, tuple)
    assert isinstance(ex.PRODUCTION_TARGETS, tuple)
    with raises(Exception):
        ex.EXPECTATION_VOCABULARY.append("x")
    with raises((TypeError, AttributeError)):
        ex.EntryVocabulary(
            entry_name="a", entry_version=1, task_class="b", fragment_ids=(), invariant_names=(),
            parameter_names=(), parameter_kinds=(),
        ).entry_name = "z"


def test_vocabulary_digest_is_the_declared_recipe():
    entry = ex.EXPECTATION_VOCABULARY[0]
    assert entry.vocabulary_digest == ex.domain_a_digest(entry.projection())
    assert entry.projection()["schema"] == "m12.6-vocabulary-entry-v1"


# ------------------------------------------------------------------ digests and determinism

def test_result_digest_is_deterministic_idempotent_and_independently_reproducible():
    task, plan = _task_and_plan()
    first = ex.verify_semantic_target_r2a(task, plan)
    second = ex.verify_semantic_target_r2a(task, plan)
    assert first.result_digest == second.result_digest
    assert first.members == second.members
    # independent recomputation through Domain A directly
    import hashlib
    from planning.unreal_state_extraction import jcs
    payload = jcs.canonicalize(first.canonical_dict()).encode("utf-8")
    assert hashlib.sha256(payload).hexdigest() == first.result_digest


def test_entry_digests_recompute_and_differ_per_required_name():
    task, plan = _task_and_plan()
    result = ex.verify_semantic_target_r2a(task, plan)
    digests = []
    for entry in result.members["invariant_results"]:
        assert ex.compute_evidence_identity(entry) == entry.evidence_identity
        assert ex.compute_invariant_result_digest(entry) == entry.invariant_result_digest
        digests.append(entry.invariant_result_digest)
    assert len(set(digests)) == len(digests)
    # preservation is observable in the digests (XIV.4.1.1 clause 5)
    tampered = copy.deepcopy(task)
    object.__setattr__(tampered, "target_state",
                       replace(task.target_state,
                               invariant_names=frozenset(set(task.target_state.invariant_names) | {"zzz"})))
    other = ex.verify_semantic_target_r2a(tampered, plan)
    assert other.result_digest != result.result_digest
    assert other.members["invariant_results"][-1].invariant_name == "zzz"


def test_plan_content_digest_is_the_single_x2_recipe():
    task, plan = _task_and_plan()
    from planning.m12.execution_plan import _canonical_sha256

    assert ex.compute_plan_content_digest(plan) == _canonical_sha256(plan.to_json_compatible(), "execution_plan")


# ------------------------------------------------------------------ preflight categories

def test_preflight_categories():
    deep = 1
    for _ in range(25):
        deep = {"n": deep}
    cases = [
        (["not", "a", "mapping"], "F1"),
        ({"a": {1, 2}}, "F4"),
        ({"a": float("nan")}, "F5"),
        (deep, "F6"),
    ]
    if _INT_DIGIT_LIMIT() == 0:
        # the declared integer-to-decimal bound is a property of the pinned runtime (XI.3): a runtime without
        # it cannot produce F8, and this test states that dependence instead of weakening the rule
        assert ex.preflight_document({"a": 2 ** 20000}) is None
    else:
        cases.append(({"a": 2 ** 20000}, "F8"))
    for document, category in cases:
        refusal = ex.preflight_document(document)
        assert refusal is not None, (document, category)
        assert refusal.category == category, (document, category, refusal.category)
    surrogate = ex.preflight_document({"a": "\ud800"})
    assert surrogate is not None and surrogate.category == "F7"


def test_preflight_passes_a_valid_document():
    assert ex.preflight_document({"a": [1, "b", None, True]}) is None
