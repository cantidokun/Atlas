"""Blender collection-membership inspection and controlled writes."""

from .blender import run_blender, validate_blend_file

TARGET_COLLECTION = "Atlas_Test"


def inspect_object_collections(file_name, object_name):
    blend_path = validate_blend_file(file_name)
    script = f"""
import bpy
import json

object_name = {object_name!r}
obj = bpy.data.objects.get(object_name)

if obj is None:
    # Missing object is valid negative evidence for conditional creation tasks.
    result = {{
        "object_name": object_name,
        "exists": False,
        "collections": [],
    }}
else:
    result = {{
        "object_name": obj.name,
        "exists": True,
        "collections": sorted(collection.name for collection in obj.users_collection),
    }}

print("ATLAS_COLLECTION_MEMBERSHIP_START")
print(json.dumps(result))
print("ATLAS_COLLECTION_MEMBERSHIP_END")
"""
    return run_blender(blend_path, script, "ATLAS_COLLECTION_MEMBERSHIP_START", "ATLAS_COLLECTION_MEMBERSHIP_END")


def move_object_to_collection(file_name, object_name, collection_name):
    blend_path = validate_blend_file(file_name)
    if collection_name != TARGET_COLLECTION:
        return {"error": f"For safety, this tool can only target the collection '{TARGET_COLLECTION}'."}

    script = f"""
import bpy
import json

object_name = {object_name!r}
collection_name = {collection_name!r}
obj = bpy.data.objects.get(object_name)
target = bpy.data.collections.get(collection_name)

if obj is None:
    result = {{"status": "error", "error": "Object not found", "object_name": object_name}}
elif target is None:
    result = {{"status": "error", "error": "Collection not found", "collection": collection_name}}
elif target in obj.users_collection and len(obj.users_collection) == 1:
    result = {{"status": "already_member", "object": object_name, "collection": collection_name}}
else:
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    target.objects.link(obj)
    bpy.ops.wm.save_as_mainfile(filepath={blend_path!r})
    result = {{"status": "moved", "object": object_name, "collection": collection_name}}

print("ATLAS_COLLECTION_WRITE_START")
print(json.dumps(result))
print("ATLAS_COLLECTION_WRITE_END")
"""
    return run_blender(blend_path, script, "ATLAS_COLLECTION_WRITE_START", "ATLAS_COLLECTION_WRITE_END")
