"""Unit coverage for the existing material-variant execution path."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner
from planning.unreal_transport_contract import UnrealTransportResponse


class MaterialRecordingTransport:
    def __init__(self):
        self.requests = []
        self.material_variant = None

    def send(self, request):
        self.requests.append(request)
        if request.operation_name == "apply_material_variant":
            self.material_variant = dict(request.arguments["material_variant"])
        observed_variant = self.material_variant or {"name": "default"}
        observed_state = {
            "FIELD_SURFACE": {
                "material": {"variant": observed_variant},
                "location": {"x": 0.0, "y": 0.0, "z": 0.0},
            }
        }
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=True,
            observed_state=observed_state,
            error="",
            source="test-unreal-material-variant",
        )


def _intent():
    return UnrealTaskIntent(
        "material-variant-test",
        "apply material variant",
        ("FIELD_SURFACE",),
    )


def test_material_variant_plan_has_read_write_verify_shape():
    plan = UnrealTaskPlanner().plan_material_variant(_intent())
    assert [operation.kind for operation in plan.operations] == [
        UnrealOperationKind.READ,
        UnrealOperationKind.READ,
        UnrealOperationKind.WRITE,
        UnrealOperationKind.VERIFY,
    ]
    assert [operation.name for operation in plan.operations] == [
        "inspect_target_actors",
        "inspect_material_state",
        "apply_material_variant",
        "verify_material_variant",
    ]
    assert plan.operations[2].capability is UnrealCapability.MATERIAL
    assert plan.operations[3].capability is UnrealCapability.MATERIAL


def test_material_variant_executor_preserves_operation_order_and_authorization():
    planner = UnrealTaskPlanner()
    intent = _intent()
    plan = planner.plan_material_variant(intent)
    # The current planner schema deliberately leaves the variant payload
    # unspecified; this test exercises the executor with an explicit write
    # operation matching the existing capability contract.
    operations = list(plan.operations)
    operations[2] = UnrealOperation(
        capability=UnrealCapability.MATERIAL,
        kind=UnrealOperationKind.WRITE,
        name="apply_material_variant",
        arguments={
            "entity_ids": ("FIELD_SURFACE",),
            "material_variant": {"name": "liquid_surface"},
        },
        entity_ids=("FIELD_SURFACE",),
    )
    plan = UnrealTaskPlan(plan.intent_id, tuple(operations))

    transport = MaterialRecordingTransport()
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))
    result = executor.execute(plan, "material-variant-auth")

    assert result.success is True
    assert [e.operation_name for e in result.evidence_ledger] == [
        "inspect_target_actors",
        "inspect_material_state",
        "apply_material_variant",
        "verify_material_variant",
    ]
    # VERIFY is semantic at the Atlas evidence layer but uses the existing
    # read-only material-state wire operation on the adapter boundary.
    assert [request.operation_name for request in transport.requests] == [
        "inspect_target_actors",
        "inspect_material_state",
        "apply_material_variant",
        "verify_material_variant",
    ]
    assert all(request.authorization_id == "material-variant-auth" for request in transport.requests)


def test_material_variant_write_requires_immediate_verification():
    planner = UnrealTaskPlanner()
    intent = _intent()
    plan = planner.plan_material_variant(intent)
    invalid = UnrealTaskPlan(plan.intent_id, plan.operations[:-1])
    transport = MaterialRecordingTransport()
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport))

    with pytest.raises(UnrealPlanExecutionError, match="must be followed by verification"):
        executor.execute(invalid, "material-invalid-auth")

    assert transport.requests == []
