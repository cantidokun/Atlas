import pytest

from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_composite_operation import build_composite_actor_operation
from planning.unreal_production_shot import (
    UnrealProductionShotRequest,
    build_production_shot_plan,
)
from planning.unreal_task_planner import UnrealTaskPlanner


RENDER = {
    "width": 1280,
    "height": 720,
    "start_frame": 1,
    "end_frame": 24,
    "output_directory": "Saved/AtlasRenderOutput",
    "output_format": "png",
}


def _intent():
    return UnrealTaskIntent(
        "production-shot-1",
        "prepare a derived liquid-field production shot",
        ("FIELD_SURFACE",),
    )


def _composite():
    return build_composite_actor_operation(
        ["FIELD_SURFACE"],
        [
            {
                "name": "set_actor_location",
                "location": {"x": 1, "y": 2, "z": 3},
            },
            {
                "name": "apply_material_variant",
                "variant": "wet",
            },
            {
                "name": "apply_niagara_variant",
                "variant": "liquid_surface",
            },
        ],
    )


def _request():
    return UnrealProductionShotRequest(
        composite=_composite(),
        start_frame=1,
        end_frame=24,
        render_config=RENDER,
    )


def test_production_shot_composes_existing_boundaries_in_order():
    plan = build_production_shot_plan(UnrealTaskPlanner(), _intent(), _request())

    assert [op.name for op in plan.operations] == [
        "inspect_target_actors",
        "set_actor_location",
        "verify_actor_location",
        "inspect_material_state",
        "apply_material_variant",
        "verify_material_variant",
        "inspect_niagara_state",
        "apply_niagara_variant",
        "verify_niagara_variant",
        "inspect_sequencer_state",
        "set_sequencer_playback_range",
        "verify_sequencer_playback_range",
        "inspect_render_state",
        "configure_render",
        "verify_render_state",
    ]


def test_production_shot_preserves_existing_entity_targets():
    plan = build_production_shot_plan(UnrealTaskPlanner(), _intent(), _request())

    assert all(op.entity_ids == ("FIELD_SURFACE",) for op in plan.operations)


def test_production_shot_requires_render_and_sequencer_ranges_to_match():
    with pytest.raises(ValueError, match="frame range"):
        UnrealProductionShotRequest(
            composite=_composite(),
            start_frame=1,
            end_frame=24,
            render_config={**RENDER, "end_frame": 25},
        )


def test_production_shot_rejects_composite_target_escape():
    intent = _intent()
    other = UnrealTaskIntent(
        "production-shot-2",
        "wrong target",
        ("OTHER",),
    )
    request = _request()
    with pytest.raises(ValueError, match="exactly match"):
        build_production_shot_plan(UnrealTaskPlanner(), other, request)


def test_production_shot_keeps_each_write_immediately_followed_by_verification():
    plan = build_production_shot_plan(UnrealTaskPlanner(), _intent(), _request())

    for index, operation in enumerate(plan.operations[:-1]):
        if operation.kind.value == "write":
            assert plan.operations[index + 1].kind.value == "verify"
            assert plan.operations[index + 1].entity_ids == operation.entity_ids
