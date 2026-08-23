from dataclasses import dataclass

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlan
from planning.unreal_transport_contract import UnrealTransportResponse


@dataclass
class VerificationTransport:
    observed_state: dict

    def send(self, request):
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=True,
            observed_state=self.observed_state,
            error="",
            source="test-unreal-verification",
        )


def test_successful_semantic_verification_marks_evidence_verified():
    location = {"x": 11.0, "y": 22.0, "z": 33.0}
    write = UnrealOperation(
        capability=UnrealCapability.MODIFY_ACTOR,
        kind=UnrealOperationKind.WRITE,
        name="set_actor_location",
        arguments={"entity_ids": ("FIELD_SURFACE",), "location": location},
        entity_ids=("FIELD_SURFACE",),
    )
    verify = UnrealOperation(
        capability=UnrealCapability.MODIFY_ACTOR,
        kind=UnrealOperationKind.VERIFY,
        name="verify_actor_location",
        arguments={"entity_ids": ("FIELD_SURFACE",), "expected_location": location},
        entity_ids=("FIELD_SURFACE",),
    )

    result = UnrealPlanExecutor(
        UnrealAdapterProduction(
            VerificationTransport({"FIELD_SURFACE": {"location": location}})
        )
    ).execute(UnrealTaskPlan("verification-contract", (write, verify)), "auth-verification-contract")

    assert result.success is True
    assert result.evidence_ledger[0].verified is False
    assert result.evidence_ledger[1].verified is True
