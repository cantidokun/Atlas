import pytest

from planning.unreal_agent import UnrealOperationKind, UnrealTaskIntent
from planning.unreal_task_planner import UnrealTaskPlanner


def _intent(intent_id="material-plan"):
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="material variant planning",
        target_entity_ids=("FIELD_SURFACE",),
    )


def test_material_plan_is_inspect_write_verify():
    plan = UnrealTaskPlanner().plan_material_variant(_intent(), {"name": "blue"})
    assert [operation.name for operation in plan.operations] == [
        "inspect_target_actors",
        "inspect_material_state",
        "apply_material_variant",
        "verify_material_variant",
    ]
    assert [operation.kind for operation in plan.operations] == [
        UnrealOperationKind.READ,
        UnrealOperationKind.READ,
        UnrealOperationKind.WRITE,
        UnrealOperationKind.VERIFY,
    ]


def test_material_plan_rejects_extra_variant_settings():
    with pytest.raises(ValueError, match="exactly name"):
        UnrealTaskPlanner().plan_material_variant(
            _intent(),
            {"name": "blue", "slot": "body"},
        )
