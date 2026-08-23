"""Explicitly scoped helpers for constructing deterministic Blender test fixtures."""
from __future__ import annotations

from .blender import run_blender, validate_blend_file


def create_test_object(file_name: str, object_name: str) -> dict:
    blend_path = validate_blend_file(file_name)
    if not object_name or object_name in {"Atlas_Marker", "Camera", "Cube", "Light"}:
        return {"error": "test object name is invalid or reserved"}
    script = f"""
import bpy, json
name = {object_name!r}
obj = bpy.data.objects.get(name)
if obj is None:
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    bpy.ops.wm.save_as_mainfile(filepath={blend_path!r})
    result = {{"status": "created", "object_name": name}}
elif obj.name == name:
    result = {{"status": "already_exists", "object_name": name}}
else:
    result = {{"status": "unexpected_name", "object_name": obj.name}}
print("ATLAS_TEST_FIXTURE_START")
print(json.dumps(result))
print("ATLAS_TEST_FIXTURE_END")
"""
    return run_blender(blend_path, script, "ATLAS_TEST_FIXTURE_START", "ATLAS_TEST_FIXTURE_END")


def set_test_transform(file_name: str, object_name: str, location: list[float], rotation: list[float]) -> dict:
    blend_path = validate_blend_file(file_name)
    if object_name in {"Atlas_Marker", "Camera", "Cube", "Light"}:
        return {"error": "test fixture cannot mutate reserved object"}
    script = f"""
import bpy, json
obj = bpy.data.objects.get({object_name!r})
if obj is None:
    result = {{"status": "object_not_found", "object_name": {object_name!r}}}
else:
    obj.location = {tuple(location)!r}
    obj.rotation_euler = tuple(__import__('math').radians(v) for v in {tuple(rotation)!r})
    bpy.ops.wm.save_as_mainfile(filepath={blend_path!r})
    result = {{"status": "ok", "object_name": obj.name}}
print("ATLAS_TEST_FIXTURE_START")
print(json.dumps(result))
print("ATLAS_TEST_FIXTURE_END")
"""
    return run_blender(blend_path, script, "ATLAS_TEST_FIXTURE_START", "ATLAS_TEST_FIXTURE_END")
