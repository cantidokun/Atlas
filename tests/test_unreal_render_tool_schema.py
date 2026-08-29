"""Regression tests for deterministic Unreal render-call validation."""

import pytest

from planning.unreal_tool_schema import validate_unreal_tool_call


BASE = {"entity_ids": ["RenderTarget"], "authorization_id": "auth-render"}


def render_args(**overrides):
    values = {
        **BASE,
        "width": 1920,
        "height": 1080,
        "start_frame": 1,
        "end_frame": 120,
        "output_directory": " /Game/Renders/Atlas ",
        "output_format": ".PNG",
    }
    values.update(overrides)
    return values


def test_configure_render_normalizes_safe_values():
    result = validate_unreal_tool_call("configure_render", render_args())
    assert result["entity_ids"] == ("RenderTarget",)
    assert result["width"] == 1920
    assert result["height"] == 1080
    assert result["output_directory"] == "/Game/Renders/Atlas"
    assert result["output_format"] == "png"


@pytest.mark.parametrize("field", ["width", "height"])
def test_configure_render_rejects_non_positive_dimensions(field):
    with pytest.raises(ValueError, match=f"{field} must be a positive integer"):
        validate_unreal_tool_call("configure_render", render_args(**{field: 0}))


def test_configure_render_rejects_reversed_frame_range():
    with pytest.raises(ValueError, match="Render start frame must not exceed end frame"):
        validate_unreal_tool_call("configure_render", render_args(start_frame=120, end_frame=1))


def test_configure_render_rejects_empty_output_directory():
    with pytest.raises(ValueError, match="output_directory must be a non-empty string"):
        validate_unreal_tool_call("configure_render", render_args(output_directory="   "))


def test_configure_render_rejects_unsupported_format():
    with pytest.raises(ValueError, match="unsupported render output format"):
        validate_unreal_tool_call("configure_render", render_args(output_format="mov"))


def test_verify_render_state_uses_same_contract():
    result = validate_unreal_tool_call("verify_render_state", render_args(output_format="exr"))
    assert result["output_format"] == "exr"
