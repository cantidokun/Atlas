import pytest

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_result_contract import BlenderExecutionResult


MOVE = {"file_name": "test_scene.blend", "object_name": "Goal_Left_post", "location": [0, 0, 0]}


def test_legacy_execute_preserves_raw_result_contract():
    boundary = BlenderExecutionBoundary(lambda tool, args: {"ok": True})
    assert boundary.execute("move_object", MOVE) == {"ok": True}


def test_execute_verified_returns_structured_result():
    boundary = BlenderExecutionBoundary(lambda tool, args: {"ok": True, "state": "applied", "details": {"object": "Goal_Left_post"}})
    result = boundary.execute_verified("move_object", MOVE)
    assert isinstance(result, BlenderExecutionResult)
    assert result.ok is True
    assert result.state == "applied"


def test_verified_path_rejects_malformed_result():
    boundary = BlenderExecutionBoundary(lambda tool, args: {"ok": True})
    with pytest.raises(ValueError):
        boundary.execute_verified("move_object", MOVE)


def test_both_paths_share_argument_validation():
    boundary = BlenderExecutionBoundary(lambda tool, args: {"ok": True})
    bad = {**MOVE, "location": [0, 0]}
    with pytest.raises(ValueError):
        boundary.execute("move_object", bad)
    with pytest.raises(ValueError):
        boundary.execute_verified("move_object", bad)
