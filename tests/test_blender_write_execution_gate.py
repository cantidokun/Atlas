import pytest

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_process_executor import BlenderProcessExecutor
from planning.blender_tool_requests import BLENDER_PROCESS_REQUEST_BUILDERS
from planning.blender_verification import BlenderVerificationError


def test_move_object_is_executable_only_after_schema_validation(monkeypatch):
    captured = {}

    def fake_run(command, blend_path, script, start_marker, end_marker, *, timeout):
        captured.update(
            command=command,
            blend_path=blend_path,
            script=script,
            start_marker=start_marker,
            end_marker=end_marker,
            timeout=timeout,
        )
        return {
            "ok": True,
            "state": "moved",
            "details": {"object_name": "Cube", "location": [1, 2, 3]},
        }

    monkeypatch.setattr("planning.blender_process_executor.run_checked_blender", fake_run)

    boundary = BlenderExecutionBoundary(
        BlenderProcessExecutor(BLENDER_PROCESS_REQUEST_BUILDERS, blender_command="blender")
    )

    result, receipt = boundary.execute_with_receipt(
        "move_object",
        {"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2, 3]},
    )

    assert result.ok is True
    assert result.state == "moved"
    assert captured["blend_path"] == "scene.blend"
    assert captured["start_marker"] == "ATLAS_WRITE_START"
    assert "target = [1, 2, 3]" in captured["script"]
    assert receipt.matches(
        "move_object",
        {"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2, 3]},
        result,
    )


def test_move_object_failure_never_becomes_verified_success(monkeypatch):
    monkeypatch.setattr(
        "planning.blender_process_executor.run_checked_blender",
        lambda *args, **kwargs: {
            "ok": False,
            "state": "object_not_found",
            "details": {"object_name": "Missing"},
        },
    )

    boundary = BlenderExecutionBoundary(
        BlenderProcessExecutor(BLENDER_PROCESS_REQUEST_BUILDERS, blender_command="blender")
    )

    with pytest.raises(BlenderVerificationError, match="did not succeed"):
        boundary.execute_verified(
            "move_object",
            {"file_name": "scene.blend", "object_name": "Missing", "location": [1, 2, 3]},
        )


def test_move_object_rejects_malformed_location_before_transport(monkeypatch):
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True
        return {"ok": True, "state": "moved", "details": {}}

    monkeypatch.setattr("planning.blender_process_executor.run_checked_blender", fake_run)

    boundary = BlenderExecutionBoundary(
        BlenderProcessExecutor(BLENDER_PROCESS_REQUEST_BUILDERS, blender_command="blender")
    )

    with pytest.raises(ValueError, match="exactly three"):
        boundary.execute(
            "move_object",
            {"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2]},
        )

    assert called is False
