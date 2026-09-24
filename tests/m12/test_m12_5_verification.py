"""Deterministic M12.5 verification tests."""

import json

import pytest

from planning.m12 import DEFAULT_UNREAL_CATALOG, generate_execution_plan
from planning.m12.verification import M12VerificationError, verify_semantic_target
from planning.unreal_transport_contract import (
    UnrealTransportRequest,
    UnrealTransportResponse,
)
from tests.extraction_payload_fixtures import actor_state_tree, response as fixture_response


def _task_and_plan(task_name="unreal.sequence-configure"):
    if task_name == "unreal.sequence-configure":
        task = DEFAULT_UNREAL_CATALOG.resolve(
            task_name,
            {
                "twin_id": "twin-1",
                "sequence_name": "main",
                "frame_start": 1,
                "frame_end": 24,
            },
            digital_twin_id="twin-1",
        )
    else:
        task = DEFAULT_UNREAL_CATALOG.resolve(
            task_name,
            {"twin_id": "twin-1", "sequence_name": "main"},
            digital_twin_id="twin-1",
        )
    return task, generate_execution_plan(task)


def _observation_pair(*, request_id="req-fixture-1", entity_ids=("FIELD_SURFACE",), tree=None, session=True):
    req = UnrealTransportRequest(
        request_id=request_id,
        operation_name="extract_actor_state",
        capability="state-extraction",
        kind="actor_state",
        arguments={},
        entity_ids=tuple(entity_ids),
        authorization_id="auth-test",
    )
    raw = fixture_response(
        tree=tree or actor_state_tree(),
        session_identity=(
            {
                "editor_session_id": "editor-1",
                "process_id": 1234,
                "process_creation_time_utc": "2026-09-23T00:00:00Z",
                "server_start_time_utc": "2026-09-23T00:00:01Z",
                "engine_version": "5.6.1-44394996+++UE5+Release-5.6",
                "project_identity": "/Game/AtlasTest",
            }
            if session
            else {}
        ),
        request_id=request_id,
        entity_ids=list(entity_ids),
    )
    resp = UnrealTransportResponse(
        request_id=raw["request_id"],
        operation_name=raw["operation_name"],
        entity_ids=tuple(raw["entity_ids"]),
        success=raw["success"],
        observed_state=raw["observed_state"],
        error=raw["error"],
        source=raw["source"],
        schema_version=raw["schema_version"],
        error_code=raw["error_code"],
        session_identity=raw.get("session_identity", {}),
    )
    return req, resp


def test_non_render_invariants_are_unknown_and_fail_closed():
    task, plan = _task_and_plan()
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[_observation_pair()],
    )
    assert result.semantic_state == "UNKNOWN"
    assert result.overall_state == "NOT_ESTABLISHED"
    assert result.render_state == "NOT_REQUIRED"
    assert "EXPECTED_VALUE_UNAVAILABLE" in result.failure_codes
    assert result.invariant_results
    assert all(r["status"] == "UNKNOWN" for r in result.invariant_results)
    assert result.overall_state != "SATISFIED"


def test_repeated_identical_observation_is_not_contradictory():
    task, plan = _task_and_plan()
    pair = _observation_pair()
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[pair, pair],
    )
    assert result.overall_state == "NOT_ESTABLISHED"
    assert "CONTRADICTORY" not in result.failure_codes
    assert len(result.observation_digests) == 1


def test_conflicting_duplicate_is_contradictory():
    from tests.extraction_payload_fixtures import actor

    task, plan = _task_and_plan()
    first = _observation_pair()
    changed_tree = actor_state_tree(actors=[actor(actor_name="ChangedFixture")])
    second = _observation_pair(tree=changed_tree)
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[first, second],
    )
    assert result.semantic_state == "INVALID_OBSERVATION"
    assert result.overall_state == "UNKNOWN"
    assert result.failure_codes == ("CONTRADICTORY",)


def test_scope_divergence_fails_closed():
    task, plan = _task_and_plan()
    first = _observation_pair(entity_ids=("FIELD_SURFACE",))
    second = _observation_pair(entity_ids=("OTHER_ENTITY",))
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[first, second],
    )
    assert result.failure_codes == ("OBSERVATION_SCOPE_DIVERGENCE",)


def test_caller_observation_digest_is_only_a_redundant_assertion():
    task, plan = _task_and_plan()
    pair = _observation_pair()
    good = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[pair],
    )
    bad = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[pair],
        claimed_observation_digest="0" * 64,
    )
    assert good.observation_identity is not None
    assert bad.failure_codes == ("IDENTITY_MISMATCH",)
    assert bad.semantic_state == "NOT_ESTABLISHED"
    assert bad.overall_state == "NOT_ESTABLISHED"


def test_missing_session_identity_is_not_transport_rooted():
    task, plan = _task_and_plan()
    req, response = _observation_pair(session=False)
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[(req, response)],
    )
    assert result.failure_codes == ("OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED",)


def test_render_bearing_task_never_reports_verified_render_in_v1():
    task, plan = _task_and_plan("unreal.render-execute")
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[_observation_pair()],
    )
    assert result.render_state == "NOT_VERIFIED"
    assert result.evidence_trust_basis.render_evidence == "NOT_ESTABLISHED"
    assert "SEQUENCE_AGREEMENT_NOT_ESTABLISHED" in result.failure_codes
    assert "REQUEST_DIGEST_AGREEMENT_NOT_ESTABLISHED" in result.failure_codes
    assert "RENDER_TASK_CORRESPONDENCE_NOT_DECIDED" in result.failure_codes
    assert result.render_state != "VERIFIED"


def test_plan_render_classification_is_authoritative_from_source():
    task, plan = _task_and_plan("unreal.render-execute")
    object.__setattr__(plan, "render_plan", False)
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[_observation_pair()],
    )
    assert result.failure_codes == ("PLAN_RENDER_CLASSIFICATION_MISMATCH",)


def test_result_canonicalization_is_stable_and_excludes_authority_material():
    task, plan = _task_and_plan()
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[_observation_pair()],
    )
    first_json = result.canonical_json()
    first_digest = result.canonical_digest
    parsed = json.loads(first_json)
    assert set(parsed["provenance"]) == {
        "verifier_revision",
        "task_identity",
        "task_version",
        "digital_twin_id",
        "plan_id",
        "source_content_digest",
        "runtime_mapping_digest",
        "required_invariant_names",
        "extraction_contract_revision",
        "extractor_identity",
        "engine_identity",
        "observation_session_identity",
        "observation_scope_identity",
        "observation_request_identity",
        "observation_digests",
        "render_job_identity",
        "render_attempt_identity",
        "render_evidence_identity",
        "evidence_trust_basis",
        "outcome",
        "invariant_outcomes",
        "failure_codes",
    }
    lowered = first_json.lower()
    for token in (
        "authorization_id",
        "attempt_nonce",
        "last_accepted_lease_token",
        "receipt_reference",
        "manifest_reference",
    ):
        assert token not in lowered
    assert result.canonical_json() == first_json
    assert result.canonical_digest == first_digest


def test_unknown_or_future_fields_cannot_create_a_positive_result():
    task, plan = _task_and_plan()
    req, response = _observation_pair()
    observed = dict(response.observed_state)
    observed["future_field"] = {"verified": True}
    forged = UnrealTransportResponse(
        request_id=response.request_id,
        operation_name=response.operation_name,
        entity_ids=response.entity_ids,
        success=response.success,
        observed_state=observed,
        error=response.error,
        source=response.source,
        schema_version=response.schema_version,
        error_code=response.error_code,
        session_identity=response.session_identity,
    )
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[(req, forged)],
    )
    assert result.overall_state == "UNKNOWN"
    assert result.semantic_state == "INVALID_OBSERVATION"
