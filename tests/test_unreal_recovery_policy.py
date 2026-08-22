from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_executor import UnrealPlanExecutionFailure
from planning.unreal_recovery_policy import (
    UnrealFailureClass,
    UnrealRecoveryDisposition,
    assess_unreal_failure,
)


def _failure(operation_name, completed=(), operation_entity_ids=()):
    return UnrealPlanExecutionFailure(
        intent_id="intent-recovery-test",
        operation_index=len(completed),
        operation_name=operation_name,
        completed_evidence=tuple(completed),
        error="test failure",
        operation_entity_ids=tuple(operation_entity_ids),
    )


def _inspection_evidence(entity_ids=("FIELD_SURFACE",)):
    return UnrealEvidence(
        operation_name="inspect_target_actors",
        entity_ids=tuple(entity_ids),
        observed_state={entity_id: {} for entity_id in entity_ids},
        source="test-unreal",
    )


def _write_evidence(entity_ids=("FIELD_SURFACE",)):
    return UnrealEvidence(
        operation_name="set_actor_location",
        entity_ids=tuple(entity_ids),
        observed_state={entity_id: {"location": {"x": 1, "y": 2, "z": 3}} for entity_id in entity_ids},
        source="test-unreal",
    )


def test_location_write_failure_is_state_uncertain_and_requires_reassessment():
    assessment = assess_unreal_failure(
        _failure("set_actor_location", (_inspection_evidence(),))
    )

    assert assessment.failure_class is UnrealFailureClass.MUTATION_FAILURE
    assert assessment.disposition is UnrealRecoveryDisposition.REASSESS_STATE
    assert assessment.state_uncertain is True
    assert assessment.requires_fresh_evidence is True
    assert assessment.target_entity_ids == ("FIELD_SURFACE",)
    assert assessment.retry_authorized is False
    assert assessment.mutation_authorized is False


def test_location_write_failure_preserves_targets_without_completed_evidence():
    assessment = assess_unreal_failure(
        _failure("set_actor_location", operation_entity_ids=("FIELD_SURFACE",))
    )

    assert assessment.failure_class is UnrealFailureClass.MUTATION_FAILURE
    assert assessment.disposition is UnrealRecoveryDisposition.REASSESS_STATE
    assert assessment.state_uncertain is True
    assert assessment.requires_fresh_evidence is True
    assert assessment.target_entity_ids == ("FIELD_SURFACE",)
    assert assessment.retry_authorized is False
    assert assessment.mutation_authorized is False


def test_post_write_verification_failure_requires_reassessment():
    assessment = assess_unreal_failure(
        _failure(
            "verify_target_actor_mapping",
            (_inspection_evidence(), _write_evidence()),
            operation_entity_ids=("FIELD_SURFACE",),
        )
    )

    assert assessment.failure_class is UnrealFailureClass.POST_WRITE_VERIFICATION_FAILURE
    assert assessment.disposition is UnrealRecoveryDisposition.REASSESS_STATE
    assert assessment.state_uncertain is True
    assert assessment.requires_fresh_evidence is True
    assert assessment.target_entity_ids == ("FIELD_SURFACE",)
    assert assessment.retry_authorized is False
    assert assessment.mutation_authorized is False


def test_observation_failure_halts_without_claiming_mutation_state():
    assessment = assess_unreal_failure(_failure("inspect_target_actors"))

    assert assessment.failure_class is UnrealFailureClass.OBSERVATION_FAILURE
    assert assessment.disposition is UnrealRecoveryDisposition.HALT
    assert assessment.state_uncertain is False
    assert assessment.requires_fresh_evidence is False
    assert assessment.retry_authorized is False
    assert assessment.mutation_authorized is False


def test_unknown_failure_halts_fail_closed():
    assessment = assess_unreal_failure(_failure("future_unreal_operation"))

    assert assessment.failure_class is UnrealFailureClass.UNKNOWN_FAILURE
    assert assessment.disposition is UnrealRecoveryDisposition.HALT
    assert assessment.state_uncertain is True
    assert assessment.retry_authorized is False
    assert assessment.mutation_authorized is False


def test_inconsistent_completed_targets_are_rejected():
    failure = _failure(
        "verify_target_actor_mapping",
        (_inspection_evidence(("FIELD_SURFACE",)), _write_evidence(("OTHER_ACTOR",))),
        operation_entity_ids=("FIELD_SURFACE",),
    )

    try:
        assess_unreal_failure(failure)
    except ValueError as exc:
        assert "inconsistent recovery targets" in str(exc)
    else:
        raise AssertionError("inconsistent recovery targets must fail closed")
