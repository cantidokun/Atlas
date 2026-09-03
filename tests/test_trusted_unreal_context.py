
"""Tests for the trusted Unreal execution context."""

from types import SimpleNamespace

import pytest

from controller.agent_trusted_context import AgentTrustedContext
from controller.trusted_unreal_context import TrustedUnrealContext
from planning.unreal_production_planning_boundary import (
    UnrealAuthorizedProductionPlan,
)
from planning.unreal_task_planner import UnrealTaskIntent


def _intent(intent_id="intent-1"):
    return UnrealTaskIntent(
        intent_id=intent_id,
        target_entity_ids=("FIELD_SURFACE",),
        description="test production",
    )


def _authorized(intent_id="intent-1"):
    production = SimpleNamespace(
        plan=SimpleNamespace(intent_id=intent_id)
    )

    return UnrealAuthorizedProductionPlan(
        production=production,
        authorization=SimpleNamespace(),
    )


def test_requires_real_authorized_production_type():
    intent = _intent()

    with pytest.raises(
        TypeError,
        match="UnrealAuthorizedProductionPlan",
    ):
        TrustedUnrealContext(
            authorized_production=object(),
            intent=intent,
            sequence_asset_path="/Game/TestSequence",
        )


def test_requires_real_unreal_intent_type():
    authorized = _authorized()

    with pytest.raises(
        TypeError,
        match="UnrealTaskIntent",
    ):
        TrustedUnrealContext(
            authorized_production=authorized,
            intent=object(),
            sequence_asset_path="/Game/TestSequence",
        )


def test_requires_non_empty_sequence_path():
    intent = _intent()
    authorized = _authorized(intent.intent_id)

    with pytest.raises(
        ValueError,
        match="non-empty Unreal package path",
    ):
        TrustedUnrealContext(
            authorized_production=authorized,
            intent=intent,
            sequence_asset_path="",
        )


def test_rejects_non_package_sequence_path():
    intent = _intent()
    authorized = _authorized(intent.intent_id)

    with pytest.raises(
        ValueError,
        match="Unreal package path",
    ):
        TrustedUnrealContext(
            authorized_production=authorized,
            intent=intent,
            sequence_asset_path="TestSequence",
        )


def test_intent_id_must_match_authorized_production():
    intent = _intent("intent-1")
    authorized = _authorized("different-intent")

    with pytest.raises(
        ValueError,
        match="intent_id must match",
    ):
        TrustedUnrealContext(
            authorized_production=authorized,
            intent=intent,
            sequence_asset_path="/Game/TestSequence",
        )


def test_context_exports_authorized_values():
    intent = _intent()
    authorized = _authorized(intent.intent_id)

    context = TrustedUnrealContext(
        authorized_production=authorized,
        intent=intent,
        sequence_asset_path="/Game/TestSequence",
    )

    trusted = context.to_trusted_agent_context()

    assert isinstance(trusted, AgentTrustedContext)
    assert (
        trusted.get("authorized_production")
        is authorized
    )
    assert trusted.get("intent") is intent
    assert trusted.get("sequence_asset_path") == "/Game/TestSequence"


def test_real_authorized_production_context_preserves_exact_authorization():
    from planning.unreal_composite_operation import (
        CompositeActorProductionOperation,
    )
    from planning.unreal_production_operation import (
        UnrealProductionSpec,
        build_unreal_production_plan,
    )
    from planning.unreal_production_planning_boundary import (
        authorize_production_plan,
    )
    from planning.unreal_render_contract import UnrealRenderConfig

    intent = _intent("real-intent-1")

    composite = CompositeActorProductionOperation(
        entity_ids=("FIELD_SURFACE",),
        operations=(
            {
                "name": "set_actor_location",
                "entity_ids": ("FIELD_SURFACE",),
                "location": {
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                },
            },
        ),
    )

    render_config = UnrealRenderConfig(
        width=64,
        height=64,
        start_frame=1,
        end_frame=1,
        output_directory="/Game/TestOutput",
        output_format="png",
    )

    spec = UnrealProductionSpec(
        composite=composite,
        start_frame=1,
        end_frame=1,
        render_config=render_config,
    )

    production = build_unreal_production_plan(intent, spec)

    authorized = authorize_production_plan(
        production,
        "trusted-test-authorization",
    )

    context = TrustedUnrealContext(
        authorized_production=authorized,
        intent=intent,
        sequence_asset_path="/Game/TestSequence",
    )

    trusted = context.to_trusted_agent_context()

    assert (
        trusted.get("authorized_production")
        is authorized
    )
    assert trusted.get("authorized_production").production is production
    assert (
        trusted.get("authorized_production").authorization.plan_digest
        == authorized.authorization.plan_digest
    )
    assert trusted.get("intent") is intent
    assert trusted.get("sequence_asset_path") == "/Game/TestSequence"


def test_real_authorization_cannot_be_replaced_by_model_context():
    from planning.unreal_composite_operation import (
        CompositeActorProductionOperation,
    )
    from planning.unreal_production_operation import (
        UnrealProductionSpec,
        build_unreal_production_plan,
    )
    from planning.unreal_production_planning_boundary import (
        authorize_production_plan,
    )
    from planning.unreal_render_contract import UnrealRenderConfig

    intent = _intent("override-test")

    composite = CompositeActorProductionOperation(
        entity_ids=("FIELD_SURFACE",),
        operations=(
            {
                "name": "set_actor_location",
                "entity_ids": ("FIELD_SURFACE",),
                "location": {
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                },
            },
        ),
    )

    render_config = UnrealRenderConfig(
        width=64,
        height=64,
        start_frame=1,
        end_frame=1,
        output_directory="/Game/TestOutput",
        output_format="png",
    )

    spec = UnrealProductionSpec(
        composite=composite,
        start_frame=1,
        end_frame=1,
        render_config=render_config,
    )

    production = build_unreal_production_plan(intent, spec)

    authorized = authorize_production_plan(
        production,
        "trusted-test-authorization",
    )

    context = TrustedUnrealContext(
        authorized_production=authorized,
        intent=intent,
        sequence_asset_path="/Game/TrustedSequence",
    )

    trusted = context.to_trusted_agent_context()

    model_context = {
        "production": True,
        "authorized_production": "MODEL_FORGED_AUTHORIZATION",
        "intent": "MODEL_FORGED_INTENT",
        "sequence_asset_path": "/Game/AttackerSequence",
    }

    merged = dict(model_context)
    merged.update(trusted.to_request_context())

    assert merged["authorized_production"] is authorized
    assert merged["intent"] is intent
    assert merged["sequence_asset_path"] == "/Game/TrustedSequence"
