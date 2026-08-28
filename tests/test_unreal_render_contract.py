import pytest

from planning.unreal_render_contract import UnrealRenderConfig, normalize_render_config


def _config():
    return {
        "width": 1920,
        "height": 1080,
        "start_frame": 1,
        "end_frame": 120,
        "output_directory": "/Game/Atlas/RenderOutput",
        "output_format": "png",
    }


def test_render_config_normalizes_exact_contract():
    config = normalize_render_config(_config())
    assert isinstance(config, UnrealRenderConfig)
    assert config.width == 1920
    assert config.end_frame == 120


@pytest.mark.parametrize("field", ["width", "height", "start_frame", "end_frame", "output_directory", "output_format"])
def test_render_config_rejects_missing_fields(field):
    value = _config()
    del value[field]
    with pytest.raises(ValueError):
        normalize_render_config(value)


def test_render_config_rejects_reversed_frame_range():
    value = _config()
    value["start_frame"] = 120
    value["end_frame"] = 1
    with pytest.raises(ValueError):
        normalize_render_config(value)


def test_render_config_rejects_boolean_dimensions():
    value = _config()
    value["width"] = True
    with pytest.raises(TypeError):
        normalize_render_config(value)
