"""Controlled Blender object transform operations."""
from math import isfinite

from .blender import run_blender, validate_blend_file


def _validate_rotation_degrees(rotation_degrees):
    if not isinstance(rotation_degrees, (list, tuple)) or len(rotation_degrees) != 3:
        return {"status": "error", "error": "rotation_degrees must contain exactly three numeric values"}
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in rotation_degrees):
        return {"status": "error", "error": "rotation_degrees must contain exactly three numeric values"}
    if any(not isfinite(float(value)) for value in rotation_degrees):
        return {"status": "error", "error": "rotation_degrees must contain only finite numeric values"}
    return None


def set_object_rotation(file_name, object_name, rotation_degrees):
    blend_path = validate_blend_file(file_name)
    validation_error = _validate_rotation_degrees(rotation_degrees)
    if validation_error:
        return validation_error
    target = [float(value) for value in rotation_degrees]

    script = f"""
import bpy
import json
import math

object_name = {object_name!r}
target = {target!r}
obj = bpy.data.objects.get(object_name)

if obj is None:
    result = {{"status": "object_not_found", "object_name": object_name}}
elif obj.rotation_mode != "XYZ":
    obj.rotation_mode = "XYZ"
    current = [math.degrees(angle) for angle in obj.rotation_euler]
    if all(abs(current[index] - target[index]) <= 1e-5 for index in range(3)):
        result = {{"status": "already_rotated", "object_name": object_name, "rotation_degrees": current}}
    else:
        obj.rotation_euler = tuple(math.radians(value) for value in target)
        bpy.ops.wm.save_as_mainfile(filepath={blend_path!r})
        result = {{"status": "ok", "object_name": object_name, "rotation_degrees": [math.degrees(angle) for angle in obj.rotation_euler]}}
elif all(abs(math.degrees(angle) - target[index]) <= 1e-5 for index, angle in enumerate(obj.rotation_euler)):
    result = {{"status": "already_rotated", "object_name": object_name, "rotation_degrees": [math.degrees(angle) for angle in obj.rotation_euler]}}
else:
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
        "location": [
            float(obj.location.x),
            float(obj.location.y),
            float(obj.location.z),
        ],
        "rotation_degrees": [math.degrees(angle) for angle in obj.rotation_euler],
    }}

print("ATLAS_TRANSFORM_START")
print(json.dumps(result))
print("ATLAS_TRANSFORM_END")
"""
    return run_blender(blend_path, script, "ATLAS_TRANSFORM_START", "ATLAS_TRANSFORM_END")
