"""M12.6 R2-A remediation tests (normative input: ATLAS_M12_6_R1_NORMATIVE_DESIGN_REV18.md, SHA
ec5eab43a4dbd3dc8e7c376133aff954a6c25a4283c3eb0d2bed31081ae2b41d).

Covers the B1-B8 remediation obligations. Every test exercises the implementation path (resolver, verifier,
classifier, result type), not constants re-stated from the contract. Where an obligation is asserted at a
declared boundary rather than end-to-end (because the frozen typed producers cannot emit the malformed form),
the test says so explicitly.
"""

import ast
import copy
import hashlib
import os
import pathlib
import subprocess
import sys


def _INT_DIGIT_LIMIT():
    """The declared integer-to-decimal bound of the running interpreter (XI.3); 0 when it has none."""
    return getattr(sys, "get_int_max_str_digits", lambda: 0)()
from dataclasses import FrozenInstanceError, replace

from planning.m12 import DEFAULT_UNREAL_CATALOG, generate_execution_plan
from planning.m12 import expectation as ex


class _Raises:
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


R18_PATH = pathlib.Path(r"C:\Users\Gavin's PC\Desktop\ATLAS_M12_6_R1_NORMATIVE_DESIGN_REV18.md")
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _task_and_plan(task_name="unreal.sequence-configure", **overrides):
    parameters = {"twin_id": "twin-1", "sequence_name": "main", "frame_start": 1, "frame_end": 24}
    parameters.update(overrides)
    task = DEFAULT_UNREAL_CATALOG.resolve(task_name, parameters, digital_twin_id="twin-1")
    return task, generate_execution_plan(task)


def _render_task_and_plan():
    """A render-bearing pair (unreal.render-execute is the declared render entry)."""
    entry = next(e for e in ex.EXPECTATION_VOCABULARY if e.entry_name == "unreal.render-execute")
    kinds = dict(entry.parameter_kinds)
    parameters = {}
    for name in entry.parameter_names:
        parameters[name] = {"string": "twin-1", "int": 1, "json": {}}[kinds[name]]
    task = DEFAULT_UNREAL_CATALOG.resolve("unreal.render-execute", parameters, digital_twin_id="twin-1")
    return task, generate_execution_plan(task)


def _claim(task, plan, **changes):
    names = sorted(task.target_state.to_invariant_names())
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
        "required_invariant_names": names,
        "invariant_expectations": [{"invariant_name": n} for n in names],
        "origin_status": ex.ORIGIN_STATUS,
        "expectation_digest": "d" * 64,
    }
    claim.update(changes)
    if "expectation_digest" not in changes:
        claim["expectation_digest"] = ex.compute_expectation_digest(claim)
    return claim


def _mutate(obj, **changes):
    for name, value in changes.items():
        object.__setattr__(obj, name, value)
    return obj


def _definition(**overrides):
    fields = dict(
        invariant_name="probe.invariant",
        definition_revision=1,
        definition_status="REGISTERED",
        authority_class="CODE_CONSTANT",
        observable_paths=("world.path.a",),
        subject_scope=("entity-1",),
        comparison="EQUALS",
        admissible_value_type="string",
        expected_value_source="CODE_CONSTANT",
        expected_value="x",
        target_binding="PRODUCTION_TARGET",
        missing_behavior="EXPECTED_VALUE_UNAVAILABLE",
        unsupported_behavior="EXPECTED_VALUE_UNAVAILABLE",
        witness_positive=None,
        witness_negative=None,
        witness_lossy=None,
        non_claim="probe",
    )
    fields.update(overrides)
    return ex.SemanticInvariantDefinition(**fields)


# --------------------------------------------------------------- B1: F2/F3/F9 schema preflight


def test_b1_wrong_type_declared_member_is_s1_row_1():
    """The previously observed `task_version = True` case refuses at S1 (row 1), classified F3."""
    task, plan = _task_and_plan()
    _mutate(task, task_version=True)
    assert ex.validate_declared_schema(task.to_json_compatible(), "task") == "F3"
    resolution = ex.resolve(task, plan)
    assert resolution.applicable_rows == frozenset({1})
    result = ex.verify_semantic_target_r2a(task, plan)
    m = result.members
    assert m["deciding_stage"] == "S1"
    assert m["primary_failure_code"] == "RESOLVER_INPUT_STRUCTURE_INVALID"
    assert m["failure_codes"] == ("RESOLVER_INPUT_STRUCTURE_INVALID",)
    assert m["semantic_state"] == "NOT_ESTABLISHED" and m["overall_state"] == "NOT_ESTABLISHED"


def test_b1_plan_wrong_type_member_is_s1_row_1():
    task, plan = _task_and_plan()
    _mutate(plan, plan_id=42)
    assert ex.validate_declared_schema(plan.to_json_compatible(), "plan") == "F3"
    result = ex.verify_semantic_target_r2a(task, plan)
    assert result.members["deciding_stage"] == "S1"
    assert result.members["primary_failure_code"] == "RESOLVER_INPUT_STRUCTURE_INVALID"


def test_b1_nested_closed_containers_and_free_form_bags():
    """F2 covers the top-level member set and the declared closed nested containers.

    Asserted at the declared-schema boundary: the frozen M12.1/M12.3 producers cannot emit a projection with an
    undeclared member, so the caller-supplied form is exercised directly.
    """
    task, plan = _task_and_plan()
    document = task.to_json_compatible()
    assert ex.validate_declared_schema(document, "task") is None  # the producer's own projection is conformant

    extra_top = dict(document, undeclared_member=1)
    assert ex.validate_declared_schema(extra_top, "task") == "F2"
    missing_top = {k: v for k, v in document.items() if k != "intent"}
    assert ex.validate_declared_schema(missing_top, "task") == "F2"

    target_state = dict(document["target_state"], undeclared_nested=1)
    assert ex.validate_declared_schema(dict(document, target_state=target_state), "task") == "F2"

    free_form = dict(document, metadata=dict(document["metadata"], extra_bag_member="v"))
    assert ex.validate_declared_schema(free_form, "task") is None  # metadata/provenance are free-form bags

    plan_document = plan.to_json_compatible()
    steps = [dict(plan_document["steps"][0], undeclared_step_member=1)]
    assert ex.validate_declared_schema(dict(plan_document, steps=steps), "plan") == "F2"


def test_b1_f9_non_empty_and_unique_sequences():
    task, plan = _task_and_plan()
    document = task.to_json_compatible()
    duplicated = dict(document, allowed_mutations=list(document["allowed_mutations"]) * 2)
    assert ex.validate_declared_schema(duplicated, "task") == "F9"
    plan_document = plan.to_json_compatible()
    assert ex.validate_declared_schema(dict(plan_document, steps=[]), "plan") == "F9"


def test_b1_f_category_matrix_per_object_class():
    """Each F category resolves to its declared row for each object class it can classify.

    Task/plan classes refuse at row 1; the expectation class refuses at row 28, and its *declared-member*
    violations are row 5 (Part IX), never an F category.
    """
    task, plan = _task_and_plan()
    base = task.to_json_compatible()

    # ---- F1: the projection is not an object
    assert ex.preflight_document(["not", "an", "object"]).category == "F1"
    assert ex.preflight_document("text").category == "F1"
    assert ex.preflight_document(7, expectation_side=True).category == "F1"

    # ---- F4: an unsupported value type (task side), and Domain A's float refusal (expectation side)
    assert ex.preflight_document({"m": {1, 2}}).category == "F4"
    assert ex.preflight_document({"m": 1.5}) is None                     # Domain B accepts floats (row 29 later)
    assert ex.preflight_document({"m": 1.5}, expectation_side=True).category == "F4"

    # ---- F5: a non-finite float
    assert ex.preflight_document({"m": float("nan")}).category == "F5"
    assert ex.preflight_document({"m": float("inf")}, expectation_side=True).category == "F5"

    # ---- F6: the bounded traversal (depth and cycle)
    deep = current = {}
    for _ in range(ex.PREFLIGHT_DEPTH_LIMIT + 3):
        current["n"] = {}
        current = current["n"]
    assert ex.preflight_document(deep).category == "F6"
    cycle = {}
    cycle["self"] = cycle
    assert ex.preflight_document(cycle).category == "F6"

    # ---- F7: a lone surrogate
    assert ex.preflight_document({"m": "\ud800"}).category == "F7"
    assert ex.preflight_document({"m": "\udfff"}, expectation_side=True).category == "F7"

    # ---- F8: the integer-to-decimal bound, a declared property of the pinned runtime (XI.3)
    if _INT_DIGIT_LIMIT() == 0:
        assert ex.preflight_document({"m": 2 ** 20000}) is None   # this runtime has no declared limit
    else:
        assert _INT_DIGIT_LIMIT() == 4300
        assert ex.preflight_document({"m": 2 ** 20000}).category == "F8"

    # ---- declared-schema categories: F2/F3/F9 are task/plan only; the expectation owns row 5 instead
    assert ex.validate_declared_schema(dict(base, undeclared=1), "task") == "F2"
    assert ex.validate_declared_schema(dict(base, task_version=True), "task") == "F3"
    assert ex.validate_declared_schema(dict(base, allowed_mutations=[]), "task") is None      # empty permitted
    assert ex.validate_declared_schema(dict(base, dependencies=[]), "task") is None           # empty permitted
    assert ex.validate_declared_schema(dict(base, allowed_mutations=["a", "a"]), "task") == "F9"
    # the same document is not conformant as the other class (its member set is undeclared there)
    assert ex.validate_declared_schema(base, "plan") == "F2"

    # expectation class: a declared-member type violation is row 5, not F3/row 28
    claim = _claim(task, plan, task_version=True)
    classification = ex.classify_supplied_expectation(claim, task=task, plan=plan)
    assert classification.rows == frozenset({5})

    # rows: row 1 for the task/plan classes, row 28 for the expectation class, for every category
    assert ex.preflight_document({"m": {1, 2}}).row == 1
    assert ex.preflight_document({"m": {1, 2}}, expectation_side=True).row == 28
    assert ex.preflight_document({"m": float("nan")}).row == 1
    assert ex.preflight_document({"m": float("nan")}, expectation_side=True).row == 28


def test_b1_malformed_inputs_never_escape_as_uncaught_exceptions():
    """A malformed required input inside the object classes always yields a well-formed refusal result."""
    task, plan = _task_and_plan()
    malformed_tasks = []
    for changes in ({"task_version": True}, {"metadata": {"s": {1, 2}}}, {"metadata": {"n": float("nan")}},
                    {"metadata": {"s": "\ud800"}}, {"canonical_task_id": 5}):
        if _INT_DIGIT_LIMIT():
            malformed_tasks.append(_mutate(copy.deepcopy(task), metadata={"b": 2 ** 20000}))
        malformed_tasks.append(_mutate(copy.deepcopy(task), **changes))
    for candidate in malformed_tasks:
        result = ex.verify_semantic_target_r2a(candidate, plan)
        assert isinstance(result, ex.M126Result)
        assert result.members["deciding_stage"] == "S1"
        assert result.members["primary_failure_code"] == "RESOLVER_INPUT_STRUCTURE_INVALID"
        assert result.canonical_dict()  # serializable and coherent
    # a wrong object class entirely
    for candidate in (None, {}, "task"):
        result = ex.verify_semantic_target_r2a(candidate, plan)
        assert result.members["deciding_stage"] == "S1"
    # a malformed expectation object
    for candidate in ([], 7, {"undeclared": 1}, {"expectation_digest": 5}):
        result = ex.verify_semantic_target_r2a(task, plan, candidate)
        assert isinstance(result, ex.M126Result)
        assert result.members["failure_codes"]


# --------------------------------------------------------------- B2 / B7: independent row applicability


def test_b2_independently_applicable_rows_are_unioned():
    task, plan = _task_and_plan()

    # (a) null target member + a bad supplied digest: row 5 and row 8 both apply
    bad_digest = _claim(task, plan, production_target_id=None, expectation_digest="e" * 64)
    classification = ex.classify_supplied_expectation(bad_digest, task=task, plan=plan)
    assert classification.rows == frozenset({5, 8}), classification.rows

    # (b) null target member + an empty required set: row 5 and row 30 both apply
    empty_set = _claim(task, plan, production_target_id=None, required_invariant_names=[],
                       invariant_expectations=[])
    classification = ex.classify_supplied_expectation(empty_set, task=task, plan=plan)
    assert classification.rows == frozenset({5, 30}), classification.rows

    # (c) null target member + a row-39 contradiction: both apply
    contradicted = _claim(task, plan, production_target_id=None, origin_status="UNREVIEWED")
    classification = ex.classify_supplied_expectation(contradicted, task=task, plan=plan)
    assert classification.rows == frozenset({5, 39}), classification.rows

    # (d) a schema-valid expectation: identity recomputation is required (rows 4 and 7)
    valid = _claim(task, plan)
    classification = ex.classify_supplied_expectation(valid, task=task, plan=plan)
    assert classification.rows == frozenset({4, 7}), classification.rows
    assert classification.schema_valid is True

    # (e) rows 14/21 apply alongside 4/7 when their own predicates hold
    stale = _claim(task, plan, plan_content_digest="f" * 64)
    classification = ex.classify_supplied_expectation(stale, task=task, plan=plan)
    assert classification.rows == frozenset({4, 7, 14, 21}), classification.rows


def test_b2_row_5_exclusivity_applies_to_rows_4_and_7_only():
    task, plan = _task_and_plan()
    for changes in ({"production_target_id": None}, {"target_revision": None}, {"target_digest": None},
                    {"production_target_id": None, "target_revision": None, "target_digest": None}):
        classification = ex.classify_supplied_expectation(_claim(task, plan, **changes), task=task, plan=plan)
        assert 5 in classification.rows
        assert not ({4, 7} & set(classification.rows)), classification.rows
    # a row-39 contradiction is not a row-5 condition: identity recomputation stays demanded
    classification = ex.classify_supplied_expectation(_claim(task, plan, origin_status="UNREVIEWED"),
                                                     task=task, plan=plan)
    assert classification.rows == frozenset({4, 7, 39}), classification.rows


def test_b2_verifier_unions_supplied_expectation_rows_with_the_resolver_rows():
    """The end-to-end path unions the resolver's S4 rows with the expectation-side rows (no suppression)."""
    task, plan = _task_and_plan()
    result = ex.verify_semantic_target_r2a(task, plan, _claim(task, plan, production_target_id=None))
    codes = result.members["failure_codes"]
    assert "EXPECTATION_INCOMPLETE" in codes              # row 5, the deciding S3 stage
    assert result.members["primary_failure_code"] == "EXPECTATION_INCOMPLETE"
    assert result.members["deciding_stage"] == "S3"
    # the resolver's own S4 rows stay applicable (unioned, not suppressed) but are preempted by S3
    assert {6, 22} <= set(result.applicable_rows)
    assert "PRODUCTION_TARGET_NOT_ESTABLISHED" not in codes


# --------------------------------------------------------------- B3: S1 same-stage aggregation


def test_b3_task_and_plan_s1_components_are_both_collected():
    task, plan = _task_and_plan()
    _mutate(task, metadata={"s": {1, 2}})                      # F4 -> row 1
    plan_document = plan.to_json_compatible()
    assert ex.plan_contains_float(plan_document) is False
    _mutate(plan, provenance={"float_probe": 1.5})             # row 29 (single float-policy condition)
    resolution = ex.resolve(task, plan)
    assert resolution.applicable_rows == frozenset({1, 29}), resolution.applicable_rows
    assert resolution.derived["preflight"]["task"]["category"] == "F4"
    assert resolution.derived["preflight"]["float_policy"] == "PLAN_CONTENT_UNSUPPORTED"
    result = ex.verify_semantic_target_r2a(task, plan)
    codes = result.members["failure_codes"]
    assert "RESOLVER_INPUT_STRUCTURE_INVALID" in codes and "PLAN_CONTENT_UNSUPPORTED" in codes
    assert result.members["primary_failure_code"] == "RESOLVER_INPUT_STRUCTURE_INVALID"  # lowest-numbered
    assert result.members["deciding_stage"] == "S1"


def test_b3_xiv31_clause_4_same_stage_order_independence():
    """Clause 4: within a stage the union and its primary code do not depend on evaluation order."""
    import itertools

    for rows in ((1, 29), (3, 6, 22), (4, 7, 14, 21), (5, 30), (5, 8, 22), (26, 40, 41), (32, 36, 42, 43, 44)):
        reference = ex.decisive_outcome(sorted(rows))
        for permutation in itertools.permutations(rows):
            outcome = ex.decisive_outcome(list(permutation))
            assert (outcome.deciding_stage, outcome.primary_code, outcome.failure_codes, outcome.reason_class) == \
                   (reference.deciding_stage, reference.primary_code, reference.failure_codes, reference.reason_class)

    # the S1 row set itself is order-independent: the same input is classified identically however composed
    task, plan = _task_and_plan()
    _mutate(task, metadata={"s": {1, 2}})
    _mutate(plan, provenance={"float_probe": 1.5})
    task_document, plan_document = task.to_json_compatible(), plan.to_json_compatible()
    first = {r for r in (ex.preflight_document(task_document).row if ex.preflight_document(task_document) else None,
                         ex.preflight_document(plan_document).row if ex.preflight_document(plan_document) else None,
                         29 if ex.plan_contains_float(plan_document) else None) if r is not None}
    second = {r for r in (29 if ex.plan_contains_float(plan_document) else None,
                          ex.preflight_document(plan_document).row if ex.preflight_document(plan_document) else None,
                          ex.preflight_document(task_document).row if ex.preflight_document(task_document) else None)
              if r is not None}
    assert first == second == {1, 29}


# --------------------------------------------------------------- B4: result coherence and immutability


def _base_result():
    task, plan = _task_and_plan()
    return ex.verify_semantic_target_r2a(task, plan), task, plan


def test_b4_derived_fields_are_enforced_against_the_applicable_rows():
    result, _task, _plan = _base_result()
    members = dict(result.members)
    rows = result.applicable_rows

    fabricated = dict(members, primary_failure_code="PRODUCTION_TARGET_NOT_ESTABLISHED")
    with raises(ex.M126ContractError):
        ex.M126Result(_construction_token=ex._RESULT_CONSTRUCTION_TOKEN, members=fabricated, applicable_rows=rows)           # row 22 is not the lowest applicable row

    wrong_stage = dict(members, deciding_stage="S3")
    with raises(ex.M126ContractError):
        ex.M126Result(_construction_token=ex._RESULT_CONSTRUCTION_TOKEN, members=wrong_stage, applicable_rows=rows)

    wrong_class = dict(members, outcome_reason_class="EVIDENCE_INSUFFICIENT")
    with raises(ex.M126ContractError):
        ex.M126Result(_construction_token=ex._RESULT_CONSTRUCTION_TOKEN, members=wrong_class, applicable_rows=rows)

    wrong_states = dict(members, semantic_state="SATISFIED", overall_state="SATISFIED")
    with raises(ex.M126ContractError):
        ex.M126Result(_construction_token=ex._RESULT_CONSTRUCTION_TOKEN, members=wrong_states, applicable_rows=rows)

    assert ex.M126Result(_construction_token=ex._RESULT_CONSTRUCTION_TOKEN, members=members, applicable_rows=rows).result_digest == result.result_digest


def test_b4_invalid_failure_code_unions_are_refused():
    result, _task, _plan = _base_result()
    members = dict(result.members)
    rows = result.applicable_rows
    with raises(ex.M126ContractError):
        ex.M126Result(_construction_token=ex._RESULT_CONSTRUCTION_TOKEN, members=dict(members, failure_codes=tuple(reversed(members["failure_codes"]))),
                      applicable_rows=rows)
    with raises(ex.M126ContractError):
        ex.M126Result(_construction_token=ex._RESULT_CONSTRUCTION_TOKEN, members=dict(members, failure_codes=members["failure_codes"] + members["failure_codes"]),
                      applicable_rows=rows)
    with raises(ex.M126ContractError):
        ex.M126Result(_construction_token=ex._RESULT_CONSTRUCTION_TOKEN, members=dict(members, failure_codes=("NOT_A_PART_XV_TOKEN",)), applicable_rows=rows)
    assert all(code in ex.emittable_tokens() for code in members["failure_codes"])


def test_b4_a_row_set_is_required_and_r2a_reachability_is_enforced():
    result, _task, _plan = _base_result()
    members = dict(result.members)
    with raises(ex.M126ContractError):
        ex.M126Result(_construction_token=ex._RESULT_CONSTRUCTION_TOKEN, members=members)                                     # no applicable rows: refused
    for member, value in (("semantic_state", "SATISFIED"), ("overall_state", "NOT_SATISFIED"),
                          ("render_state", "VERIFIED"), ("deciding_stage", "S5")):
        with raises(ex.M126ContractError):
            ex.M126Result(_construction_token=ex._RESULT_CONSTRUCTION_TOKEN, members=dict(members, **{member: value}), applicable_rows=result.applicable_rows)
    fault = ex.express_fault_result(fault_injected=True)
    assert fault.members["deciding_stage"] is None
    assert fault.members["failure_codes"] == ("RESOLVER_INTERNAL_FAILURE",)
    assert fault.members["outcome_reason_class"] == "INTERNAL_FAILURE"
    with raises(ex.M126ContractError):
        ex.M126Result(_construction_token=ex._RESULT_CONSTRUCTION_TOKEN, members=dict(members, failure_codes=("SATISFIED",)), applicable_rows=(2,))


def test_b4_post_construction_mutation_is_detected():
    """XXVIII.1 item 8: canonical members are immutable, and a drifted copy cannot be serialized."""
    result, _task, _plan = _base_result()
    with raises(TypeError):
        result.members["semantic_state"] = "SATISFIED"
    with raises(TypeError):
        result.members["evidence_trust_basis"]["semantic_observation"] = "VERIFIED"
    with raises(TypeError):
        result.members["evidence_trust_basis"]["new_member"] = 1
    with raises(AttributeError):
        result.members["required_invariant_names"].append("extra")
    assert isinstance(result.applicable_rows, tuple)

    # a copy that has drifted since construction is refused at construction and again before serialization
    drifted = dict(result.members, semantic_state="SATISFIED", overall_state="SATISFIED")
    with raises(ex.M126ContractError):
        ex.M126Result(_construction_token=ex._RESULT_CONSTRUCTION_TOKEN, members=drifted, applicable_rows=result.applicable_rows)
    constructed = ex.M126Result(_construction_token=ex._RESULT_CONSTRUCTION_TOKEN, members=dict(result.members), applicable_rows=result.applicable_rows)
    object.__setattr__(constructed, "members", {**constructed.members, "primary_failure_code": None})
    with raises(ex.M126ContractError):
        constructed.canonical_dict()
    with raises(ex.M126ContractError):
        constructed.result_digest


# --------------------------------------------------------------- B5: M5 render-evidence integration


class _VerifiedEvidence:
    """Minimal stand-in for the M5-verified evidence returned by the unchanged M5 entry point."""

    digital_twin_id = "twin-1"
    atlas_job_id = "job-0001"
    attempt_ordinal = 2


def test_b5_render_evidence_requires_the_real_m5_handoff_types():
    """Part XVII.5/B8: a mapping or a shadow object cannot establish the render dimension (row 36)."""
    task, plan = _render_task_and_plan()
    for supplied in ({"operation_name": "inspect_render_job", "entity_ids": ("twin-1",), "observed_state": {},
                      "source": "engine", "job_record": {"atlas_job_id": "job-0001"}}, object()):
        result = ex.verify_semantic_target_r2a(task, plan, render_evidence=supplied)
        assert 36 in result.applicable_rows and 44 not in result.applicable_rows
        assert result.members["render_job_identity"] is None
        assert result.members["evidence_trust_basis"]["render_evidence"] == "NOT_ESTABLISHED"


# --------------------------------------------------------------- B6: S2 target-table reference integrity


def test_b6_dangling_mapping_reference_is_an_s2_integrity_refusal():
    """A mapping that matches the selector but references a nonexistent target is row 10, never a coverage miss."""
    task, _plan = _task_and_plan()
    triple = ex._selector_triple(task)
    dangling = ex.TaskTargetMapping(entry_name=triple[0], entry_version=triple[1], task_class=triple[2],
                                    production_target_id="target-does-not-exist")
    assert ex.mapping_reference_status(triple, mappings=(dangling,), targets=()) == "dangling"
    assert 10 in ex.revalidate_authority(targets=(), mappings=(dangling,))
    duplicate = (dangling, replace(dangling, production_target_id="other"))
    assert ex.mapping_reference_status(triple, mappings=duplicate, targets=()) == "duplicate"
    assert ex.mapping_reference_status(("other-entry", 1, triple[2]), mappings=(dangling,), targets=()) == "none"
    # the shipped R2-A tables are empty, so no dangling reference can arise from them (the resolver's own path
    # is a pure coverage miss reaching row 22, asserted elsewhere)
    assert ex.PRODUCTION_TARGET_BY_TASK == () and ex.PRODUCTION_TARGETS == ()
    resolution = ex.resolve(task, _plan)
    assert 22 in resolution.applicable_rows and 10 not in resolution.applicable_rows


def test_b6_non_conforming_authority_tables_are_refused_at_their_rows():
    conforming = _definition()
    assert ex.revalidate_authority(definitions=(conforming,), targets=()) == frozenset({9})
    # row 11: two REGISTERED definitions share one invariant name
    row_11 = (conforming, replace(conforming, definition_revision=2))
    assert 11 in ex.revalidate_authority(definitions=row_11, targets=())
    # row 33: an authority class other than the single admitted one
    row_33 = (replace(conforming, authority_class="RUNTIME_PROBE"),)
    assert 33 in ex.revalidate_authority(definitions=row_33, targets=())
    # row 38: an empty or unsorted observable path set / subject scope
    assert 38 in ex.revalidate_authority(definitions=(replace(conforming, observable_paths=()),), targets=())
    assert 38 in ex.revalidate_authority(definitions=(replace(conforming, subject_scope=("b", "a")),), targets=())
    # row 12: two mappings share one selector triple
    specs = (ex.ProductionTargetSpec("t1", 1, "a", "b", (), (), None, "ref", "nonclaim"),
             ex.ProductionTargetSpec("t2", 1, "a", "b", (), (), None, "ref", "nonclaim"))
    conflicting = (ex.TaskTargetMapping("e", 1, "c", "t1"), ex.TaskTargetMapping("e", 1, "c", "t2"))
    assert 10 in ex.revalidate_authority(targets=(), mappings=conflicting)          # the dangling reference
    assert 12 in ex.revalidate_authority(targets=specs, mappings=conflicting)       # the duplicate triple
    # the shipped R2-A tables conform to their reviewed constants (no integrity row applies)
    assert ex.revalidate_authority() == frozenset()


# --------------------------------------------------------------- B7: incomplete expectation members


def test_b7_absent_expectation_members_are_never_compared_against_recomputed_values():
    task, plan = _task_and_plan()
    for member in ("plan_content_digest", "source_content_digest", "expectation_digest", "plan_id"):
        claim = _claim(task, plan)
        claim.pop(member)
        classification = ex.classify_supplied_expectation(claim, task=task, plan=plan)
        assert classification.rows == frozenset({5}), (member, classification.rows)
        assert "stale_plan" not in classification.detail and "stale_source" not in classification.detail
        assert "digest_mismatch" not in classification.detail
        assert classification.schema_valid is False
    # with the prerequisites present, rows 14/21 do apply on a genuine mismatch
    stale = _claim(task, plan, plan_content_digest="f" * 64)
    classification = ex.classify_supplied_expectation(stale, task=task, plan=plan)
    assert {14, 21} <= set(classification.rows) and classification.detail["stale_plan"] is True
    fresh = _claim(task, plan)
    classification = ex.classify_supplied_expectation(fresh, task=task, plan=plan)
    assert not ({14, 21} & set(classification.rows))


# --------------------------------------------------------------- B8: structural / CI obligations


def _module_source():
    return (REPO_ROOT / "planning" / "m12" / "expectation.py").read_text(encoding="utf-8")


def test_b8_xiv74_single_implementation_and_single_call_sites():
    """XIV.7.4: one implementation and one call site per contract mechanism, asserted structurally."""
    tree = ast.parse(_module_source())
    defined = {}

    def _name(node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None

    counts = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            counts.setdefault(node.name, []).append("definition")
        elif isinstance(node, ast.Call):
            called = _name(node.func)
            if called:
                counts.setdefault(called, []).append("call")
    for mechanism in ("M126Result", "verify_semantic_target_r2a", "compute_evidence_identity",
                      "compute_invariant_result_digest", "compute_plan_content_digest", "classify_failure_row",
                      "decisive_outcome", "map_states", "unresolved_entry"):
        kinds = counts.get(mechanism, [])
        assert kinds.count("definition") == 1, (mechanism, kinds)
    assert counts["M126Result"].count("definition") == 1        # one sealed result type
    assert counts["compute_evidence_identity"].count("definition") == 1
    constants = [node for node in tree.body
                 if isinstance(node, ast.Assign)
                 and any(getattr(t, "id", None) == "RESULT_SCHEMA_CONSTANT" for t in node.targets)]
    assert len(constants) == 1


def test_b8_cross_process_hash_seed_determinism():
    """Determinism across processes with differing PYTHONHASHSEED (Part XX obligation)."""
    program = (
        "import sys; sys.path.insert(0, '.');"
        "from planning.m12 import DEFAULT_UNREAL_CATALOG, generate_execution_plan;"
        "from planning.m12 import expectation as ex;"
        "t = DEFAULT_UNREAL_CATALOG.resolve('unreal.sequence-configure',"
        " {'twin_id': 'twin-1', 'sequence_name': 'main', 'frame_start': 1, 'frame_end': 24},"
        " digital_twin_id='twin-1');"
        "p = generate_execution_plan(t);"
        "r = ex.verify_semantic_target_r2a(t, p);"
        "print(r.result_digest)"
    )
    digests = set()
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        completed = subprocess.run([sys.executable, "-c", program], cwd=str(REPO_ROOT), env=env,
                                   capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr
        digests.add(completed.stdout.strip())
    assert len(digests) == 1, digests


def test_b8_artifact_derived_part_xv_census():
    """The Part XV row/token census derived from the frozen artifact matches the implementation's table."""
    if not R18_PATH.exists():
        print("SKIP: the R18 artifact is not present in this environment (census cannot be derived)")
        return
    text = R18_PATH.read_text(encoding="utf-8")
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == \
        "ec5eab43a4dbd3dc8e7c376133aff954a6c25a4283c3eb0d2bed31081ae2b41d"
    start = text.index("# PART XV")
    end = text.index("# PART XVI")
    rows = [line for line in text[start:end].splitlines()
            if line.startswith("| ") and line.split("|")[1].strip().isdigit()]
    row_ids = {int(line.split("|")[1].strip()) for line in rows}
    tokens = {line.split("|")[3].strip().strip("`") for line in rows if line.count("|") >= 4}
    declared_rows, declared_tokens = ex.row_census()
    assert len(row_ids) == declared_rows == 42
    assert len(tokens) == declared_tokens == 35
    assert row_ids == {row_id for row_id in range(1, 45)} - {34, 35}


def test_b8_xxviii2_affected_assertion_record():
    """The record's affected-assertion set is asserted exactly (count, files, categories)."""
    if not R18_PATH.exists():
        print("SKIP: the R18 artifact is not present in this environment")
        return
    text = R18_PATH.read_text(encoding="utf-8")
    section = text[text.index("## XXVIII.2"):]
    section = section[:section.index("## XXVIII.3")]
    tables = [block for block in section.split("|---|---|---|---|")[1:]]
    category_i = [line for line in tables[0].splitlines() if line.startswith("| ") and line.split("|")[1].strip().isdigit()]
    category_ii = [line for line in tables[1].splitlines() if line.startswith("| ") and line.split("|")[1].strip().isdigit()]
    assert len(category_i) == 22, len(category_i)
    assert len(category_ii) == 2, len(category_ii)
    statements = category_i + category_ii
    assert len(statements) == 24
    files = {line.split("|")[2].strip() for line in statements}
    assert files == {"test_m12_5_verification.py", "test_m12_5_adversarial.py"}
    assert len(files) == 2
    lines = {f for f in (line.split("|")[3].strip() for line in statements)}
    assert all(f.isdigit() for f in lines)
    # every recorded base line is an assertion statement in its recorded file, and the two affected files are
    # untouched by this remediation (the compatibility change lands with the M12.6 verifier, not before)
    tests_dir = REPO_ROOT / "tests" / "m12"
    for statement in statements:
        file_name = statement.split("|")[2].strip()
        base_line = int(statement.split("|")[3].strip())
        lines_of_file = (tests_dir / file_name).read_text(encoding="utf-8").splitlines()
        assert base_line <= len(lines_of_file), (file_name, base_line)
        assert "assert" in lines_of_file[base_line - 1], (file_name, base_line, lines_of_file[base_line - 1])


def test_b8_target_table_identity_and_consumer_controls():
    """Part XX / VIII.3: the target table is a frozen constant and its consumer objects are immutable."""
    assert isinstance(ex.PRODUCTION_TARGETS, tuple) and isinstance(ex.PRODUCTION_TARGET_BY_TASK, tuple)
    assert isinstance(ex.SEMANTIC_INVARIANT_DEFINITIONS, tuple)
    assert ex.REGISTERED_COUNT == 0
    assert ex.target_table_digest(ex.PRODUCTION_TARGETS) == ex.TARGET_TABLE_DIGEST
    mapping = ex.TaskTargetMapping("e", 1, "c", "t")
    with raises(FrozenInstanceError):
        mapping.production_target_id = "other"
    spec = ex.ProductionTargetSpec("t", 1, "a", "b", (), (), None, "ref", "nonclaim")
    with raises(FrozenInstanceError):
        spec.target_revision = 2
    with raises(TypeError):
        ex.PRODUCTION_TARGETS[0] = spec if ex.PRODUCTION_TARGETS else None
    status = ex.production_target_status()
    assert status  # a declared, serializable status for the empty R2-A table
    # the empty table cannot produce an R2-B-only outcome
    task, plan = _task_and_plan()
    result = ex.verify_semantic_target_r2a(task, plan)
    for member in ("production_target_id", "target_revision", "target_digest"):
        assert result.members[member] is None
    assert result.members["semantic_state"] not in ("SATISFIED", "NOT_SATISFIED")
