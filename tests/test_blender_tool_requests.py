import pytest

from planning.blender_process_executor import BlenderProcessRequest
from planning.blender_tool_requests import (
    BLENDER_PROCESS_REQUEST_BUILDERS,
    build_inspect_scene_request,
)


def test_inspect_scene_request_is_deterministic():
    first = build_inspect_scene_request("inspect_scene", {"file_name": "scene.blend"})
    second = build_inspect_scene_request("inspect_scene", {"file_name": "scene.blend"})

    assert isinstance(first, BlenderProcessRequest)
    assert first == second
    assert first.blend_path == "scene.blend"
    assert first.start_marker == "ATLAS_RESULT_START"
    assert first.end_marker == "ATLAS_RESULT_END"


def test_inspect_scene_request_rejects_tool_mismatch():
    with pytest.raises(ValueError, match="request builder/tool mismatch"):
        build_inspect_scene_request("move_object", {"file_name": "scene.blend"})


def test_inspect_scene_request_rejects_empty_file_name():
    with pytest.raises(ValueError, match="file_name"):
        build_inspect_scene_request("inspect_scene", {"file_name": "   "})


def test_current_validated_capabilities_are_registered():
    assert set(BLENDER_PROCESS_REQUEST_BUILDERS) == {"inspect_scene", "move_object"}
