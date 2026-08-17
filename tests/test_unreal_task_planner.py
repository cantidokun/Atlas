import pytest

from planning.unreal_agent import UnrealOperationKind, UnrealTaskIntent
from planning.unreal_task_planner import UnrealTaskPlanner


def test_inspection_plan_is_read_then_verify():
    plan = UnrealTaskPlanner().plan_inspection(
        UnrealTaskIntent("inspect-1", "inspect left goal", ("GOAL_LEFT",))
    )
    assert [op.kind for op in plan.operations] == [
        UnrealOperationKind.READ,
        UnrealOperationKind.VERIFY,
    ]
    assert all(op.entity_ids == ("GOAL_LEFT",) for op in plan.operations)


def test_material_variant_is_inspect_write_verify():
    plan = UnrealTaskPlanner().plan_material_variant(
        UnrealTaskIntent("variant-1", "create liquid surface variant", ("FIELD_SURFACE",))
    )
    assert [op.kind for op in plan.operations] == [
        UnrealOperationKind.READ,
        UnrealOperationKind.READ,
        UnrealOperationKind.WRITE,
        UnrealOperationKind.VERIFY,
    ]
    assert plan.operations[2].name == "apply_material_variant"


def test_planner_requires_explicit_targets():
    intent = UnrealTaskIntent("bad-1", "modify something", ())
    with pytest.raises(ValueError):
        UnrealTaskPlanner().plan_material_variant(intent)
