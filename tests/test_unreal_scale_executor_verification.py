import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlanner


class FakeScaleAdapter(UnrealAdapterProduction):
    def __init__(self, scale):
        super().__init__(transport=object(), source_tag="scale-test")
        self.scale = dict(scale)

    def inspect(self, operation, authorization_id):
        return self._evidence(operation)

    def apply_authorized(self, operation, authorization_id):
        self.scale = dict(operation.arguments["scale"])
        return self._evidence(operation)

    def verify(self, operation, authorization_id):
        return self._evidence(operation)

    def _evidence(self, operation):
        return UnrealEvidence(
            operation_name=operation.name,
            entity_ids=tuple(operation.entity_ids),
            observed_state={"FIELD_SURFACE": {"scale": dict(self.scale)}},
            source="fake-unreal",
            verified=False,
        )


def _intent(intent_id):
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="scale executor semantic verification",
        target_entity_ids=("FIELD_SURFACE",),
    )


def test_executor_semantically_verifies_actor_scale_after_write():
    target = {"x": 1.25, "y": 0.75, "z": 2.0}
    result = UnrealPlanExecutor(FakeScaleAdapter(target)).execute(
        UnrealTaskPlanner().plan_actor_scale_write(_intent("scale-proof"), target),
        "scale-proof-auth",
    )
    assert result.success is True
    assert result.evidence_ledger[-1].observed_state["FIELD_SURFACE"]["scale"] == target


def test_executor_fails_when_post_write_scale_does_not_match_target():
    target = {"x": 1.25, "y": 0.75, "z": 2.0}
    adapter = FakeScaleAdapter({"x": 1.0, "y": 1.0, "z": 1.0})
    original_apply = adapter.apply_authorized

    def apply_without_requested_state(operation, authorization_id):
        evidence = original_apply(operation, authorization_id)
        adapter.scale = {"x": 1.0, "y": 1.0, "z": 1.0}
        return evidence

    adapter.apply_authorized = apply_without_requested_state

    with pytest.raises(UnrealPlanExecutionError, match="scale") as exc_info:
        UnrealPlanExecutor(adapter).execute(
            UnrealTaskPlanner().plan_actor_scale_write(_intent("scale-fail"), target),
            "scale-fail-auth",
        )

    assert exc_info.value.failure.operation_name == "verify_target_actor_mapping"
    assert len(exc_info.value.failure.completed_evidence) == 2
