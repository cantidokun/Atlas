"""Tests for heterogeneous Unreal production-plan composition."""

import pytest

from planning.unreal_composite_operation import build_composite_actor_operation
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_production_operation import (
    UnrealProductionSpec,
    build_unreal_production_plan,
)
from planning.unreal_render_contract import UnrealRenderConfig
from planning.unreal_task_planner import UnrealTaskIntent


TARGET = "FIELD_SURFACE"


def _intent(intent_id="production-1"):
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="heterogeneous production test",
        target_entity_ids=(TARGET,),
    )


def _composite():
    return build_composite_actor_operation(
        [TARGET],
        [
            {"name": "set_actor_location", "location": {"x": 10.0, "y": 20.0, "z": 30.0}},
            {"name": "set_actor_rotation", "rotation": {"pitch": 0.0, "yaw": 15.0, "roll": 0.0}},
            {"name": "set_actor_scale", "scale": {"x": 1.1, "y": 1.1, "z": 1.1}},
            {"name": "apply_material_variant", "variant": "liquid_surface"},
            {"name": "apply_niagara_variant", "variant": "goal_burst"},
        ],
    )


def _spec(with_blueprint=True):
    return UnrealProductionSpec(
        composite=_composite(),
        start_frame=1,
        end_frame=24,
        render_config=UnrealRenderConfig(
            width=1280,
            height=720,
            start_frame=1,
            end_frame=24,
            output_directory="Saved/AtlasProductionOutput",
            output_format="png",
        ),
        blueprint_asset_path="/Game/AtlasTest/BP_AtlasTest",
    ) if with_blueprint else UnrealProductionSpec(
        composite=_composite(),
        start_frame=1,
        end_frame=24,
        render_config=UnrealRenderConfig(
            width=1280,
            height=720,
            start_frame=1,
            end_frame=24,
            output_directory="Saved/AtlasProductionOutput",
            output_format="png",
        ),
    )


def test_production_plan_contains_all_heterogeneous_phases():
    production = build_unreal_production_plan(_intent(), _spec())

    assert [name for name, _, _ in production.phases] == [
        "blueprint",
        "actor_composite",
        "sequencer",
        "render",
    ]
    assert [operation.name for operation in production.plan.operations] == [
        "inspect_blueprint_state",
        "compile_blueprint",
        "verify_blueprint_state",
        "inspect_target_actors",
        "set_actor_location",
        "verify_actor_location",
        "set_actor_rotation",
        "verify_actor_rotation",
        "set_actor_scale",
        "verify_actor_scale",
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


def test_production_plan_is_directly_authorizable():
    production = build_unreal_production_plan(_intent(), _spec())
    authorization = UnrealPlanAuthorization.issue(production.plan, "production-auth")

    assert authorization.matches(production.plan)
    assert authorization.authorization_id == "production-auth"
    assert authorization.plan_digest
    assert authorization.authorization_digest


def test_production_plan_digest_changes_when_a_phase_changes():
    first = build_unreal_production_plan(_intent("production-a"), _spec())
    second = build_unreal_production_plan(
        _intent("production-b"),
        _spec(),
    )

    first_auth = UnrealPlanAuthorization.issue(first.plan, "production-auth")
    second_auth = UnrealPlanAuthorization.issue(second.plan, "production-auth")

    assert first_auth.plan_digest != second_auth.plan_digest


def test_blueprint_phase_is_optional_but_remaining_phases_are_preserved():
    production = build_unreal_production_plan(_intent(), _spec(with_blueprint=False))

    assert [name for name, _, _ in production.phases] == [
        "actor_composite",
        "sequencer",
        "render",
    ]
    assert production.plan.operations[0].name == "inspect_target_actors"
    assert production.plan.operations[-1].name == "verify_render_state"


def test_production_requires_matching_targets():
    mismatched_intent = UnrealTaskIntent(
        intent_id="production-mismatch",
        description="mismatch",
        target_entity_ids=("OTHER",),
    )

    with pytest.raises(ValueError, match="exactly match"):
        build_unreal_production_plan(mismatched_intent, _spec())


def test_render_frame_range_must_match_production_range():
    with pytest.raises(ValueError, match="frame range"):
        UnrealProductionSpec(
            composite=_composite(),
            start_frame=1,
            end_frame=24,
            render_config=UnrealRenderConfig(
                width=1280,
                height=720,
                start_frame=1,
                end_frame=25,
                output_directory="Saved/AtlasProductionOutput",
                output_format="png",
            ),
        )
