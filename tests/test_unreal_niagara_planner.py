import pytest

from planning.unreal_agent import UnrealOperationKind, UnrealTaskIntent
from planning.unreal_task_planner import UnrealTaskPlanner


def _intent(intent_id="niagara-plan"):
    return UnrealTaskIntent(intent_id=intent_id, description="Niagara variant planning", target_entity_ids=("FIELD_SURFACE",))


def test_niagara_plan_is_inspect_write_verify():
    plan = UnrealTaskPlanner().plan_niagara_variant(_intent(), {"name": "goal_burst"})
    assert [operation.name for operation in plan.operations] == ["inspect_target_actors", "inspect_niagara_state", "apply_niagara_variant", "verify_niagara_variant"]
    assert [operation.kind for operation in plan.operations] == [UnrealOperationKind.READ, UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY]


def test_niagara_plan_rejects_extra_variant_settings():
    with pytest.raises(ValueError, match="exactly name"):
        UnrealTaskPlanner().plan_niagara_variant(_intent(), {"name": "goal_burst", "enabled": True})
