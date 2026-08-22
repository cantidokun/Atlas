from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_executor import UnrealPlanExecutionFailure
from planning.unreal_recovery_policy import (
    UnrealFailureClass,
    UnrealRecoveryDisposition,
    assess_unreal_failure,
)


def _failure(operation_name, completed=()):
    return UnrealPlanExecutionFailure(
        intent_id="intent-recovery-test",
        operation_index=len(completed),
        operation_name=operation_name,
        completed_evidence=tuple(completed),
        error="test failure",
    )


def _write_evidence():
    return UnrealEvidence(
        operation_name="set_actor_location",
        entity_ids=("FIELD_SURFACE",),
        observed_state={"FIELD_SURFACE": {"location": {"x": 1, "y": 2, "z": 3}}},
        source="test-unreal",
    )


def test_location_write_failure_is_state_uncertain_and_requires_reassessment():
    assessment = assess_unreal_failure(_failure("set_actor_location"))

    assert assessment.failure_class is UnrealFailureClass.MUTATION_FAILURE
    assert assessment.disposition is UnrealRecoveryDisposition.REASSESS_STATE
    assert assessment.state_uncertain is True


def test_post_write_verification_failure_requires_reassessment():
    assessment = assess_unreal_failure(
        _failure("verify_target_actor_mapping", (_write_evidence(),))
    )

    assert assessment.failure_class is UnrealFailureClass.POST_WRITE_VERIFICATION_FAILURE
    assert assessment.disposition is UnrealRecoveryDisposition.REASSESS_STATE
    assert assessment.state_uncertain is True


def test_observation_failure_halts_without_claiming_mutation_state():
    assessment = assess_unreal_failure(_failure("inspect_target_actors"))

    assert assessment.failure_class is UnrealFailureClass.OBSERVATION_FAILURE
    assert assessment.disposition is UnrealRecoveryDisposition.HALT
    assert assessment.state_uncertain is False


def test_unknown_failure_halts_fail_closed():
    assessment = assess_unreal_failure(_failure("future_unreal_operation"))

    assert assessment.failure_class is UnrealFailureClass.UNKNOWN_FAILURE
    assert assessment.disposition is UnrealRecoveryDisposition.HALT
    assert assessment.state_uncertain is True
