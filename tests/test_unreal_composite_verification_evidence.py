from dataclasses import dataclass

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealOperationKind, UnrealTaskIntent
from planning.unreal_composite_operation import build_composite_actor_operation
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_contract import UnrealTransportResponse


TARGET = "FIELD_SURFACE"


@dataclass
class CompositeVerificationTransport:
    state: dict

    def send(self, request):
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=True,
            observed_state=self.state,
            error="",
            source="test-unreal-composite-verification",
        )


def test_composite_marks_every_successful_verification_as_verified():
    state = {
        TARGET: {
            "location": {"x": 101.0, "y": 202.0, "z": 303.0},
            "rotation": {"pitch": 1.0, "yaw": 2.0, "roll": 3.0},
            "scale": {"x": 1.5, "y": 1.5, "z": 1.5},
            "material": {"variant": {"name": "liquid_surface"}},
            "niagara": {"variant": {"name": "goal_burst"}},
        }
    }
    intent = UnrealTaskIntent("composite-verification", "verify complete production state", (TARGET,))
    composite = build_composite_actor_operation(
        [TARGET],
        [
            {"name": "set_actor_location", "entity_ids": (TARGET,), "location": state[TARGET]["location"]},
            {"name": "set_actor_rotation", "entity_ids": (TARGET,), "rotation": state[TARGET]["rotation"]},
            {"name": "set_actor_scale", "entity_ids": (TARGET,), "scale": state[TARGET]["scale"]},
            {"name": "apply_material_variant", "entity_ids": (TARGET,), "variant": "liquid_surface"},
            {"name": "apply_niagara_variant", "entity_ids": (TARGET,), "variant": "goal_burst"},
        ],
    )

    plan = UnrealTaskPlanner().plan_composite_actor_production(intent, composite)
    result = UnrealPlanExecutor(
        UnrealAdapterProduction(CompositeVerificationTransport(state))
    ).execute(plan, "auth-composite-verification")

    assert result.success is True
    verification_evidence = [
        evidence
        for operation, evidence in zip(plan.operations, result.evidence_ledger)
        if operation.kind is UnrealOperationKind.VERIFY
    ]
    assert len(verification_evidence) == 5
    assert all(evidence.verified for evidence in verification_evidence)
