import pytest

from planning.unreal_agent import UnrealOperationKind, UnrealTaskIntent
from planning.unreal_composite_operation import build_composite_actor_operation
from planning.unreal_task_planner import UnrealTaskPlanner


def test_composite_orders_existing_capabilities_deterministically():
    composite = build_composite_actor_operation(
        ["FIELD_SURFACE"],
        [
            {"name": "apply_niagara_variant", "entity_ids": ("FIELD_SURFACE",), "variant": "dust"},
            {"name": "set_actor_scale", "entity_ids": ("FIELD_SURFACE",), "scale": {"x": 2, "y": 2, "z": 2}},
            {"name": "set_actor_location", "entity_ids": ("FIELD_SURFACE",), "location": {"x": 1, "y": 2, "z": 3}},
            {"name": "apply_material_variant", "entity_ids": ("FIELD_SURFACE",), "variant": "wet"},
            {"name": "set_actor_rotation", "entity_ids": ("FIELD_SURFACE",), "rotation": {"pitch": 0, "yaw": 90, "roll": 0}},
        ],
    )
    assert [op["name"] for op in composite.ordered_operations()] == [
        "set_actor_location", "set_actor_rotation", "set_actor_scale",
        "apply_material_variant", "apply_niagara_variant",
    ]


def test_composite_rejects_unknown_transport_primitive():
    with pytest.raises(ValueError, match="unsupported composite operation"):
        build_composite_actor_operation(
            ["FIELD_SURFACE"],
            [{"name": "delete_actor", "entity_ids": ("FIELD_SURFACE",)}],
        )


def test_composite_rejects_entity_escape():
    with pytest.raises(ValueError, match="contained"):
        build_composite_actor_operation(
            ["FIELD_SURFACE"],
            [{"name": "set_actor_scale", "entity_ids": ("OTHER",), "scale": {"x": 1, "y": 1, "z": 1}}],
        )


def test_composite_planner_adds_immediate_semantic_verification_boundaries():
    intent = UnrealTaskIntent("composite-1", "prepare field production state", ("FIELD_SURFACE",))
    composite = build_composite_actor_operation(
        ["FIELD_SURFACE"],
        [
            {"name": "set_actor_location", "entity_ids": ("FIELD_SURFACE",), "location": {"x": 1, "y": 2, "z": 3}},
            {"name": "set_actor_rotation", "entity_ids": ("FIELD_SURFACE",), "rotation": {"pitch": 0, "yaw": 90, "roll": 0}},
            {"name": "set_actor_scale", "entity_ids": ("FIELD_SURFACE",), "scale": {"x": 2, "y": 2, "z": 2}},
            {"name": "apply_material_variant", "entity_ids": ("FIELD_SURFACE",), "variant": "wet"},
            {"name": "apply_niagara_variant", "entity_ids": ("FIELD_SURFACE",), "variant": "dust"},
        ],
    )
    plan = UnrealTaskPlanner().plan_composite_actor_production(intent, composite)
    names = [op.name for op in plan.operations]
    assert names == [
        "inspect_target_actors",
        "set_actor_location", "verify_actor_location",
        "set_actor_rotation", "verify_actor_rotation",
        "set_actor_scale", "verify_actor_scale",
        "inspect_material_state", "apply_material_variant", "verify_material_variant",
        "inspect_niagara_state", "apply_niagara_variant", "verify_niagara_variant",
    ]
    for index, operation in enumerate(plan.operations):
        if operation.kind is UnrealOperationKind.WRITE:
            assert plan.operations[index + 1].kind is UnrealOperationKind.VERIFY
            assert plan.operations[index + 1].entity_ids == operation.entity_ids
