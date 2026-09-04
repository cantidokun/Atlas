import pytest

from planning.blender_process_executor import BlenderProcessRequest
from planning.blender_tool_requests import (
    BLENDER_PROCESS_REQUEST_BUILDERS,
    build_inspect_object_transform_request,
    build_move_object_request,
    build_set_object_rotation_request,
)


def test_move_object_request_preserves_validated_arguments():
    request = build_move_object_request(
        "move_object",
        {"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2, 3]},
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


def test_rotation_request_sets_deterministic_degrees_and_persists():
    request = build_set_object_rotation_request(
        "set_object_rotation",
        {"file_name": "scene.blend", "object_name": "Cube", "rotation_degrees": [0, 45, 90]},
    )
    assert isinstance(request, BlenderProcessRequest)
    assert request.blend_path == "scene.blend"
    assert request.start_marker == "ATLAS_ROTATION_START"
    assert request.end_marker == "ATLAS_ROTATION_END"
    assert "target = [0, 45, 90]" in request.script
    assert 'obj.rotation_mode = "XYZ"' in request.script
    assert "math.radians(value)" in request.script
    assert "bpy.ops.wm.save_as_mainfile" in request.script


def test_rotation_request_rejects_invalid_vector():
    with pytest.raises(ValueError, match="exactly three"):
        build_set_object_rotation_request(
            "set_object_rotation",
            {"file_name": "scene.blend", "object_name": "Cube", "rotation_degrees": [0, 45]},
        )


def test_inspect_transform_request_is_read_only_and_fresh_inspection_capability():
    request = build_inspect_object_transform_request(
        "inspect_object_transform",
        {"file_name": "scene.blend", "object_name": "Cube"},
    )
    assert isinstance(request, BlenderProcessRequest)
    assert request.start_marker == "ATLAS_TRANSFORM_START"
    assert request.end_marker == "ATLAS_TRANSFORM_END"
    assert "rotation_degrees" in request.script
    assert "bpy.ops.wm.save_as_mainfile" not in request.script


def test_registered_capabilities_are_exactly_the_current_controlled_set():
    assert set(BLENDER_PROCESS_REQUEST_BUILDERS) == {
        "inspect_scene",
        "inspect_object_transform",
        "move_object",
        "set_object_rotation",
    }
