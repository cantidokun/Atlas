"""Tests for deterministic Unreal tool-call validation."""

import pytest

from planning.unreal_tool_schema import validate_unreal_tool_call


def test_set_actor_scale_accepts_valid_arguments():
    result = validate_unreal_tool_call(
        "set_actor_scale",
        {
            "entity_ids": ["Cube"],
            "authorization_id": "auth-1",
            "scale": {"x": 1.5, "y": 2, "z": 0.75},
        },
    )
    assert result["entity_ids"] == ("Cube",)
    assert result["scale"] == {"x": 1.5, "y": 2, "z": 0.75}


def test_set_actor_scale_rejects_missing_scale():
    with pytest.raises(ValueError, match="missing required argument: scale"):
        validate_unreal_tool_call(
            "set_actor_scale",
            {"entity_ids": ["Cube"], "authorization_id": "auth-1"},
        )


def test_set_actor_scale_rejects_wrong_shape():
    with pytest.raises(ValueError, match="scale must contain exactly x, y, and z"):
        validate_unreal_tool_call(
            "set_actor_scale",
            {
                "entity_ids": ["Cube"],
                "authorization_id": "auth-1",
                "scale": {"x": 1, "y": 1},
            },
        )


def test_set_actor_scale_rejects_boolean_component():
    with pytest.raises(TypeError, match="scale components must be numeric"):
        validate_unreal_tool_call(
            "set_actor_scale",
            {
                "entity_ids": ["Cube"],
                "authorization_id": "auth-1",
                "scale": {"x": True, "y": 1, "z": 1},
            },
        )
