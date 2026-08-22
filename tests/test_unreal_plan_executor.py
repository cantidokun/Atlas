from dataclasses import dataclass

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
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
            source="test-unreal",
        )


def _location_operation(location):
    return UnrealOperation(
        capability=UnrealCapability.MODIFY_ACTOR,
        kind=UnrealOperationKind.WRITE,
        name="set_actor_location",
        arguments={
            "entity_ids": ("FIELD_SURFACE",),
            "location": location,
        },
        entity_ids=("FIELD_SURFACE",),
    )


def _verify_operation():
    return UnrealOperation(
        capability=UnrealCapability.INSPECT_ACTOR,
        kind=UnrealOperationKind.VERIFY,
        name="verify_target_actor_mapping",
        arguments={"entity_ids": ("FIELD_SURFACE",)},
        entity_ids=("FIELD_SURFACE",),
    )


def test_executor_preserves_actor_location_payload():
    transport = RecordingTransport({"FIELD_SURFACE": {"location": {"x": 1, "y": 2, "z": 3}}})
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    plan = UnrealTaskPlan(
        "location-write",
        (_location_operation({"x": 1.0, "y": 2.0, "z": 3.0}), _verify_operation()),
    )

    result = executor.execute(plan, "auth-location-001")

    assert result.success is True
    assert transport.requests[0].arguments["location"] == {"x": 1.0, "y": 2.0, "z": 3.0}
    assert transport.requests[0].authorization_id == "auth-location-001"


def test_executor_rejects_malformed_actor_location_before_transport():
    transport = RecordingTransport({})
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    plan = UnrealTaskPlan(
        "location-write",
        (_location_operation({"x": 1.0, "y": 2.0}), _verify_operation()),
    )

    with pytest.raises(UnrealPlanExecutionError, match="location must contain exactly x, y, and z"):
        executor.execute(plan, "auth-location-002")

    assert transport.requests == []


def test_executor_rejects_unverified_write():
    transport = RecordingTransport({"FIELD_SURFACE": {"location": {"x": 1, "y": 2, "z": 3}}})
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    plan = UnrealTaskPlan(
        "location-write-unverified",
        (_location_operation({"x": 1.0, "y": 2.0, "z": 3.0}),),
    )

    with pytest.raises(UnrealPlanExecutionError, match="must be followed by verification"):
        executor.execute(plan, "auth-location-003")

    assert transport.requests == []


def test_executor_rejects_write_with_wrong_verification_targets():
    transport = RecordingTransport({"FIELD_SURFACE": {"location": {"x": 10, "y": 20, "z": 30}}})
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    wrong_target_verify = UnrealOperation(
        capability=UnrealCapability.INSPECT_ACTOR,
        kind=UnrealOperationKind.VERIFY,
        name="verify_target_actor_mapping",
        arguments={"entity_ids": ("OTHER_ACTOR",)},
        entity_ids=("OTHER_ACTOR",),
    )
    plan = UnrealTaskPlan(
        "location-write-wrong-target",
        (_location_operation({"x": 10.0, "y": 20.0, "z": 30.0}), wrong_target_verify),
    )

    with pytest.raises(UnrealPlanExecutionError, match="must target the same entities"):
        executor.execute(plan, "auth-location-004")

    assert transport.requests == []


def test_executor_verifies_actor_location_after_write():
    target = {"x": 10.0, "y": 20.0, "z": 30.0}
    transport = RecordingTransport({"FIELD_SURFACE": {"location": target}})
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    plan = UnrealTaskPlan(
        "location-write-verify",
        (_location_operation(target), _verify_operation()),
    )

    result = executor.execute(plan, "auth-location-005")

    assert result.success is True
    assert len(result.evidence_ledger) == 2
    assert [request.operation_name for request in transport.requests] == [
        "set_actor_location",
        "verify_target_actor_mapping",
    ]


def test_executor_rejects_post_write_location_mismatch():
    requested = {"x": 10.0, "y": 20.0, "z": 30.0}
    observed = {"x": 10.0, "y": 20.5, "z": 30.0}
    transport = RecordingTransport({"FIELD_SURFACE": {"location": observed}})
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    plan = UnrealTaskPlan(
        "location-write-mismatch",
        (_location_operation(requested), _verify_operation()),
    )

    with pytest.raises(UnrealPlanExecutionError, match="does not match expected"):
        executor.execute(plan, "auth-location-006")

    assert len(transport.requests) == 2
