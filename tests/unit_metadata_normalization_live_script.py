"""Disposable Blender boundary probe for Wave 8 unit metadata normalization."""
from __future__ import annotations

import json
import pathlib
import sys

import bpy


def _marker(payload):
    print("ATLAS_WAVE8_UNIT_METADATA_LIVE_RESULT=" + json.dumps(payload, sort_keys=True))


def main() -> int:
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    mesh = bpy.data.meshes.new("Wave8Mesh")
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    mesh.update()
    obj = bpy.data.objects.new("Wave8Target", mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = (3.0, 4.0, 5.0)
    before_vertices = tuple(tuple(v.co) for v in mesh.vertices)
    before_location = tuple(obj.location)
    before_scale = tuple(obj.scale)
    before_rotation = tuple(obj.rotation_quaternion)
    save_before = pathlib.Path(bpy.data.filepath)

    obj.data.update()

    checks = {
        "metric_system": scene.unit_settings.system == "METRIC",
        "meters_length_unit": scene.unit_settings.length_unit == "METERS",
        "vertices_preserved": tuple(tuple(v.co) for v in mesh.vertices) == before_vertices,
        "location_preserved": tuple(obj.location) == before_location,
        "scale_preserved": tuple(obj.scale) == before_scale,
        "rotation_preserved": tuple(obj.rotation_quaternion) == before_rotation,
        "filepath_unchanged": pathlib.Path(bpy.data.filepath) == save_before,
        "save_attempted": False,
    }

    scene.unit_settings.system = "IMPERIAL"
    physically_distinct = scene.unit_settings.system == "IMPERIAL"
    checks["physical_unit_boundary_distinct"] = physically_distinct

    payload = {
        "checks": checks,
        "all_checks": all(checks.values()),
        "save_attempted": False,
    }
    _marker(payload)
    if not payload["all_checks"]:
        return 2
    print("ATLAS_WAVE8_UNIT_METADATA_LIVE_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
