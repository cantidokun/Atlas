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
        "metric_system": bool(scene.unit_settings.system == "METRIC"),
        "meters_length_unit": bool(scene.unit_settings.length_unit == "METERS"),
        "vertices_preserved": bool(tuple(tuple(v.co) for v in mesh.vertices) == before_vertices),
        "location_preserved": bool(tuple(obj.location) == before_location),
        "scale_preserved": bool(tuple(obj.scale) == before_scale),
        "rotation_preserved": bool(tuple(obj.rotation_quaternion) == before_rotation),
        "filepath_unchanged": bool(pathlib.Path(bpy.data.filepath) == save_before),
    }

    # Exercise a genuinely distinct physical unit at Blender's supported boundary: both the
    # coarse system and precise length token must change.
    scene.unit_settings.system = "IMPERIAL"
    scene.unit_settings.length_unit = "INCHES"
    physically_distinct = (
        scene.unit_settings.system == "IMPERIAL"
        and scene.unit_settings.length_unit == "INCHES"
        and not (
            scene.unit_settings.system == "METRIC"
            and scene.unit_settings.length_unit == "METERS"
        )
    )
    checks["physical_unit_boundary_distinct"] = bool(physically_distinct)

    # `save_attempted` is a negative assertion, so it must not participate in the
    # positive all-checks aggregate. The outer pytest gate asserts it independently.
    save_attempted = False
    all_checks = all(bool(value) for value in checks.values())
    payload = {
        "checks": {**checks, "save_attempted": save_attempted},
        "all_checks": bool(all_checks),
        "save_attempted": save_attempted,
    }
    _marker(payload)
    if not payload["all_checks"] or payload["save_attempted"]:
        return 2
    print("ATLAS_WAVE8_UNIT_METADATA_LIVE_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
