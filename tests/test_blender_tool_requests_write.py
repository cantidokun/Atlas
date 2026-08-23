import pytest

from planning.blender_process_executor import BlenderProcessRequest
from planning.blender_tool_requests import (
    BLENDER_PROCESS_REQUEST_BUILDERS,
    build_move_object_request,
)


def test_move_object_request_preserves_validated_arguments():
    request = build_move_object_request(
        "move_object",
        {
            "file_name": "scene.blend",
            "object_name": "Cube",
            "location": [1, 2, 3],
        },
    )

    assert isinstance(request, BlenderProcessRequest)
    assert request.blend_path == "scene.blend"
    assert request.start_marker == "ATLAS_WRITE_START"
    assert request.end_marker == "ATLAS_WRITE_END"
    assert "object_name = 'Cube'" in request.script
    assert "target = [1, 2, 3]" in request.script
    assert "obj.location = target" in request.script
    assert "bpy.data.filepath" in request.script


def test_move_object_request_rejects_tool_mismatch():
    with pytest.raises(ValueError, match="request builder/tool mismatch"):
        build_move_object_request(
            "inspect_scene",
            {"file_name": "scene.blend", "object_name": "Cube", "location": [0, 0, 0]},
        )


def test_move_object_request_rejects_invalid_vector():
    with pytest.raises(ValueError, match="exactly three"):
        build_move_object_request(
            "move_object",
            {"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2]},
        )


def test_move_object_is_registered_as_the_only_write_capability():
    assert set(BLENDER_PROCESS_REQUEST_BUILDERS) == {"inspect_scene", "move_object"}
