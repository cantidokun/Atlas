import pytest

from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_composite_operation import build_composite_actor_operation
from planning.unreal_task_planner import UnrealTaskPlanner


def test_composite_uses_semantic_transform_verifiers():
    intent = UnrealTaskIntent("transform-verify", "verify transforms", ("FIELD_SURFACE",))
    composite = build_composite_actor_operation(
        ["FIELD_SURFACE"],
        [
            {"name": "set_actor_location", "entity_ids": ("FIELD_SURFACE",), "location": {"x": 1, "y": 2, "z": 3}},
            {"name": "set_actor_rotation", "entity_ids": ("FIELD_SURFACE",), "rotation": {"pitch": 0, "yaw": 90, "roll": 0}},
            {"name": "set_actor_scale", "entity_ids": ("FIELD_SURFACE",), "scale": {"x": 2, "y": 2, "z": 2}},
        ],
    )
    operations = UnrealTaskPlanner().plan_composite_actor_production(intent, composite).operations
    assert [op.name for op in operations] == [
        "inspect_target_actors",
        "set_actor_location", "verify_actor_location",
        "set_actor_rotation", "verify_actor_rotation",
        "set_actor_scale", "verify_actor_scale",
    ]
    assert operations[2].arguments["expected_location"] == {"x": 1, "y": 2, "z": 3}
    assert operations[4].arguments["expected_rotation"] == {"pitch": 0, "yaw": 90, "roll": 0}
    assert operations[6].arguments["expected_scale"] == {"x": 2, "y": 2, "z": 2}
