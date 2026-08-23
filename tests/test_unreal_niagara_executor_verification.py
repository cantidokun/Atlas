import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlanner


class FakeNiagaraAdapter(UnrealAdapterProduction):
    def __init__(self, variant):
        super().__init__(transport=object(), source_tag="niagara-test")
        self.variant = variant

    def inspect(self, operation, authorization_id):
        return self._evidence(operation)

    def apply_authorized(self, operation, authorization_id):
        self.variant = operation.arguments["niagara_variant"]["name"]
        return self._evidence(operation)

    def verify(self, operation, authorization_id):
        return self._evidence(operation)

    def _evidence(self, operation):
        return UnrealEvidence(
            operation_name=operation.name,
            entity_ids=tuple(operation.entity_ids),
            observed_state={"FIELD_SURFACE": {"niagara": {"name": self.variant}}},
            source="fake-unreal",
            verified=False,
        )


def _intent(intent_id):
    return UnrealTaskIntent(intent_id, "Niagara executor semantic verification", ("FIELD_SURFACE",))


def test_executor_semantically_verifies_niagara_variant_after_write():
    result = UnrealPlanExecutor(FakeNiagaraAdapter("default")).execute(
        UnrealTaskPlanner().plan_niagara_variant(_intent("niagara-proof"), {"name": "sparks"}),
        "niagara-proof-auth",
    )
    assert result.success is True
    assert result.evidence_ledger[-1].observed_state["FIELD_SURFACE"]["niagara"]["name"] == "sparks"


def test_executor_fails_when_post_write_niagara_variant_does_not_match_target():
    target = {"name": "sparks"}
    adapter = FakeNiagaraAdapter("default")
    original_apply = adapter.apply_authorized

    def apply_without_requested_state(operation, authorization_id):
        evidence = original_apply(operation, authorization_id)
        adapter.variant = "default"
        return evidence

    adapter.apply_authorized = apply_without_requested_state
    with pytest.raises(UnrealPlanExecutionError, match="niagara name") as exc_info:
        UnrealPlanExecutor(adapter).execute(
            UnrealTaskPlanner().plan_niagara_variant(_intent("niagara-fail"), target),
            "niagara-fail-auth",
        )
    assert exc_info.value.failure.operation_name == "verify_niagara_variant"
    assert len(exc_info.value.failure.completed_evidence) == 3
