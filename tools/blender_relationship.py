"""Relationship-changing Blender operations for the Atlas agent."""

import json

from .blender import run_blender, validate_blend_file


ALLOWED_CHILD = "Atlas_Marker"
ALLOWED_PARENT = "Goal_Left_post"


def inspect_object_parent(file_name, object_name):
    blend_path = validate_blend_file(file_name)
    script = f"""
import bpy
import json

object_name = {object_name!r}
obj = bpy.data.objects.get(object_name)

if obj is None:
    result = {{"status": "error", "error": "Object not found", "object_name": object_name}}
else:
    result = {{
        "status": "inspected",
        "object_name": obj.name,
        "parent_name": obj.parent.name if obj.parent else None,
        "parent_type": obj.parent.type if obj.parent else None,
    }}

print("ATLAS_PARENT_START")
print(json.dumps(result))
print("ATLAS_PARENT_END")
"""
    return run_blender(blend_path, script, "ATLAS_PARENT_START", "ATLAS_PARENT_END")


def parent_object(file_name, child_name, parent_name):
    blend_path = validate_blend_file(file_name)

    if child_name != ALLOWED_CHILD:
        return {"status": "error", "error": "For safety, this tool can only parent Atlas_Marker."}
    if parent_name != ALLOWED_PARENT:
        return {"status": "error", "error": "For safety, this tool can only use Goal_Left_post as the parent."}
    if child_name == parent_name:
        return {"status": "error", "error": "An object cannot parent itself."}

    script = f"""
import bpy
import json

child_name = {child_name!r}
parent_name = {parent_name!r}
child = bpy.data.objects.get(child_name)
parent = bpy.data.objects.get(parent_name)

if child is None:
    result = {{"status": "error", "error": "Child object not found", "child_name": child_name}}
elif parent is None:
    result = {{"status": "error", "error": "Parent object not found", "parent_name": parent_name}}
elif child == parent:
    result = {{"status": "error", "error": "An object cannot parent itself"}}
elif child.parent == parent:
    result = {{"status": "already_parented", "child": child_name, "parent": parent_name}}
else:
    previous_parent = child.parent.name if child.parent else None
    child.parent = parent
    bpy.ops.wm.save_as_mainfile(filepath={blend_path!r})
    result = {{
        "status": "parented",
        "child": child_name,
        "parent": parent_name,
        "previous_parent": previous_parent,
    }}

print("ATLAS_PARENT_WRITE_START")
print(json.dumps(result))
print("ATLAS_PARENT_WRITE_END")
"""
    return run_blender(blend_path, script, "ATLAS_PARENT_WRITE_START", "ATLAS_PARENT_WRITE_END")
