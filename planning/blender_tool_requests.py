"""Build deterministic Blender process requests from validated tool calls."""
from typing import Any, Dict

from planning.blender_process_executor import BlenderProcessRequest


def _require_string(arguments: Dict[str, Any], name: str) -> str:
    value = arguments[name]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def build_inspect_scene_request(tool: str, arguments: Dict[str, Any]) -> BlenderProcessRequest:
    if tool != "inspect_scene":
        raise ValueError("request builder/tool mismatch")
    file_name = _require_string(arguments, "file_name")
    script = f"""
import bpy, json
result = {{
    "scene": bpy.context.scene.name,
    "total_objects": len(bpy.context.scene.objects),
    "objects": [{{
        "name": obj.name,
        "type": obj.type,
        "location": [round(obj.location.x, 3), round(obj.location.y, 3), round(obj.location.z, 3)],
        "dimensions": [round(obj.dimensions.x, 3), round(obj.dimensions.y, 3), round(obj.dimensions.z, 3)]
    }} for obj in bpy.context.scene.objects]
}}
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


BLENDER_PROCESS_REQUEST_BUILDERS = {
    "inspect_scene": build_inspect_scene_request,
}
