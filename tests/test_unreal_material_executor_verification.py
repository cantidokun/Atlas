import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlanner


class FakeMaterialAdapter(UnrealAdapterProduction):
    def __init__(self, variant):
        super().__init__(transport=object(), source_tag="material-test")
        self.variant = variant

    def inspect(self, operation, authorization_id):
        return self._evidence(operation)

    def apply_authorized(self, operation, authorization_id):
        self.variant = operation.arguments["material_variant"]["name"]
        return self._evidence(operation)

    def verify(self, operation, authorization_id):
        return self._evidence(operation)

    def _evidence(self, operation):
        return UnrealEvidence(
            operation_name=operation.name,
            entity_ids=tuple(operation.entity_ids),
            observed_state={
                "FIELD_SURFACE": {
                    "material": {"variant": {"name": self.variant}},
                }
            },
            source="fake-unreal",
            verified=False,
        )


def _intent(intent_id):
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="material executor semantic verification",
        target_entity_ids=("FIELD_SURFACE",),
    )


def test_executor_semantically_verifies_material_variant_after_write():
    target = {"name": "blue"}
    result = UnrealPlanExecutor(FakeMaterialAdapter("default")).execute(
        UnrealTaskPlanner().plan_material_variant(_intent("material-proof"), target),
        "material-proof-auth",
    )
    assert result.success is True
    assert result.evidence_ledger[-1].observed_state["FIELD_SURFACE"]["material"]["variant"]["name"] == "blue"


def test_executor_fails_when_post_write_material_variant_does_not_match_target():
    target = {"name": "blue"}
    adapter = FakeMaterialAdapter("default")
    original_apply = adapter.apply_authorized

    def apply_without_requested_state(operation, authorization_id):
        evidence = original_apply(operation, authorization_id)
        adapter.variant = "default"
        return evidence

    adapter.apply_authorized = apply_without_requested_state

    with pytest.raises(UnrealPlanExecutionError, match="material variant") as exc_info:
        UnrealPlanExecutor(adapter).execute(
            UnrealTaskPlanner().plan_material_variant(_intent("material-fail"), target),
            "material-fail-auth",
        )

    assert exc_info.value.failure.operation_name == "verify_material_variant"
    assert len(exc_info.value.failure.completed_evidence) == 3
