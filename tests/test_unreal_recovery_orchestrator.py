import pytest

from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_plan_executor import UnrealPlanExecutionFailure
from planning.unreal_recovery_orchestrator import UnrealRecoveryOrchestrator
from planning.unreal_recovery_policy import (
    UnrealFailureClass,
    UnrealRecoveryDisposition,
)
from planning.unreal_evidence_contract import UnrealEvidence


def _failure(
    operation_name="set_actor_location",
    operation_entity_ids=("FIELD_SURFACE",),
    completed_evidence=(),
):
    return UnrealPlanExecutionFailure(
        intent_id="recovery-orchestration",
        operation_index=1,
        operation_name=operation_name,
        completed_evidence=tuple(completed_evidence),
        error="simulated failure",
        operation_entity_ids=operation_entity_ids,
    )


def test_mutation_failure_becomes_targeted_read_only_reassessment_plan():
    result = UnrealRecoveryOrchestrator().plan(_failure())

    assert result.assessment.failure_class is UnrealFailureClass.MUTATION_FAILURE
    assert result.assessment.disposition is UnrealRecoveryDisposition.REASSESS_STATE
    assert result.assessment.state_uncertain is True
    assert result.assessment.requires_fresh_evidence is True
    assert result.assessment.retry_authorized is False
    assert result.assessment.mutation_authorized is False

    plan = result.reassessment_plan
    assert plan is not None
    assert len(plan.operations) == 1
    operation = plan.operations[0]
    assert operation.kind is UnrealOperationKind.READ
    assert operation.capability is UnrealCapability.INSPECT_ACTOR
    assert operation.name == "inspect_target_actors"
    assert operation.entity_ids == ("FIELD_SURFACE",)
    assert operation.arguments["entity_ids"] == ("FIELD_SURFACE",)


def test_post_write_verification_failure_preserves_completed_write_targets():
    write_evidence = UnrealEvidence(
        operation_name="set_actor_location",
        entity_ids=("FIELD_SURFACE",),
        observed_state={"FIELD_SURFACE": {"location": {"x": 1.0, "y": 2.0, "z": 3.0}}},
        source="test-unreal",
        verified=False,
    )

    result = UnrealRecoveryOrchestrator().plan(
        _failure(
            operation_name="verify_target_actor_mapping",
            completed_evidence=(write_evidence,),
        )
    )

    assert result.assessment.failure_class is UnrealFailureClass.POST_WRITE_VERIFICATION_FAILURE
    assert result.assessment.state_uncertain is True
    assert result.assessment.target_entity_ids == ("FIELD_SURFACE",)
    assert result.reassessment_plan is not None
    assert result.reassessment_plan.operations[0].entity_ids == ("FIELD_SURFACE",)


def test_observation_failure_halts_without_creating_a_plan():
    result = UnrealRecoveryOrchestrator().plan(
        _failure(operation_name="inspect_target_actors")
    )

    assert result.assessment.failure_class is UnrealFailureClass.OBSERVATION_FAILURE
    assert result.assessment.disposition is UnrealRecoveryDisposition.HALT
    assert result.reassessment_plan is None
    assert result.assessment.retry_authorized is False
    assert result.assessment.mutation_authorized is False


def test_unknown_failure_halts_fail_closed():
    result = UnrealRecoveryOrchestrator().plan(
        _failure(operation_name="unexpected_operation")
    )

    assert result.assessment.failure_class is UnrealFailureClass.UNKNOWN_FAILURE
    assert result.assessment.disposition is UnrealRecoveryDisposition.HALT
    assert result.reassessment_plan is None
