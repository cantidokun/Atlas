from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_process_executor import BlenderProcessExecutor
from planning.blender_tool_requests import BLENDER_PROCESS_REQUEST_BUILDERS


def test_execution_boundary_can_use_process_executor_for_validated_inspection(monkeypatch):
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
            "scene": "Scene",
            "total_objects": 0,
            "objects": [],
        }

    monkeypatch.setattr(
        "planning.blender_process_executor.run_checked_blender",
        fake_run,
    )

    executor = BlenderProcessExecutor(
        BLENDER_PROCESS_REQUEST_BUILDERS,
        blender_command="blender",
    )
    boundary = BlenderExecutionBoundary(executor)

    result = boundary.execute("inspect_scene", {"file_name": "scene.blend"})

    assert result["scene"] == "Scene"
    assert captured["command"] == "blender"
    assert captured["blend_path"] == "scene.blend"
    assert captured["start_marker"] == "ATLAS_RESULT_START"
    assert captured["end_marker"] == "ATLAS_RESULT_END"


def test_execution_boundary_does_not_expand_registered_capabilities():
    executor = BlenderProcessExecutor(
        BLENDER_PROCESS_REQUEST_BUILDERS,
        blender_command="blender",
    )
    boundary = BlenderExecutionBoundary(executor)

    try:
        boundary.execute("not_registered", {})
    except ValueError as exc:
        assert "unsupported Blender tool" in str(exc)
    else:
        raise AssertionError("unregistered Blender capability was executable")
