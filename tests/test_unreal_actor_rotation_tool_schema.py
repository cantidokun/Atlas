import pytest

from planning.unreal_tool_schema import validate_unreal_tool_call


def test_actor_rotation_tool_schema_accepts_exact_payload():
    result = validate_unreal_tool_call(
        "set_actor_rotation",
        {
            "entity_ids": ("FIELD_SURFACE",),
            "authorization_id": "rotation-auth",
            "rotation": {"pitch": 12.0, "yaw": 47.5, "roll": -8.0},
        },
    )
    assert result["entity_ids"] == ("FIELD_SURFACE",)
    assert result["rotation"] == {"pitch": 12.0, "yaw": 47.5, "roll": -8.0}


def test_actor_rotation_tool_schema_rejects_wrong_shape():
    with pytest.raises(ValueError, match="exactly pitch, yaw, and roll"):
        validate_unreal_tool_call(
            "set_actor_rotation",
            {
                "entity_ids": ("FIELD_SURFACE",),
                "authorization_id": "rotation-auth",
                "rotation": {"pitch": 1.0},
            },
        )


def test_actor_rotation_tool_schema_rejects_non_numeric_angles():
    with pytest.raises(TypeError, match="rotation angles must be numeric"):
        validate_unreal_tool_call(
            "set_actor_rotation",
            {
                "entity_ids": ("FIELD_SURFACE",),
                "authorization_id": "rotation-auth",
                "rotation": {"pitch": "1", "yaw": 2.0, "roll": 3.0},
            },
        )
