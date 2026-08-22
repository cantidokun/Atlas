from dataclasses import dataclass

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_executor import UnrealPlanExecutionFailure, UnrealPlanExecutor
from planning.unreal_recovery_coordinator import UnrealRecoveryCoordinator
from planning.unreal_recovery_orchestrator import UnrealRecoveryPlan
from planning.unreal_recovery_policy import (
    UnrealFailureClass,
    UnrealRecoveryDisposition,
    assess_unreal_failure,
)
from planning.unreal_task_planner import UnrealTaskPlan
from planning.unreal_transport_contract import UnrealTransportResponse
from planning.unreal_reassessment_decision import UnrealReassessmentOutcome


@dataclass
class RecoveryTransport:
    observed_state: dict

    def __post_init__(self):
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=True,
            observed_state=self.observed_state,
            error="",
            source="test-recovery",
        )


def _failure(target_location):
    return UnrealPlanExecutionFailure(
        intent_id="recovery-coordinator",
        operation_index=2,
        operation_name="verify_target_actor_mapping",
        completed_evidence=(
            UnrealEvidence(
                operation_name="inspect_target_actors",
                entity_ids=("FIELD_SURFACE",),
                observed_state={
                    "FIELD_SURFACE": {"location": {"x": 0.0, "y": 0.0, "z": 0.0}}
                },
                source="test-recovery",
                verified=False,
            ),
            UnrealEvidence(
                operation_name="set_actor_location",
                entity_ids=("FIELD_SURFACE",),
                observed_state={"FIELD_SURFACE": {"location": target_location}},
                source="test-recovery",
                verified=False,
            ),
        ),
        error="simulated post-write verification failure",
        operation_entity_ids=("FIELD_SURFACE",),
        operation_arguments={"entity_ids": ("FIELD_SURFACE",)},
        completed_operation_arguments=(
            {"entity_ids": ("FIELD_SURFACE",)},
            {"entity_ids": ("FIELD_SURFACE",), "location": target_location},
        ),
    )


def test_coordinator_reassesses_post_write_failure_without_retrying_mutation():
    target = {"x": 10.0, "y": 20.0, "z": 30.0}
    transport = RecoveryTransport({"FIELD_SURFACE": {"location": target}})
    coordinator = UnrealRecoveryCoordinator(
        UnrealPlanExecutor(UnrealAdapterProduction(transport))
    )

    result = coordinator.reassess(_failure(target), "recovery-read-auth")

    assert result.assessment.failure_class is UnrealFailureClass.POST_WRITE_VERIFICATION_FAILURE
    assert result.assessment.disposition is UnrealRecoveryDisposition.REASSESS_STATE
    assert result.execution_result is not None
    assert result.decision is not None
    assert result.decision.outcome is UnrealReassessmentOutcome.CONFIRMED
    assert result.decision.retry_authorized is False
    assert result.decision.mutation_authorized is False
    assert [request.operation_name for request in transport.requests] == [
        "inspect_target_actors"
    ]
    assert all(request.kind == "read" for request in transport.requests)


def test_coordinator_reports_changed_state_without_authorizing_retry():
    target = {"x": 10.0, "y": 20.0, "z": 30.0}
    changed = {"x": 10.0, "y": 25.0, "z": 30.0}
    transport = RecoveryTransport({"FIELD_SURFACE": {"location": changed}})
    coordinator = UnrealRecoveryCoordinator(
        UnrealPlanExecutor(UnrealAdapterProduction(transport))
    )

    result = coordinator.reassess(_failure(target), "recovery-read-auth")

    assert result.decision is not None
    assert result.decision.outcome is UnrealReassessmentOutcome.STATE_CHANGED
    assert result.decision.retry_authorized is False
    assert result.decision.mutation_authorized is False
    assert [request.operation_name for request in transport.requests] == [
        "inspect_target_actors"
    ]


def test_coordinator_halts_observation_failure_without_transport_work():
    failure = UnrealPlanExecutionFailure(
        intent_id="recovery-observation-halt",
        operation_index=0,
        operation_name="inspect_target_actors",
        completed_evidence=(),
        error="simulated observation failure",
        operation_entity_ids=("FIELD_SURFACE",),
        operation_arguments={"entity_ids": ("FIELD_SURFACE",)},
    )
    transport = RecoveryTransport({})
    coordinator = UnrealRecoveryCoordinator(
        UnrealPlanExecutor(UnrealAdapterProduction(transport))
    )

    result = coordinator.reassess(failure, "recovery-read-auth")

    assert result.assessment.disposition is UnrealRecoveryDisposition.HALT
    assert result.execution_result is None
    assert result.decision is None
    assert transport.requests == []


def test_coordinator_rejects_reassessment_without_recoverable_mutation_intent():
    failure = UnrealPlanExecutionFailure(
        intent_id="recovery-missing-intent",
        operation_index=2,
        operation_name="verify_target_actor_mapping",
        completed_evidence=(
            UnrealEvidence(
                operation_name="inspect_target_actors",
                entity_ids=("FIELD_SURFACE",),
                observed_state={
                    "FIELD_SURFACE": {"location": {"x": 0.0, "y": 0.0, "z": 0.0}}
                },
                source="test-recovery",
                verified=False,
            ),
        ),
        error="simulated post-write verification failure",
        operation_entity_ids=("FIELD_SURFACE",),
        operation_arguments={"entity_ids": ("FIELD_SURFACE",)},
        completed_operation_arguments=({"entity_ids": ("FIELD_SURFACE",)},),
    )
    transport = RecoveryTransport({"FIELD_SURFACE": {"location": {"x": 0.0, "y": 0.0, "z": 0.0}}})
    coordinator = UnrealRecoveryCoordinator(
        UnrealPlanExecutor(UnrealAdapterProduction(transport))
    )

    with pytest.raises(ValueError, match="recoverable mutation location intent"):
        coordinator.reassess(failure, "recovery-read-auth")

    assert transport.requests == []


def test_coordinator_rejects_mutating_reassessment_plan_before_transport():
    target = {"x": 10.0, "y": 20.0, "z": 30.0}
    transport = RecoveryTransport({"FIELD_SURFACE": {"location": target}})

    class MaliciousOrchestrator:
        def plan(self, failure):
            return UnrealRecoveryPlan(
                assessment=assess_unreal_failure(failure),
                reassessment_plan=UnrealTaskPlan(
                    intent_id="malicious-reassess",
                    operations=(
                        UnrealOperation(
                            capability=UnrealCapability.MODIFY_ACTOR,
                            kind=UnrealOperationKind.WRITE,
                            name="set_actor_location",
                            arguments={"entity_ids": ("FIELD_SURFACE",), "location": target},
                            entity_ids=("FIELD_SURFACE",),
                        ),
                    ),
                ),
            )

    coordinator = UnrealRecoveryCoordinator(
        UnrealPlanExecutor(UnrealAdapterProduction(transport)),
        orchestrator=MaliciousOrchestrator(),
    )

    with pytest.raises(ValueError, match="reassessment plan must be read-only"):
        coordinator.reassess(_failure(target), "recovery-read-auth")

    assert transport.requests == []
