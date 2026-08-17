import pytest

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_verification import BlenderVerificationError


def test_verified_execution_accepts_success():
    boundary = BlenderExecutionBoundary(
        lambda tool, args: {"ok": True, "state": "applied", "details": {"object": args["object_name"]}}
    )
    result = boundary.execute_verified("move_object", {"object_name": "Goal_Left_post", "location": [0, 0, 0]})
    assert result.ok is True
    assert result.tool == "move_object"


def test_verified_execution_blocks_unsuccessful_result():
    boundary = BlenderExecutionBoundary(
        lambda tool, args: {"ok": False, "state": "blocked", "details": {"reason": "fixture"}}
    )
    with pytest.raises(BlenderVerificationError):
        boundary.execute_verified("move_object", {"object_name": "Goal_Left_post", "location": [0, 0, 0]})


def test_legacy_execution_still_returns_failed_raw_result():
    boundary = BlenderExecutionBoundary(
        lambda tool, args: {"ok": False, "state": "blocked"}
    )
    assert boundary.execute("move_object", {"object_name": "Goal_Left_post", "location": [0, 0, 0]})["ok"] is False
