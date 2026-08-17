import pytest

from planning.blender_execution_boundary import BlenderExecutionBoundary


def test_valid_move_reaches_executor():
    calls = []
    boundary = BlenderExecutionBoundary(lambda tool, args: calls.append((tool, args)) or {"ok": True})
    result = boundary.execute("move_object", {"object_name": "Goal_Left_post", "location": [0.0, 5.233, 0.0]})
    assert result == {"ok": True}
    assert calls == [("move_object", {"object_name": "Goal_Left_post", "location": [0.0, 5.233, 0.0]})]


def test_malformed_move_never_reaches_executor():
    calls = []
    boundary = BlenderExecutionBoundary(lambda tool, args: calls.append((tool, args)) or {"ok": True})
    with pytest.raises(ValueError):
        boundary.execute("move_object", {"object_name": "Goal_Left_post", "location": [0.0, 5.233]})
    assert calls == []


def test_unknown_tool_never_reaches_executor():
    calls = []
    boundary = BlenderExecutionBoundary(lambda tool, args: calls.append((tool, args)) or {"ok": True})
    with pytest.raises(ValueError):
        boundary.execute("delete_everything", {})
    assert calls == []


def test_non_object_executor_result_is_rejected():
    boundary = BlenderExecutionBoundary(lambda tool, args: ["bad"])
    with pytest.raises(TypeError):
        boundary.execute("inspect_object", {"object_name": "Goal_Left_post"})
