"""Atlas M12.6 R2-A refusal-only machinery tests."""

from dataclasses import replace

import pytest

from planning.m12 import DEFAULT_UNREAL_CATALOG, generate_execution_plan
from planning.m12.expectation import (
    DEFINITIONS_BY_NAME,
    PRODUCTION_TARGET_BY_TASK,
    TARGET_TABLE_DIGEST,
    ReasonClass,
    OverallState,
    SemanticState,
    SemanticExpectationRefusal,
    compute_evidence_identity,
    compute_invariant_result_digest,
    compute_plan_content_digest,
    compute_result_digest,
    resolve_semantic_expectation,
    structural_preflight,
)
from planning.unreal_state_extraction.jcs import canonical_bytes


def _task_plan(name="unreal.sequence-configure"):
    params = (
        {
            "twin_id": "twin-1",
            "sequence_name": "main",
            "frame_start": 1,
            "frame_end": 24,
        }
        if name == "unreal.sequence-configure"
        else {"twin_id": "twin-1", "sequence_name": "main"}
    )
    task = DEFAULT_UNREAL_CATALOG.resolve(
        name, params, digital_twin_id="twin-1"
    )
    return task, generate_execution_plan(task)


def test_r2a_empty_authority_state_is_single_deterministic_refusal():
    task, plan = _task_plan()
    with pytest.raises(SemanticExpectationRefusal) as caught:
        resolve_semantic_expectation(source_task=task, plan=plan)

    refusal = caught.value
    assert refusal.primary_code == "EXPECTED_VALUE_UNAVAILABLE"
    assert refusal.stage == 4
    assert refusal.reason_class is ReasonClass.AUTHORITY_ABSENT
    assert refusal.failure_codes == (
        "EXPECTED_VALUE_UNAVAILABLE",
        "PRODUCTION_TARGET_NOT_ESTABLISHED",
    )
    assert refusal.semantic_state is SemanticState.NOT_ESTABLISHED
    assert refusal.overall_state is OverallState.NOT_ESTABLISHED
    assert set(refusal.invariant_states.values()) == {
        # R2-A must never report MISSING for an S4 refusal.
        __import__("planning.m12.expectation", fromlist=["InvariantState"]).InvariantState.UNKNOWN
    }


def test_r2a_empty_target_table_is_not_a_target_value():
    assert PRODUCTION_TARGET_BY_TASK == ()
    assert TARGET_TABLE_DIGEST
    assert not any(
        getattr(row, "production_target_id", None)
        for row in PRODUCTION_TARGET_BY_TASK
    )


def test_plan_digest_uses_m12_3_full_document_recipe():
    _, plan = _task_plan()
    assert compute_plan_content_digest(plan) == __import__(
        "planning.m12.execution_plan", fromlist=["_canonical_sha256"]
    )._canonical_sha256(plan.to_json_compatible(), "execution_plan")


def test_structural_preflight_accepts_exact_valid_task_and_plan():
    task, plan = _task_plan()
    assert structural_preflight(task, plan) is None


def test_structural_preflight_rejects_subclass_types():
    task, plan = _task_plan()

    class TaskSubclass(type(task)):
        pass

    class PlanSubclass(type(plan)):
        pass

    bad_task = object.__new__(TaskSubclass)
    bad_plan = object.__new__(PlanSubclass)
    assert structural_preflight(bad_task, plan) == "F1"
    assert structural_preflight(task, bad_plan) == "F1"


def test_evidence_identity_distinguishes_absent_from_present_null():
    definition = next(iter(DEFINITIONS_BY_NAME.values()))
    absent = compute_evidence_identity(
        invariant_name=definition.invariant_name,
        definition=definition,
        resolved_observables=(),
        value_state="ABSENT",
        observation_bound=False,
        observation_request_id=None,
        observation_scope=None,
        canonical_state_digest=None,
    )
    present_null = compute_evidence_identity(
        invariant_name=definition.invariant_name,
        definition=definition,
        resolved_observables=(
            __import__("planning.m12.expectation", fromlist=["ResolvedObservable"]).ResolvedObservable(
                concrete_path="world.null_value", value=None
            ),
        ),
        value_state="PRESENT_NULL",
        observation_bound=True,
        observation_request_id="req-1",
        observation_scope=("FIELD_SURFACE",),
        canonical_state_digest="0" * 64,
    )
    assert absent != present_null


def test_invariant_result_digest_is_domain_separated_and_recomputable():
    entry = {
        "invariant_name": "scene_initialized",
        "definition_id": "scene_initialized",
        "definition_revision": 1,
        "definition_digest": "0" * 64,
        "authority_class": "CODE_CONSTANT",
        "subject_scope": (),
        "expected_value_identity": "1" * 64,
        "comparison": "EQUALS",
        "admissible_value_type": "STR",
        "observed_path_patterns": (),
        "value_state": "ABSENT",
        "resolved_observables": (),
        "observation_bound": False,
        "observation_identity": None,
        "invariant_state": "UNKNOWN",
        "mismatch_reason": None,
        "evidence_identity": "2" * 64,
    }
    first = compute_invariant_result_digest(entry)
    second = compute_invariant_result_digest(dict(entry))
    assert first == second
    changed = dict(entry, invariant_state="MISSING")
    assert first != compute_invariant_result_digest(changed)


def test_result_digest_is_domain_separated():
    from planning.m12.expectation import RESULT_DIGEST_KEYS

    payload = {
        key: None for key in RESULT_DIGEST_KEYS
    }
    payload.update({
        "schema": "m12.6-result-v1",
        "verifier_revision": "m12.6-v1",
        "expectation_contract_revision": "m12.6-expectation-v1",
        "resolver_revision": "m12.6-resolver-v1",
        "registry_revision": 1,
        "registry_digest": "0" * 64,
        "target_table_revision": 1,
        "target_table_digest": "1" * 64,
        "task_identity": "unreal.sequence-configure",
        "task_version": 1,
        "digital_twin_id": "twin-1",
        "catalog_entry_name": "unreal.sequence-configure",
        "catalog_entry_version": 1,
        "vocabulary_digest": "2" * 64,
        "plan_id": "plan:test",
        "source_content_digest": "3" * 64,
        "plan_content_digest": "4" * 64,
        "render_task": False,
        "required_invariant_names": ["scene_initialized"],
        "expectation_identity": {},
        "expectation_digest": "5" * 64,
        "observation_identity": None,
        "observation_digests": [],
        "render_job_identity": None,
        "render_attempt_identity": None,
        "render_evidence_identity": None,
        "evidence_trust_basis": {
            "semantic_observation": "NOT_ESTABLISHED",
            "render_evidence": "NOT_APPLICABLE",
        },
        "invariant_results": [],
        "semantic_state": "NOT_ESTABLISHED",
        "render_state": "NOT_REQUIRED",
        "overall_state": "NOT_ESTABLISHED",
        "outcome_reason_class": "AUTHORITY_ABSENT",
        "failure_codes": ["EXPECTED_VALUE_UNAVAILABLE"],
        "origin_status": "NOT_ESTABLISHED",
        "production_target_id": None,
        "target_revision": None,
        "target_digest": None,
    })
    digest = compute_result_digest(payload)
    assert len(digest) == 64
    assert digest == compute_result_digest(dict(payload))
    assert digest != compute_result_digest(
        dict(payload, failure_codes=["PRODUCTION_TARGET_NOT_ESTABLISHED"])
    )


def test_within_stage_order_is_deterministic():
    first = tuple(sorted(("EXPECTED_VALUE_UNAVAILABLE", "PRODUCTION_TARGET_NOT_ESTABLISHED")))
    second = tuple(sorted(("PRODUCTION_TARGET_NOT_ESTABLISHED", "EXPECTED_VALUE_UNAVAILABLE")))
    assert first == second

def test_failure_classifier_is_closed_and_stage_homogeneous():
    from planning.m12.expectation import FAILURE_CLASSIFIER, aggregate_stage_failures
    assert FAILURE_CLASSIFIER["EXPECTED_VALUE_UNAVAILABLE"] == (4, ReasonClass.AUTHORITY_ABSENT)
    assert FAILURE_CLASSIFIER["PRODUCTION_TARGET_NOT_ESTABLISHED"] == (4, ReasonClass.AUTHORITY_ABSENT)
    primary, cls, codes = aggregate_stage_failures([
        (22, "PRODUCTION_TARGET_NOT_ESTABLISHED"),
        (6, "EXPECTED_VALUE_UNAVAILABLE"),
    ])
    assert primary == "EXPECTED_VALUE_UNAVAILABLE"
    assert cls is ReasonClass.AUTHORITY_ABSENT
    assert codes == (
        "EXPECTED_VALUE_UNAVAILABLE",
        "PRODUCTION_TARGET_NOT_ESTABLISHED",
    )


def test_finite_plan_float_uses_single_policy_token():
    task, plan = _task_plan()
    provenance = dict(plan.provenance)
    provenance["float_policy_probe"] = 1.25
    object.__setattr__(plan, "provenance", provenance)
    with pytest.raises(SemanticExpectationRefusal) as caught:
        resolve_semantic_expectation(source_task=task, plan=plan)
    assert caught.value.primary_code == "PLAN_CONTENT_UNSUPPORTED"


def test_noncanonical_fragment_refuses_before_s4():
    from planning.m12.execution_plan import _build_plan_id

    task, plan = _task_plan()
    step = plan.steps[0]
    object.__setattr__(step, "semantic_operation", "not-a-canonical-fragment")
    object.__setattr__(
        plan,
        "plan_id",
        _build_plan_id(
            task.canonical_task_id,
            task.task_version,
            tuple(s.semantic_operation for s in plan.steps),
            plan.source_content_digest,
        ),
    )
    with pytest.raises(SemanticExpectationRefusal) as caught:
        resolve_semantic_expectation(source_task=task, plan=plan)
    assert caught.value.primary_code == "PLAN_STEP_NOT_CANONICAL"


def test_render_classification_mismatch_is_s3_refusal():
    task, plan = _task_plan("unreal.sequence-configure")
    object.__setattr__(plan, "render_plan", True)
    with pytest.raises(SemanticExpectationRefusal) as caught:
        resolve_semantic_expectation(source_task=task, plan=plan)
    assert caught.value.primary_code == "PLAN_RENDER_CLASSIFICATION_MISMATCH"


def test_r2a_result_contract_is_closed_and_digest_recomputable():
    from planning.m12.verification import verify_semantic_target

    task, plan = _task_plan()
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[],
    )
    assert result.verifier_revision == "m12.6-v1"
    assert result.semantic_state in {"UNKNOWN", "NOT_ESTABLISHED"}
    assert result.overall_state in {"UNKNOWN", "NOT_ESTABLISHED"}
    assert result.outcome_reason_class in {
        "AUTHORITY_ABSENT", "BINDING_ABSENT", "EVIDENCE_INSUFFICIENT", "INTERNAL_FAILURE"
    }
    assert result.invariant_results
    assert all(
        type(entry).__name__ == "InvariantVerificationResult"
        for entry in result.invariant_results
    )
    assert all(entry.invariant_state in {"UNKNOWN", "MISSING"} for entry in result.invariant_results)
    assert result.result_digest == result.canonical_digest
    assert len(result.result_digest) == 64
    assert result.result_digest == result.canonical_digest
    assert "runtime_mapping_digest" not in result.canonical_dict
    assert "provenance" not in result.canonical_dict


def test_r2a_result_digest_changes_when_closed_failure_code_changes():
    from planning.m12.verification import verify_semantic_target

    task, plan = _task_plan()
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[],
    )
    payload = dict(result.canonical_dict)
    altered = dict(payload, failure_codes=["PRODUCTION_TARGET_NOT_ESTABLISHED"])
    assert result.result_digest != compute_result_digest(altered)
