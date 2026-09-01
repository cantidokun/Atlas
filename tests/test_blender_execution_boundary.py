import pytest

from planning.blender_execution_boundary import BlenderExecutionBoundary, BlenderClosedLoopResult
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_verification import BlenderVerificationError


def test_valid_move_reaches_executor():
    calls = []
    boundary = BlenderExecutionBoundary(lambda tool, args: calls.append((tool, args)) or {"ok": True})
    result = boundary.execute("move_object", {"object_name": "Goal_Left_post", "location": [0.0, 5.233, 0.0]})
    assert result == {"ok": True}
    assert calls == [("move_object", {"object_name": "Goal_Left_post", "location": [0.0, 5.233, 0.0]})]


def test_valid_move_preserves_tuple_representation():
    calls = []
    boundary = BlenderExecutionBoundary(lambda tool, args: calls.append(args) or {"ok": True})
    boundary.execute("move_object", {"object_name": "Goal_Left_post", "location": (0.0, 5.233, 0.0)})
    assert calls[0]["location"] == (0.0, 5.233, 0.0)
    assert isinstance(calls[0]["location"], tuple)


def test_validated_nested_location_is_detached():
    original = {"object_name": "Goal_Left_post", "location": [0.0, 5.233, 0.0]}
    calls = []
    boundary = BlenderExecutionBoundary(lambda tool, args: calls.append(args) or {"ok": True})
    boundary.execute("move_object", original)
    original["location"][0] = 999.0
    assert calls[0]["location"] == [0.0, 5.233, 0.0]


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


def test_closed_loop_requires_fresh_persistence_verification():
    calls = []
    location = [0.0, 5.233, 0.0]

    def executor(tool, args):
        calls.append((tool, dict(args)))
        if tool == "move_object":
            location[:] = list(args["location"])
            return {"ok": True, "state": "moved", "details": {"location": list(location)}}
        return {
            "ok": True,
            "state": "inspected",
            "details": {
                "objects": [{"name": "Goal_Left_post", "location": list(location)}]
            },
        }

    boundary = BlenderExecutionBoundary(executor)
    closed_loop = boundary.execute_with_persistence(
        "move_object",
        {"object_name": "Goal_Left_post", "location": [0.25, 5.233, 0.0]},
        "inspect_scene",
        {"file_name": "fixture.blend"},
        {"Goal_Left_post": [0.25, 5.233, 0.0]},
        lambda result: {
            "Goal_Left_post": result.details["objects"][0]["location"]
        },
    )

    assert isinstance(closed_loop, BlenderClosedLoopResult)
    assert isinstance(closed_loop.operation_receipt, BlenderExecutionReceipt)
    assert closed_loop.persistence_evidence.matches(
        "move_object",
        {"object_name": "Goal_Left_post", "location": [0.25, 5.233, 0.0]},
        {"Goal_Left_post": [0.25, 5.233, 0.0]},
        {"Goal_Left_post": [0.25, 5.233, 0.0]},
        closed_loop.inspection_result,
    )
    assert [call[0] for call in calls] == ["move_object", "inspect_scene"]


def test_closed_loop_rejects_non_persisted_state():
    location = [0.0, 0.0, 0.0]

    def executor(tool, args):
        if tool == "move_object":
            return {"ok": True, "state": "moved", "details": {}}
        return {
            "ok": True,
            "state": "inspected",
            "details": {
                "objects": [{"name": "Goal_Left_post", "location": list(location)}]
            },
        }

    boundary = BlenderExecutionBoundary(executor)
    with pytest.raises(ValueError, match="expected and observed state to match"):
        boundary.execute_with_persistence(
            "move_object",
            {"object_name": "Goal_Left_post", "location": [0.25, 0.0, 0.0]},
            "inspect_scene",
            {"file_name": "fixture.blend"},
            {"Goal_Left_post": [0.25, 0.0, 0.0]},
            lambda result: {
                "Goal_Left_post": result.details["objects"][0]["location"]
            },
        )


def test_failed_execution_never_enters_closed_loop_inspection():
    calls = []

    def executor(tool, args):
        calls.append(tool)
        return {"ok": False, "state": "blocked", "details": {}}

    boundary = BlenderExecutionBoundary(executor)
    with pytest.raises(BlenderVerificationError):
        boundary.execute_with_persistence(
            "move_object",
            {"object_name": "Goal_Left_post", "location": [0.0, 0.0, 0.0]},
            "inspect_scene",
            {"file_name": "fixture.blend"},
            {"Goal_Left_post": [0.0, 0.0, 0.0]},
            lambda result: {},
        )
    assert calls == ["move_object"]
