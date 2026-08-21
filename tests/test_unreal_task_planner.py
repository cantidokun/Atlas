import pytest

from planning.unreal_agent import UnrealCapability, UnrealOperationKind, UnrealTaskIntent
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


def test_actor_location_write_is_inspect_write_verify():
    plan = UnrealTaskPlanner().plan_actor_location_write(
        UnrealTaskIntent("move-1", "move field surface", ("FIELD_SURFACE",)),
        {"x": 100.0, "y": 200.0, "z": 300.0},
    )
    assert [op.kind for op in plan.operations] == [
        UnrealOperationKind.READ,
        UnrealOperationKind.WRITE,
        UnrealOperationKind.VERIFY,
    ]
    assert plan.operations[0].capability is UnrealCapability.INSPECT_ACTOR
    assert plan.operations[1].capability is UnrealCapability.MODIFY_ACTOR
    assert plan.operations[1].name == "set_actor_location"
    assert plan.operations[1].arguments == {
        "entity_ids": ("FIELD_SURFACE",),
        "location": {"x": 100.0, "y": 200.0, "z": 300.0},
    }
    assert plan.operations[2].capability is UnrealCapability.INSPECT_ACTOR


def test_actor_location_write_rejects_incomplete_location():
    with pytest.raises(ValueError, match="exactly x, y, and z"):
        UnrealTaskPlanner().plan_actor_location_write(
            UnrealTaskIntent("move-2", "move field surface", ("FIELD_SURFACE",)),
            {"x": 100.0, "y": 200.0},
        )


def test_actor_location_write_rejects_non_numeric_location():
    with pytest.raises(TypeError, match="coordinates must be numeric"):
        UnrealTaskPlanner().plan_actor_location_write(
            UnrealTaskIntent("move-3", "move field surface", ("FIELD_SURFACE",)),
            {"x": 100.0, "y": "200", "z": 300.0},
        )


def test_planner_requires_explicit_targets():
    intent = UnrealTaskIntent("bad-1", "modify something", ())
    with pytest.raises(ValueError):
        UnrealTaskPlanner().plan_material_variant(intent)
