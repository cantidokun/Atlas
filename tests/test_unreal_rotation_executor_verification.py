import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlanner


class FakeRotationAdapter(UnrealAdapterProduction):
    def __init__(self, rotation):
        super().__init__(transport=object(), source_tag="rotation-test")
        self.rotation = rotation

    def inspect(self, operation, authorization_id):
        return UnrealEvidence(
            operation_name=operation.name,
            entity_ids=tuple(operation.entity_ids),
            observed_state={"FIELD_SURFACE": {"rotation": dict(self.rotation)}},
            source="fake-unreal",
            verified=False,
        )

    def apply_authorized(self, operation, authorization_id):
        self.rotation = dict(operation.arguments["rotation"])
        return UnrealEvidence(
            operation_name=operation.name,
            entity_ids=tuple(operation.entity_ids),
            observed_state={"FIELD_SURFACE": {"rotation": dict(self.rotation)}},
            source="fake-unreal",
            verified=False,
        )

    def verify(self, operation, authorization_id):
        return UnrealEvidence(
            operation_name=operation.name,
            entity_ids=tuple(operation.entity_ids),
            observed_state={"FIELD_SURFACE": {"rotation": dict(self.rotation)}},
            source="fake-unreal",
            verified=False,
        )


def _intent(intent_id):
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="rotation executor semantic verification",
        target_entity_ids=("FIELD_SURFACE",),
    )


def test_executor_semantically_verifies_actor_rotation_after_write():
    target = {"pitch": 11.0, "yaw": 37.0, "roll": -9.0}
    adapter = FakeRotationAdapter(target)
    executor = UnrealPlanExecutor(adapter)

    result = executor.execute(
        UnrealTaskPlanner().plan_actor_rotation_write(_intent("rotation-proof"), target),
        "rotation-proof-auth",
    )

    assert result.success is True
    assert result.evidence_ledger[-1].observed_state["FIELD_SURFACE"]["rotation"] == target


def test_executor_fails_when_post_write_rotation_does_not_match_target():
    target = {"pitch": 11.0, "yaw": 37.0, "roll": -9.0}
    adapter = FakeRotationAdapter({"pitch": 0.0, "yaw": 0.0, "roll": 0.0})
    original_apply = adapter.apply_authorized

    def apply_without_requested_state(operation, authorization_id):
        evidence = original_apply(operation, authorization_id)
        adapter.rotation = {"pitch": 0.0, "yaw": 0.0, "roll": 0.0}
        return evidence

    adapter.apply_authorized = apply_without_requested_state
    executor = UnrealPlanExecutor(adapter)

    with pytest.raises(UnrealPlanExecutionError, match="rotation") as exc_info:
        executor.execute(
            UnrealTaskPlanner().plan_actor_rotation_write(_intent("rotation-fail"), target),
            "rotation-fail-auth",
        )

    assert exc_info.value.failure.operation_name == "verify_target_actor_mapping"
    assert len(exc_info.value.failure.completed_evidence) == 2
