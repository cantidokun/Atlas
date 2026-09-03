
"""Tests for the host-owned agent execution context."""

import pytest

from controller.agent_controller_intent import AgentControllerIntent
from controller.agent_execution_context import AgentExecutionContext
from controller.agent_trusted_context import AgentTrustedContext
from controller.trusted_unreal_context import TrustedUnrealContext


def _trusted_unreal_context():
    from tests.test_trusted_unreal_context import _authorized, _intent

    intent = _intent("execution-context")
    authorized = _authorized(intent.intent_id)

    return TrustedUnrealContext(
        authorized_production=authorized,
        intent=intent,
        sequence_asset_path="/Game/Trusted/Sequence",
    )


def test_context_starts_empty():
    context = AgentExecutionContext()

    assert context.has("unreal") is False
    assert context.get("unreal") is None
    assert context.context_for_request("unreal") == {}


def test_install_unreal_requires_real_trusted_context():
    context = AgentExecutionContext()

    with pytest.raises(
        TypeError,
        match="TrustedUnrealContext",
    ):
        context.install_unreal(object())


def test_install_unreal_exposes_only_trusted_values():
    context = AgentExecutionContext()
    trusted = _trusted_unreal_context()

    context.install_unreal(trusted)

    exported = context.context_for_request("unreal")

    assert exported["authorized_production"] is (
        trusted.authorized_production
    )
    assert exported["intent"] is trusted.intent
    assert exported["sequence_asset_path"] == (
        "/Game/Trusted/Sequence"
    )


def test_install_generic_context_requires_typed_context():
    context = AgentExecutionContext()

    with pytest.raises(
        TypeError,
        match="AgentTrustedContext",
    ):
        context.install("unreal", {})


def test_generic_context_is_normalized_by_provider():
    context = AgentExecutionContext()
    trusted = AgentTrustedContext.from_values(
        {
            "approved": True,
        }
    )

    context.install(" UNREAL ", trusted)

    assert context.has("unreal") is True
    assert context.get("unreal") is trusted
    assert context.context_for_request("unreal") == {
        "approved": True,
    }


def test_unknown_provider_returns_empty_context():
    context = AgentExecutionContext()
    context.install(
        "unreal",
        AgentTrustedContext.from_values({"approved": True}),
    )

    assert context.context_for_request("blender") == {}


def test_provider_validation_is_fail_closed():
    context = AgentExecutionContext()

    with pytest.raises(
        ValueError,
        match="non-empty string",
    ):
        context.has("   ")


def test_agent_execution_context_does_not_authorize():
    context = AgentExecutionContext()

    trusted = AgentTrustedContext.from_values(
        {
            "authorized_production": "already-authorized",
        }
    )

    context.install("unreal", trusted)

    assert context.context_for_request("unreal")[
        "authorized_production"
    ] == "already-authorized"


def test_controller_intent_resolves_context_by_provider_only():
    context = AgentExecutionContext()
    unreal = AgentTrustedContext.from_values({"approved": True})
    blender = AgentTrustedContext.from_values({"approved": False})

    context.install("unreal", unreal)
    context.install("blender", blender)

    intent = AgentControllerIntent(
        capability="production",
        provider="UNREAL",
        context={
            "approved": False,
            "provider": "blender",
        },
        intent="forged-model-intent",
    )

    resolved = context.context_for_controller_intent(intent)

    assert resolved is unreal
    assert resolved.get("approved") is True


def test_controller_intent_without_provider_gets_no_trusted_context():
    context = AgentExecutionContext()
    context.install(
        "unreal",
        AgentTrustedContext.from_values({"approved": True}),
    )

    intent = AgentControllerIntent(
        capability="production",
        provider=None,
        context={"approved": True},
        intent="unreal",
    )

    resolved = context.context_for_controller_intent(intent)

    assert resolved.to_request_context() == {}


def test_controller_intent_binding_requires_typed_intent():
    context = AgentExecutionContext()

    with pytest.raises(
        TypeError,
        match="AgentControllerIntent",
    ):
        context.context_for_controller_intent(object())


def test_trusted_context_cannot_be_replaced_within_one_execution():
    context = AgentExecutionContext()
    first = AgentTrustedContext.from_values({"approved": True})
    second = AgentTrustedContext.from_values({"approved": False})

    context.install("unreal", first)

    with pytest.raises(
        ValueError,
        match="already installed",
    ):
        context.install("unreal", second)

    assert context.get("unreal") is first


def test_unreal_install_cannot_replace_existing_context():
    context = AgentExecutionContext()
    first = _trusted_unreal_context()
    second = _trusted_unreal_context()

    context.install_unreal(first)

    with pytest.raises(
        ValueError,
        match="already installed",
    ):
        context.install_unreal(second)

    assert context.context_for_request("unreal")["intent"] is first.intent
