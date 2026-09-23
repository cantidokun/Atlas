"""M12.5 identity-binding tests."""

from dataclasses import replace

from planning.m12 import DEFAULT_UNREAL_CATALOG, generate_execution_plan
from planning.m12.verification import verify_semantic_target
from planning.unreal_transport_contract import UnrealTransportRequest, UnrealTransportResponse
from tests.extraction_payload_fixtures import actor_state_tree, response as fixture_response


def _task_plan():
    task = DEFAULT_UNREAL_CATALOG.resolve(
        "unreal.sequence-configure",
        {
            "twin_id": "twin-1",
            "sequence_name": "main",
            "frame_start": 1,
            "frame_end": 24,
        },
        digital_twin_id="twin-1",
    )
    return task, generate_execution_plan(task)


def _pair(request_id="req-fixture-1"):
    request = UnrealTransportRequest(
        request_id=request_id,
        operation_name="extract_actor_state",
        capability="state-extraction",
        kind="actor_state",
        arguments={},
        entity_ids=("FIELD_SURFACE",),
        authorization_id="auth-test",
    )
    raw = fixture_response(
        tree=actor_state_tree(),
        request_id=request_id,
        entity_ids=["FIELD_SURFACE"],
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


def test_source_content_digest_binds_plan_to_exact_task():
    task, plan = _task_plan()
    object.__setattr__(plan, "source_content_digest", "0" * 64)
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[_pair()],
    )
    assert result.failure_codes == ("IDENTITY_MISMATCH",)


def test_twin_identity_binding_is_checked_independently_of_render_evidence():
    task, plan = _task_plan()
    object.__setattr__(plan, "digital_twin_id", "different-twin")
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[_pair()],
    )
    assert result.failure_codes == ("IDENTITY_MISMATCH",)


def test_source_target_set_must_equal_plan_requirement_union():
    task, plan = _task_plan()
    step = plan.steps[0]
    original = step.verification_requirements
    object.__setattr__(step, "verification_requirements", original[1:])
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[_pair()],
    )
    assert result.failure_codes == ("INCOMPLETE_REQUIRED_INVARIANT_SET",)


def test_plan_cannot_add_unrequested_verification_requirement():
    task, plan = _task_plan()
    step = plan.steps[0]
    object.__setattr__(
        step,
        "verification_requirements",
        tuple(step.verification_requirements) + ("caller-added",),
    )
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[_pair()],
    )
    assert result.failure_codes == ("EXTRA_PLAN_VERIFICATION_REQUIREMENT",)


def test_render_flag_cannot_override_digest_bound_source_classification():
    task, plan = _task_plan()
    object.__setattr__(plan, "render_plan", True)
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[_pair()],
    )
    assert result.failure_codes == ("PLAN_RENDER_CLASSIFICATION_MISMATCH",)


def test_plan_identity_is_recomputed_against_source_and_steps():
    task, plan = _task_plan()
    object.__setattr__(plan, "plan_id", "forged-plan-id")
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[_pair()],
    )
    assert result.failure_codes == ("IDENTITY_MISMATCH",)
