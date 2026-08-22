import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_contract import UnrealTransportResponse


class RecordingTransport:
    def __init__(self):
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=True,
            observed_state={"FIELD_SURFACE": {"location": {"x": 10.0, "y": 20.0, "z": 30.0}}},
            error="",
            source="test-unreal-compound-authorization",
        )


def _intent(intent_id="compound-auth"):
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="compound authorization test",
        target_entity_ids=("FIELD_SURFACE",),
    )


def test_authorization_binds_the_complete_composed_plan():
    planner = UnrealTaskPlanner()
    intent = _intent()
    composed = planner.compose_plans(
        intent,
        (
            planner.plan_inspection(intent),
            planner.plan_actor_location_write(intent, {"x": 11.0, "y": 22.0, "z": 33.0}),
        ),
    )

    authorization = UnrealPlanAuthorization.issue(composed, "compound-auth-001")

    assert authorization.matches(composed) is True
    assert len(composed.operations) == 5
    assert authorization.snapshot()["authorization_id"] == "compound-auth-001"


def test_compound_authorization_rejects_any_changed_subplan_operation_before_transport():
    planner = UnrealTaskPlanner()
    intent = _intent()
    authorized = planner.compose_plans(
        intent,
        (
            planner.plan_inspection(intent),
            planner.plan_actor_location_write(intent, {"x": 11.0, "y": 22.0, "z": 33.0}),
        ),
    )
    changed = planner.compose_plans(
        intent,
        (
            planner.plan_inspection(intent),
            planner.plan_actor_location_write(intent, {"x": 12.0, "y": 22.0, "z": 33.0}),
        ),
    )
    authorization = UnrealPlanAuthorization.issue(authorized, "compound-auth-002")
    transport = RecordingTransport()
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))

    with pytest.raises(UnrealPlanExecutionError, match="does not match the exact Unreal task plan"):
        executor.execute_authorized(changed, authorization)

    assert transport.requests == []


def test_compound_authorized_execution_propagates_one_receipt_id_to_every_operation():
    planner = UnrealTaskPlanner()
    intent = _intent()
    composed = planner.compose_plans(
        intent,
        (
            planner.plan_inspection(intent),
            planner.plan_actor_location_write(intent, {"x": 11.0, "y": 22.0, "z": 33.0}),
        ),
    )
    authorization = UnrealPlanAuthorization.issue(composed, "compound-auth-003")
    transport = RecordingTransport()
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))

    result = executor.execute_authorized(composed, authorization)

    assert result.success is True
    assert len(result.evidence_ledger) == 5
    assert [request.operation_name for request in transport.requests] == [
        "inspect_target_actors",
        "verify_target_actor_mapping",
        "inspect_target_actors",
        "set_actor_location",
        "inspect_target_actors",
    ]
    assert all(request.authorization_id == "compound-auth-003" for request in transport.requests)
