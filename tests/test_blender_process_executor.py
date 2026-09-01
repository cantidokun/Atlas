import pytest

from planning.blender_process_executor import (
    BlenderProcessExecutor,
    BlenderProcessRequest,
)


def test_process_executor_passes_validated_request_to_transport(monkeypatch):
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
        return {"ok": True, "state": "persisted"}

    monkeypatch.setattr(
        "planning.blender_process_executor.run_checked_blender",
        fake_run,
    )

    def builder(tool, arguments):
        assert tool == "inspect_scene"
        assert arguments == {"file_name": "scene.blend"}
        return BlenderProcessRequest(
            blend_path="C:/Atlas/scene.blend",
            script="print('inspect')",
            start_marker="ATLAS_RESULT_START",
            end_marker="ATLAS_RESULT_END",
            timeout=30,
        )

    executor = BlenderProcessExecutor(
        {"inspect_scene": builder},
        blender_command="blender",
    )

    assert executor("inspect_scene", {"file_name": "scene.blend"}) == {
        "ok": True,
        "state": "persisted",
    }
    assert captured == {
        "command": "blender",
        "blend_path": "C:/Atlas/scene.blend",
        "script": "print('inspect')",
        "start_marker": "ATLAS_RESULT_START",
        "end_marker": "ATLAS_RESULT_END",
        "timeout": 30,
    }


def test_process_executor_rejects_unknown_tool():
    executor = BlenderProcessExecutor({}, blender_command="blender")

    with pytest.raises(ValueError, match="No Blender process request builder"):
        executor("unknown_tool", {})


def test_process_executor_rejects_invalid_request_builder_result():
    executor = BlenderProcessExecutor(
        {"inspect_scene": lambda tool, arguments: {"not": "a request"}},
        blender_command="blender",
    )

    with pytest.raises(TypeError, match="BlenderProcessRequest"):
        executor("inspect_scene", {})


def test_process_executor_copies_arguments_before_builder_receives_them(monkeypatch):
    observed = {}

    def fake_run(command, blend_path, script, start_marker, end_marker, *, timeout):
        return {"ok": True, "state": "inspected"}

    monkeypatch.setattr(
        "planning.blender_process_executor.run_checked_blender",
        fake_run,
    )

    def builder(tool, arguments):
        observed["arguments"] = arguments
        arguments["file_name"] = "mutated.blend"
        return BlenderProcessRequest(
            blend_path="scene.blend",
            script="print('ok')",
            start_marker="START",
            end_marker="END",
        )

    executor = BlenderProcessExecutor(
        {"inspect_scene": builder},
        blender_command="blender",
    )
    original = {"file_name": "scene.blend"}

    executor("inspect_scene", original)

    assert original == {"file_name": "scene.blend"}
    assert observed["arguments"] == {"file_name": "mutated.blend"}
