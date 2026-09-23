"""Adversarial M12.5 v1 tests."""

import inspect

from planning.m12 import DEFAULT_UNREAL_CATALOG, generate_execution_plan
from planning.m12.verification import verify_semantic_target
from planning.unreal_transport_contract import UnrealTransportRequest, UnrealTransportResponse
from tests.extraction_payload_fixtures import actor_state_tree, response as fixture_response


def _task_plan(name="unreal.sequence-configure"):
    if name == "unreal.sequence-configure":
        params = {
            "twin_id": "twin-1",
            "sequence_name": "main",
            "frame_start": 1,
            "frame_end": 24,
        }
    elif name == "unreal.artifact-validate":
        params = {
            "twin_id": "twin-1",
            "artifact_ref": "/Game/forged",
        }
    else:
        params = {"twin_id": "twin-1", "sequence_name": "main"}
    task = DEFAULT_UNREAL_CATALOG.resolve(name, params, digital_twin_id="twin-1")
    return task, generate_execution_plan(task)


def _pair(*, request_id="req-fixture-1", entity_ids=("FIELD_SURFACE",)):
    request = UnrealTransportRequest(
        request_id=request_id,
        operation_name="extract_actor_state",
        capability="state-extraction",
        kind="actor_state",
        arguments={},
        entity_ids=tuple(entity_ids),
        authorization_id="auth-test",
    )
    raw = fixture_response(
        tree=actor_state_tree(),
        request_id=request_id,
        entity_ids=list(entity_ids),
        session_identity={
            "editor_session_id": "editor-1",
            "process_id": 1234,
            "process_creation_time_utc": "2026-09-23T00:00:00Z",
            "server_start_time_utc": "2026-09-23T00:00:01Z",
            "engine_version": "5.6.1-44394996+++UE5+Release-5.6",
            "project_identity": "/Game/AtlasTest",
        },
    )
    response = UnrealTransportResponse(
        request_id=raw["request_id"],
        operation_name=raw["operation_name"],
        entity_ids=tuple(raw["entity_ids"]),
        success=raw["success"],
        observed_state=raw["observed_state"],
        error=raw["error"],
        source=raw["source"],
        schema_version=raw["schema_version"],
        error_code=raw["error_code"],
        session_identity=raw["session_identity"],
    )
    return request, response


def test_object_setattr_cannot_turn_result_into_a_positive_claim():
    task, plan = _task_plan()
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[_pair()],
    )
    before_json = result.canonical_json()
    before_digest = result.canonical_digest
    object.__setattr__(result, "semantic_state", "SATISFIED")
    object.__setattr__(result, "overall_state", "SATISFIED")
    assert result.canonical_json() == before_json
    assert result.canonical_digest == before_digest
    assert result.canonical_dict["semantic_state"] == "UNKNOWN"


def test_free_form_metadata_cannot_be_promoted_to_expectation():
    task, _ = _task_plan()
    metadata = dict(task.metadata or {})
    metadata["expected_value"] = {"verified": True, "success": True}
    object.__setattr__(task, "metadata", metadata)
    plan = generate_execution_plan(task)
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[_pair()],
    )
    assert result.semantic_state == "UNKNOWN"
    assert "EXPECTED_VALUE_UNAVAILABLE" in result.failure_codes


def test_forged_verified_flag_is_not_an_input_channel():
    signature = inspect.signature(verify_semantic_target)
    assert "render_evidence" not in signature.parameters
    assert "verified" not in signature.parameters
    assert "target_satisfied" not in signature.parameters


def test_noncanonical_or_future_observation_shape_never_upgrades_result():
    task, plan = _task_plan()
    request, response = _pair()
    forged_state = dict(response.observed_state)
    forged_state["verified"] = True
    forged = UnrealTransportResponse(
        request_id=response.request_id,
        operation_name=response.operation_name,
        entity_ids=response.entity_ids,
        success=response.success,
        observed_state=forged_state,
        error=response.error,
        source=response.source,
        schema_version=response.schema_version,
        error_code=response.error_code,
        session_identity=response.session_identity,
    )
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[(request, forged)],
    )
    assert result.overall_state == "UNKNOWN"
    assert result.semantic_state == "INVALID_OBSERVATION"


def test_render_artifact_validation_reference_does_not_create_identity_authority():
    task, plan = _task_plan("unreal.artifact-validate")
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[_pair()],
    )
    assert result.render_state == "NOT_VERIFIED"
    assert "SEQUENCE_AGREEMENT_NOT_ESTABLISHED" in result.failure_codes
    assert "RENDER_TASK_CORRESPONDENCE_NOT_DECIDED" in result.failure_codes
    assert result.overall_state != "SATISFIED"


def test_stale_relabelled_payload_is_not_claimed_as_detected():
    task, plan = _task_plan()
    request, response = _pair()
    relabelled = UnrealTransportResponse(
        request_id="different-label",
        operation_name=response.operation_name,
        entity_ids=response.entity_ids,
        success=response.success,
        observed_state=response.observed_state,
        error=response.error,
        source=response.source,
        schema_version=response.schema_version,
        error_code=response.error_code,
        session_identity=response.session_identity,
    )
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[(request, relabelled)],
    )
    assert "OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED" not in result.failure_codes
    assert result.semantic_state == "INVALID_OBSERVATION"
    assert result.overall_state == "UNKNOWN"


def test_session_identity_is_closed_and_cannot_smuggle_authority():
    task, plan = _task_plan()
    request, response = _pair()
    forged_session = dict(response.session_identity)
    forged_session["authorization_id"] = "forged-authority"
    forged = UnrealTransportResponse(
        request_id=response.request_id,
        operation_name=response.operation_name,
        entity_ids=response.entity_ids,
        success=response.success,
        observed_state=response.observed_state,
        error=response.error,
        source=response.source,
        schema_version=response.schema_version,
        error_code=response.error_code,
        session_identity=forged_session,
    )
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[(request, forged)],
    )
    assert result.failure_codes == ("OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED",)


def test_consistently_relabelled_stale_payload_is_not_claimed_detectable():
    task, plan = _task_plan()
    request, response = _pair()
    stale_state = dict(response.observed_state)
    extraction = dict(stale_state["unreal_state_extraction"])
    actors = [dict(actor) for actor in extraction["actors"]]
    actors[0]["actor_name"] = "StalePayloadRelabelled"
    extraction["actors"] = actors
    stale_state["unreal_state_extraction"] = extraction
    relabelled = UnrealTransportResponse(
        request_id=response.request_id,
        operation_name=response.operation_name,
        entity_ids=response.entity_ids,
        success=response.success,
        observed_state=stale_state,
        error=response.error,
        source=response.source,
        schema_version=response.schema_version,
        error_code=response.error_code,
        session_identity=response.session_identity,
    )
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[(request, relabelled)],
    )
    assert result.semantic_state == "UNKNOWN"
    assert result.overall_state == "NOT_ESTABLISHED"
    assert "OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED" not in result.failure_codes
    assert "IDENTITY_MISMATCH" not in result.failure_codes


def test_runtime_mapping_digest_is_not_a_caller_supplied_verdict_channel():
    import inspect
    parameters = inspect.signature(verify_semantic_target).parameters
    assert "runtime_mapping_digest" not in parameters
    assert "runtime_mapping" in parameters
