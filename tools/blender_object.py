"""Controlled Blender object metadata operations."""
from .blender import run_blender, validate_blend_file


def rename_object(file_name, object_name, new_name):
    blend_path = validate_blend_file(file_name)
    if not new_name or new_name in {"", ".", ".."}:
        return {"error": "New object name must be non-empty."}
    script = f"""
import bpy
import json

object_name = {object_name!r}
new_name = {new_name!r}
obj = bpy.data.objects.get(object_name)
if obj is None:
    result = {{"status": "object_not_found", "object_name": object_name}}
elif bpy.data.objects.get(new_name) is not None and new_name != object_name:
    result = {{"status": "name_conflict", "object_name": object_name, "new_name": new_name}}
elif obj.name == new_name:
    result = {{"status": "already_named", "object_name": object_name, "new_name": new_name}}
else:
    old_name = obj.name
    obj.name = new_name
    bpy.ops.wm.save_as_mainfile(filepath={blend_path!r})
    result = {{"status": "renamed", "old_name": old_name, "new_name": obj.name}}

print("ATLAS_RENAME_START")
print(json.dumps(result))
print("ATLAS_RENAME_END")
"""
    return run_blender(blend_path, script, "ATLAS_RENAME_START", "ATLAS_RENAME_END")
