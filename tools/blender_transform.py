"""Controlled Blender object transform operations."""
from .blender import run_blender, validate_blend_file


def set_object_rotation(file_name, object_name, rotation_degrees):
    blend_path = validate_blend_file(file_name)
    if not isinstance(rotation_degrees, (list, tuple)) or len(rotation_degrees) != 3:
        return {"status": "error", "error": "rotation_degrees must contain exactly three values"}
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in rotation_degrees):
        return {"status": "error", "error": "rotation_degrees must contain numeric values"}

    script = f"""
import bpy
import json
import math

object_name = {object_name!r}
target = [float(value) for value in {list(rotation_degrees)!r}]
obj = bpy.data.objects.get(object_name)

if obj is None:
    result = {{"status": "object_not_found", "object_name": object_name}}
elif all(abs(math.degrees(angle) - wanted) <= 1e-5 for angle, wanted in zip(obj.rotation_euler, target)):
    result = {{"status": "already_rotated", "object_name": object_name, "rotation_degrees": [math.degrees(angle) for angle in obj.rotation_euler]}}
else:
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = tuple(math.radians(value) for value in target)
    bpy.ops.wm.save_as_mainfile(filepath={blend_path!r})
    result = {{"status": "ok", "object_name": object_name, "rotation_degrees": [math.degrees(angle) for angle in obj.rotation_euler]}}

print("ATLAS_ROTATION_START")
print(json.dumps(result))
print("ATLAS_ROTATION_END")
"""
    return run_blender(blend_path, script, "ATLAS_ROTATION_START", "ATLAS_ROTATION_END")


def inspect_object_transform(file_name, object_name):
    blend_path = validate_blend_file(file_name)
    script = f"""
import bpy
import json
import math

object_name = {object_name!r}
obj = bpy.data.objects.get(object_name)
if obj is None:
    result = {{"status": "object_not_found", "object_name": object_name}}
else:
    result = {{
        "status": "ok",
        "object_name": object_name,
        "rotation_degrees": [math.degrees(angle) for angle in obj.rotation_euler],
    }}

print("ATLAS_TRANSFORM_START")
print(json.dumps(result))
print("ATLAS_TRANSFORM_END")
"""
    return run_blender(blend_path, script, "ATLAS_TRANSFORM_START", "ATLAS_TRANSFORM_END")
