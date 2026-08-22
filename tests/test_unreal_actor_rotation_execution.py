"""Unit coverage for explicit actor-rotation execution."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner
from planning.unreal_transport_contract import UnrealTransportResponse


class RotationRecordingTransport:
    def __init__(self):
        self.requests = []
        self.rotation = {"pitch": 0.0, "yaw": 0.0, "roll": 0.0}

    def send(self, request):
        self.requests.append(request)
        if request.operation_name == "set_actor_rotation":
            self.rotation = dict(request.arguments["rotation"])
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=True,
            observed_state={
                "FIELD_SURFACE": {
                    "location": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "rotation": dict(self.rotation),
                }
            },
            error="",
            source="test-unreal-actor-rotation",
        )


def _intent():
    return UnrealTaskIntent("actor-rotation-test", "rotate actor", ("FIELD_SURFACE",))


def _rotation():
    return {"pitch": 12.0, "yaw": 47.5, "roll": -8.0}


def test_actor_rotation_plan_has_read_write_verify_shape_and_payload():
    plan = UnrealTaskPlanner().plan_actor_rotation_write(_intent(), _rotation())

    assert [operation.kind for operation in plan.operations] == [
        UnrealOperationKind.READ,
        UnrealOperationKind.WRITE,
        UnrealOperationKind.VERIFY,
    ]
    assert [operation.name for operation in plan.operations] == [
        "inspect_target_actors",
        "set_actor_rotation",
        "verify_target_actor_mapping",
    ]
    assert plan.operations[1].capability is UnrealCapability.MODIFY_ACTOR
    assert plan.operations[1].arguments["rotation"] == _rotation()


def test_actor_rotation_planner_rejects_invalid_payloads():
    planner = UnrealTaskPlanner()
    with pytest.raises(TypeError, match="rotation must be a mapping"):
        planner.plan_actor_rotation_write(_intent(), None)
    with pytest.raises(ValueError, match="exactly pitch, yaw, and roll"):
        planner.plan_actor_rotation_write(_intent(), {"pitch": 1.0})
    with pytest.raises(TypeError, match="rotation angles must be numeric"):
        planner.plan_actor_rotation_write(_intent(), {"pitch": True, "yaw": 2.0, "roll": 3.0})


def test_actor_rotation_executor_preserves_order_and_authorization():
    plan = UnrealTaskPlanner().plan_actor_rotation_write(_intent(), _rotation())
    transport = RotationRecordingTransport()
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))

    result = executor.execute(plan, "actor-rotation-auth")

    assert result.success is True
    assert [e.operation_name for e in result.evidence_ledger] == [
        "inspect_target_actors",
        "set_actor_rotation",
        "verify_target_actor_mapping",
    ]
    assert [request.operation_name for request in transport.requests] == [
        "inspect_target_actors",
        "set_actor_rotation",
        "inspect_target_actors",
    ]
    assert all(request.authorization_id == "actor-rotation-auth" for request in transport.requests)
    assert result.evidence_ledger[2].observed_state["FIELD_SURFACE"]["rotation"] == pytest.approx(_rotation())


def test_actor_rotation_write_requires_immediate_verification():
    planner = UnrealTaskPlanner()
    plan = planner.plan_actor_rotation_write(_intent(), _rotation())
    invalid = UnrealTaskPlan(plan.intent_id, plan.operations[:-1])
    transport = RotationRecordingTransport()
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))

    with pytest.raises(UnrealPlanExecutionError, match="must be followed by verification"):
        executor.execute(invalid, "actor-rotation-invalid-auth")

    assert transport.requests == []
