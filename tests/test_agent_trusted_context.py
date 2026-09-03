
"""Tests for the trusted agent controller context."""

import pytest

from controller.agent_trusted_context import AgentTrustedContext


def test_empty_context_is_empty():
    context = AgentTrustedContext.empty()

    assert context.to_request_context() == {}
    assert context.contains("authorized_production") is False


def test_context_preserves_values():
    context = AgentTrustedContext.from_values(
        {
            "authorized_production": "AUTH",
            "sequence_asset_path": "/Game/Test",
        }
    )

    assert context.get("authorized_production") == "AUTH"
    assert context.get("sequence_asset_path") == "/Game/Test"


def test_context_returns_copy_for_request_context():
    context = AgentTrustedContext.from_values(
        {
            "sequence_asset_path": "/Game/Test",
        }
    )

    request_context = context.to_request_context()
    request_context["sequence_asset_path"] = "/Game/Changed"

    assert context.get("sequence_asset_path") == "/Game/Test"


def test_context_rejects_non_mapping():
    with pytest.raises(TypeError, match="values must be a mapping"):
        AgentTrustedContext(["not", "a", "mapping"])


def test_context_rejects_empty_key():
    with pytest.raises(ValueError, match="non-empty strings"):
        AgentTrustedContext.from_values(
            {
                "": "invalid",
            }
        )


def test_context_is_immutable_at_public_boundary():
    context = AgentTrustedContext.from_values(
        {
            "authorization_id": "AUTH-1",
        }
    )

    request_context = context.to_request_context()
    request_context["authorization_id"] = "AUTH-2"

    assert context.get("authorization_id") == "AUTH-1"
