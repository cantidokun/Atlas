import pytest

from planning.blender_result_contract import normalize_blender_result


def test_normalizes_valid_result():
    result = normalize_blender_result("move_object", {"ok": True, "state": "applied", "details": {"object": "Goal_Left_post"}})
    assert result.tool == "move_object"
    assert result.ok is True
    assert result.state == "applied"
    assert result.details == {"object": "Goal_Left_post"}


def test_details_default_to_empty_object():
    result = normalize_blender_result("inspect_object", {"ok": True, "state": "verified"})
    assert result.details == {}


def test_missing_required_result_field_blocks():
    with pytest.raises(ValueError):
        normalize_blender_result("move_object", {"ok": True})


def test_invalid_result_shape_blocks():
    with pytest.raises(TypeError):
        normalize_blender_result("move_object", ["ok"])


def test_invalid_details_blocks():
    with pytest.raises(TypeError):
        normalize_blender_result("move_object", {"ok": True, "state": "applied", "details": []})


def test_result_is_immutable():
    result = normalize_blender_result("move_object", {"ok": False, "state": "blocked"})
    with pytest.raises(Exception):
        result.state = "applied"
