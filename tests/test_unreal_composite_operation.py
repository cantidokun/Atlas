import pytest

from planning.unreal_composite_operation import build_composite_actor_operation


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
