"""Build deterministic Blender process requests from validated tool calls."""
from typing import Any, Dict

from planning.blender_process_executor import BlenderProcessRequest


def _require_string(arguments: Dict[str, Any], name: str) -> str:
    value = arguments[name]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _require_vector(arguments: Dict[str, Any], name: str):
    value = arguments[name]
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{name} must contain exactly three numeric values")
    return list(value)


def build_inspect_scene_request(tool: str, arguments: Dict[str, Any]) -> BlenderProcessRequest:
    if tool != "inspect_scene":
        raise ValueError("request builder/tool mismatch")
    file_name = _require_string(arguments, "file_name")
    script = """
import bpy, json
result = {
    "ok": True,
    "state": "inspected",
    "details": {
        "scene": bpy.context.scene.name,
        "total_objects": len(bpy.context.scene.objects),
        "objects": [{
            "name": obj.name,
            "type": obj.type,
            "location": [round(obj.location.x, 3), round(obj.location.y, 3), round(obj.location.z, 3)],
            "dimensions": [round(obj.dimensions.x, 3), round(obj.dimensions.y, 3), round(obj.dimensions.z, 3)]
        } for obj in bpy.context.scene.objects]
    }
}
print("ATLAS_RESULT_START")
print(json.dumps(result))
print("ATLAS_RESULT_END")
"""
    return BlenderProcessRequest(
        blend_path=file_name,
        script=script,
        start_marker="ATLAS_RESULT_START",
        end_marker="ATLAS_RESULT_END",
    )


def build_move_object_request(tool: str, arguments: Dict[str, Any]) -> BlenderProcessRequest:
    """Build the first controlled Blender write request from validated arguments."""
    if tool != "move_object":
        raise ValueError("request builder/tool mismatch")
    file_name = _require_string(arguments, "file_name")
    object_name = _require_string(arguments, "object_name")
    location = _require_vector(arguments, "location")
    script = f"""
import bpy, json
object_name = {object_name!r}
target = {location!r}
obj = bpy.data.objects.get(object_name)
if obj is None:
    result = {{
        "ok": False,
        "state": "object_not_found",
        "details": {{"object_name": object_name}}
    }}
else:
    obj.location = target
    bpy.ops.wm.save_as_mainfile(filepath={file_name!r})
    result = {{
        "ok": True,
        "state": "moved",
        "details": {{
            "object_name": obj.name,
            "location": [obj.location.x, obj.location.y, obj.location.z]
        }}
    }}
print("ATLAS_WRITE_START")
print(json.dumps(result))
print("ATLAS_WRITE_END")
"""
    return BlenderProcessRequest(
        blend_path=file_name,
        script=script,
        start_marker="ATLAS_WRITE_START",
        end_marker="ATLAS_WRITE_END",
    )


BLENDER_PROCESS_REQUEST_BUILDERS = {
    "inspect_scene": build_inspect_scene_request,
    "move_object": build_move_object_request,
}
