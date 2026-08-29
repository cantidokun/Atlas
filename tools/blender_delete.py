"""Controlled Blender object deletion with conservative safety checks."""

from .blender import run_blender, validate_blend_file

PROTECTED_TYPES = {"CAMERA", "LIGHT"}
PROTECTED_COLLECTIONS = {"Atlas_Protected"}


def delete_object(file_name, object_name):
    blend_path = validate_blend_file(file_name)
    script = f"""
import bpy
import json

object_name = {object_name!r}
obj = bpy.data.objects.get(object_name)

if obj is None:
    result = {{"status": "already_absent", "object_name": object_name, "mutation_performed": False}}
elif obj.type in {{"CAMERA", "LIGHT"}}:
    result = {{"status": "blocked", "error": "Protected object type", "object_name": object_name, "object_type": obj.type, "mutation_performed": False}}
elif any(collection.name == "Atlas_Protected" for collection in obj.users_collection):
    result = {{"status": "blocked", "error": "Protected collection membership", "object_name": object_name, "mutation_performed": False}}
elif len(obj.children) > 0:
    result = {{"status": "blocked", "error": "Object has child objects", "object_name": object_name, "mutation_performed": False}}
else:
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.wm.save_as_mainfile(filepath={blend_path!r})
    result = {{"status": "ok", "object_name": object_name, "mutation_performed": True}}

print("ATLAS_DELETE_START")
print(json.dumps(result))
print("ATLAS_DELETE_END")
"""
    return run_blender(blend_path, script, "ATLAS_DELETE_START", "ATLAS_DELETE_END")
