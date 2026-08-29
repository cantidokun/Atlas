"""Tests for deterministic Unreal tool-call validation."""

import pytest

from planning.unreal_tool_schema import validate_unreal_tool_call


def test_set_actor_scale_accepts_valid_arguments():
    result = validate_unreal_tool_call("set_actor_scale", {"entity_ids": ["Cube"], "authorization_id": "auth-1", "scale": {"x": 1.5, "y": 2, "z": 0.75}})
    assert result["entity_ids"] == ("Cube",)
    assert result["scale"] == {"x": 1.5, "y": 2, "z": 0.75}


def test_set_actor_scale_rejects_missing_scale():
    with pytest.raises(ValueError, match="missing required argument: scale"):
        validate_unreal_tool_call("set_actor_scale", {"entity_ids": ["Cube"], "authorization_id": "auth-1"})


def test_set_actor_scale_rejects_wrong_shape():
    with pytest.raises(ValueError, match="scale must contain exactly x, y, and z"):
        validate_unreal_tool_call("set_actor_scale", {"entity_ids": ["Cube"], "authorization_id": "auth-1", "scale": {"x": 1, "y": 1}})


def test_set_actor_scale_rejects_boolean_component():
    with pytest.raises(TypeError, match="scale components must be numeric"):
        validate_unreal_tool_call("set_actor_scale", {"entity_ids": ["Cube"], "authorization_id": "auth-1", "scale": {"x": True, "y": 1, "z": 1}})


def _render_arguments(**overrides):
    arguments = {"entity_ids": ["RenderQueue"], "authorization_id": "auth-render", "width": 1920, "height": 1080, "start_frame": 1, "end_frame": 120, "output_directory": " /Game/Renders/Atlas ", "output_format": ".PNG"}
    arguments.update(overrides)
    return arguments


def test_configure_render_normalizes_safe_arguments():
    result = validate_unreal_tool_call("configure_render", _render_arguments())
    assert result["entity_ids"] == ("RenderQueue",)
    assert result["output_directory"] == "/Game/Renders/Atlas"
    assert result["output_format"] == "png"


@pytest.mark.parametrize("field", ["width", "height"])
def test_configure_render_rejects_non_positive_dimensions(field):
    with pytest.raises(ValueError, match=rf"{field} must be a positive integer"):
        validate_unreal_tool_call("configure_render", _render_arguments(**{field: 0}))


def test_configure_render_rejects_invalid_frame_range():
    with pytest.raises(ValueError, match="Render start frame must not exceed end frame"):
        validate_unreal_tool_call("configure_render", _render_arguments(start_frame=121, end_frame=120))


def test_configure_render_rejects_empty_output_directory():
    with pytest.raises(ValueError, match="output_directory must be a non-empty string"):
        validate_unreal_tool_call("configure_render", _render_arguments(output_directory="  "))


@pytest.mark.parametrize("output_format", ["mov", "mp4", "  "])
def test_configure_render_rejects_unsupported_output_format(output_format):
    with pytest.raises(ValueError, match="unsupported render output format|output_format must be a non-empty string"):
        validate_unreal_tool_call("configure_render", _render_arguments(output_format=output_format))


def test_verify_render_state_uses_the_same_render_contract():
    result = validate_unreal_tool_call("verify_render_state", _render_arguments())
    assert result["output_format"] == "png"


def test_render_validation_rejects_boolean_dimensions():
    with pytest.raises(ValueError, match="width must be a positive integer"):
        validate_unreal_tool_call("configure_render", _render_arguments(width=True))
