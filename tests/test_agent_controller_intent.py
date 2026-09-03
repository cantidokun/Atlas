
"""Tests for explicit provider-neutral controller intent parsing."""

import pytest

from controller.agent_controller_intent import (
    AgentControllerIntent,
    extract_agent_controller_intent,
    parse_agent_controller_intent,
)
from controller.agent_task_request import AgentTaskRequest


def test_parse_agent_controller_intent_preserves_explicit_request_fields():
    intent = parse_agent_controller_intent(
        {
            "capability": "production",
            "provider": "unreal",
            "context": {
                "production": True,
                "target_entity_ids": ("FIELD_SURFACE",),
            },
            "intent": "render-field-production",
        }
    )

    assert isinstance(intent, AgentControllerIntent)
    assert intent.capability == "production"
    assert intent.provider == "unreal"
    assert intent.context["production"] is True
    assert intent.context["target_entity_ids"] == ("FIELD_SURFACE",)
    assert intent.intent == "render-field-production"

    request = intent.to_task_request()

    assert isinstance(request, AgentTaskRequest)
    assert request.capability == "production"
    assert request.provider == "unreal"
    assert request.context["production"] is True
    assert request.intent == "render-field-production"


def test_parse_agent_controller_intent_defaults_context_to_empty_dictionary():
    intent = parse_agent_controller_intent(
        {
            "capability": "inspection",
            "provider": "unreal",
        }
    )

    assert intent.context == {}
    assert intent.to_task_request().routing_kwargs() == {
        "capability": "inspection",
        "provider": "unreal",
        "context": {},
    }


def test_parse_agent_controller_intent_rejects_missing_capability():
    with pytest.raises(ValueError, match="capability"):
        parse_agent_controller_intent({"provider": "unreal"})


def test_parse_agent_controller_intent_rejects_non_dict_context():
    with pytest.raises(TypeError, match="context"):
        parse_agent_controller_intent(
            {
                "capability": "production",
                "context": [],
            }
        )


def test_extract_agent_controller_intent_returns_none_without_marker():
    assert extract_agent_controller_intent(
        "I will inspect the current scene before deciding."
    ) is None


def test_extract_agent_controller_intent_parses_explicit_request():
    content = """
I have determined that the Unreal production capability is required.

ATLAS_CONTROLLER_REQUEST:
{
  "capability": "production",
  "provider": "unreal",
  "intent": "render-field-production",
  "context": {
    "production": true,
    "target_entity_ids": ["FIELD_SURFACE"]
  }
}
"""

    intent = extract_agent_controller_intent(content)

    assert isinstance(intent, AgentControllerIntent)
    assert intent.capability == "production"
    assert intent.provider == "unreal"
    assert intent.intent == "render-field-production"
    assert intent.context == {
        "production": True,
        "target_entity_ids": ["FIELD_SURFACE"],
    }


def test_extract_agent_controller_intent_rejects_invalid_json():
    with pytest.raises(ValueError, match="invalid JSON"):
        extract_agent_controller_intent(
            """
ATLAS_CONTROLLER_REQUEST:
{
  "capability": "production",
}
"""
        )


def test_extract_agent_controller_intent_rejects_non_object_payload():
    with pytest.raises(ValueError, match="must be a JSON object"):
        extract_agent_controller_intent(
            """
ATLAS_CONTROLLER_REQUEST:
["production"]
"""
        )


def test_requested_intent_is_model_metadata_not_authorization():
    intent = parse_agent_controller_intent(
        {
            "capability": "production",
            "provider": "unreal",
            "intent": "render-field-production",
            "context": {
                "production": True,
            },
        }
    )

    assert intent.requested_intent == "render-field-production"
    assert intent.intent == intent.requested_intent
    assert "authorized_production" not in intent.context
