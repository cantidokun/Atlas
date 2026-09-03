
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
