from dataclasses import dataclass

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor, UnrealPlanExecutionFailure
from planning.unreal_task_planner import UnrealTaskPlan
from planning.unreal_transport_contract import UnrealTransportResponse


@dataclass
class RecordingTransport:
    response_state: dict

    def __post_init__(self):
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=True,
            observed_state=self.response_state,
            error="",
            source="test-unreal-reassessment",
        )


def _failure():
    return UnrealPlanExecutionFailure(
        intent_id="composite-live",
        operation_index=5,
        operation_name="verify_actor_location",
        completed_evidence=(),
        error="verification failed",
        operation_entity_ids=("FIELD_SURFACE",),
        operation_arguments={
            "entity_ids": ("FIELD_SURFACE",),
            "expected_location": {"x": 10.0, "y": 20.0, "z": 30.0},
        },
        completed_operation_arguments=(),
    )


def test_failure_reassessment_plan_is_read_only_and_targets_failed_entities():
    plan = _failure().reassessment_plan()

    assert plan.intent_id == "composite-live:reassess"
    assert [operation.name for operation in plan.operations] == [
        "inspect_target_actors",
        "verify_target_actor_mapping",
    ]
    assert all(operation.kind is not UnrealOperationKind.WRITE for operation in plan.operations)
    assert all(operation.capability is UnrealCapability.INSPECT_ACTOR for operation in plan.operations)
    assert all(operation.entity_ids == ("FIELD_SURFACE",) for operation in plan.operations)


def test_failure_reassessment_plan_requires_explicit_authorization_before_execution():
    failure = _failure()
    plan = failure.reassessment_plan()
    transport = RecordingTransport({
        "FIELD_SURFACE": {
            "entity_id": "FIELD_SURFACE",
            "actor_name": "FieldSurface",
            "actor_class": "Actor",
            "location": {"x": 11.0, "y": 20.0, "z": 30.0},
            "rotation": {"pitch": 0, "yaw": 0, "roll": 0},
            "scale": {"x": 1, "y": 1, "z": 1},
        }
    })
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))

    result = executor.execute(plan, "recovery-reassessment-auth")

    assert result.success is True
    assert [request.operation_name for request in transport.requests] == [
        "inspect_target_actors",
        "inspect_target_actors",
    ]
    assert [e.operation_name for e in result.evidence_ledger] == [
        "inspect_target_actors",
        "verify_target_actor_mapping",
    ]
    assert all(e.verified for e in result.evidence_ledger)


def test_failure_reassessment_plan_does_not_replay_failed_mutation():
    plan = _failure().reassessment_plan()

    assert all(operation.kind is not UnrealOperationKind.WRITE for operation in plan.operations)
    assert not any(operation.name == "set_actor_location" for operation in plan.operations)
    assert not any(operation.name == "apply_material_variant" for operation in plan.operations)
    assert not any(operation.name == "apply_niagara_variant" for operation in plan.operations)


def test_failure_reassessment_requires_entity_context():
    failure = UnrealPlanExecutionFailure(
        intent_id="no-target",
        operation_index=0,
        operation_name="set_actor_location",
        completed_evidence=(),
        error="failed",
    )

    try:
        failure.reassessment_plan()
    except ValueError as exc:
        assert str(exc) == "failure must contain operation_entity_ids for recovery reassessment"
    else:
        raise AssertionError("expected reassessment to reject missing entity context")
