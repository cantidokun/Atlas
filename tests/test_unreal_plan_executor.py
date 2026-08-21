from dataclasses import dataclass

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_evidence_contract import UnrealEvidence
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


def test_executor_preserves_actor_location_payload():
    transport = RecordingTransport({"FIELD_SURFACE": {"location": {"x": 1, "y": 2, "z": 3}}})
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    plan = UnrealTaskPlan("location-write", (_location_operation({"x": 1.0, "y": 2.0, "z": 3.0}),))

    result = executor.execute(plan, "auth-location-001")

    assert result.success is True
    assert transport.requests[0].arguments["location"] == {"x": 1.0, "y": 2.0, "z": 3.0}
    assert transport.requests[0].authorization_id == "auth-location-001"


def test_executor_rejects_malformed_actor_location_before_transport():
    transport = RecordingTransport({})
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    plan = UnrealTaskPlan("location-write", (_location_operation({"x": 1.0, "y": 2.0}),))

    with pytest.raises(UnrealPlanExecutionError, match="location must contain exactly x, y, and z"):
        executor.execute(plan, "auth-location-002")

    assert transport.requests == []
