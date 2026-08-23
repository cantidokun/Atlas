import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlan
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
            source="test-unreal-authorization",
        )


def _plan(location=(10.0, 20.0, 30.0)):
    target = {"x": location[0], "y": location[1], "z": location[2]}
    write = UnrealOperation(
        capability=UnrealCapability.MODIFY_ACTOR,
        kind=UnrealOperationKind.WRITE,
        name="set_actor_location",
        arguments={"entity_ids": ("FIELD_SURFACE",), "location": target},
        entity_ids=("FIELD_SURFACE",),
    )
    verify = UnrealOperation(
        capability=UnrealCapability.MODIFY_ACTOR,
        kind=UnrealOperationKind.VERIFY,
        name="verify_actor_location",
        arguments={"entity_ids": ("FIELD_SURFACE",), "expected_location": target},
        entity_ids=("FIELD_SURFACE",),
    )
    return UnrealTaskPlan("replacement-plan", (write, verify))


def test_authorization_binds_exact_plan():
    plan = _plan()
    authorization = UnrealPlanAuthorization.issue(plan, "replacement-auth-001")

    assert authorization.matches(plan) is True
    assert authorization.authorization_id == "replacement-auth-001"
    assert authorization.snapshot()["plan_digest"] == authorization.plan_digest


def test_authorization_rejects_modified_plan_before_transport():
    authorized_plan = _plan((10.0, 20.0, 30.0))
    changed_plan = _plan((11.0, 20.0, 30.0))
    authorization = UnrealPlanAuthorization.issue(authorized_plan, "replacement-auth-002")
    transport = RecordingTransport()
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))

    with pytest.raises(UnrealPlanExecutionError, match="does not match the exact Unreal task plan"):
        executor.execute_authorized(changed_plan, authorization)

    assert transport.requests == []


def test_authorized_execution_propagates_receipt_authorization_id():
    plan = _plan()
    authorization = UnrealPlanAuthorization.issue(plan, "replacement-auth-003")
    transport = RecordingTransport()
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))

    result = executor.execute_authorized(plan, authorization)

    assert result.success is True
    assert len(transport.requests) == 2
    assert all(request.authorization_id == "replacement-auth-003" for request in transport.requests)


def test_authorized_execution_rejects_wrong_receipt_type():
    plan = _plan()
    transport = RecordingTransport()
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))

    with pytest.raises(TypeError, match="UnrealPlanAuthorization"):
        executor.execute_authorized(plan, object())

    assert transport.requests == []


def test_authorization_digest_changes_when_operation_arguments_change():
    first = UnrealPlanAuthorization.issue(_plan((10.0, 20.0, 30.0)), "replacement-auth-004")
    second = UnrealPlanAuthorization.issue(_plan((10.0, 20.0, 31.0)), "replacement-auth-004")

    assert first.plan_digest != second.plan_digest
    assert first.matches(_plan((10.0, 20.0, 31.0))) is False
