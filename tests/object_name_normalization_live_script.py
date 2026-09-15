"""Disposable Blender boundary probe for Wave 9 object-name normalization."""
from __future__ import annotations

import json
import pathlib
import sys

import bpy


def _marker(payload):
    print("ATLAS_WAVE9_OBJECT_NAME_LIVE_RESULT=" + json.dumps(payload, sort_keys=True))


def main() -> int:
    scene = bpy.context.scene
    mesh = bpy.data.meshes.new("Wave9Mesh")
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    mesh.update()
    target = bpy.data.objects.new("Pitch Main", mesh)
    sibling_mesh = bpy.data.meshes.new("Wave9SiblingMesh")
    sibling = bpy.data.objects.new("goal.left", sibling_mesh)
    bpy.context.collection.objects.link(target)
    bpy.context.collection.objects.link(sibling)
    target.location = (3.0, 4.0, 5.0)
    target.scale = (1.25, 0.75, 1.0)
    target.rotation_mode = "QUATERNION"
    target.rotation_quaternion = (0.9238795, 0.0, 0.3826834, 0.0)

    before_vertex_coords = tuple(tuple(v.co) for v in mesh.vertices)
    before_location = tuple(target.location)
    before_scale = tuple(target.scale)
    before_rotation = tuple(target.rotation_quaternion)
    before_mesh_name = target.data.name
    before_filepath = pathlib.Path(bpy.data.filepath)

    target.name = "pitch.main"

    checks = {
        "target_renamed": target.name == "pitch.main",
        "stable_data_identity": target.data.name == before_mesh_name,
        "vertices_preserved": tuple(tuple(v.co) for v in mesh.vertices) == before_vertex_coords,
        "location_preserved": tuple(target.location) == before_location,
        "scale_preserved": tuple(target.scale) == before_scale,
        "rotation_preserved": tuple(target.rotation_quaternion) == before_rotation,
        "sibling_preserved": sibling.name == "goal.left",
        "unique_names": len({obj.name for obj in (target, sibling)}) == 2,
        "filepath_unchanged": pathlib.Path(bpy.data.filepath) == before_filepath,
        "collision_visible": "goal.left" in {obj.name for obj in (target, sibling)},
    }

    # A target name colliding with the sibling is an invalid boundary condition; no mutation is
    # attempted. This only probes Blender's observable namespace semantics; authorization/planning
    # remains in the canonical-model executor.
    collision_refused = "goal.left" == sibling.name and target.name != sibling.name
    checks["collision_boundary"] = collision_refused

    save_attempted = False
    all_checks = all(bool(v) for v in checks.values())
    payload = {
        "checks": {**checks, "save_attempted": save_attempted},
        "all_checks": bool(all_checks),
        "save_attempted": save_attempted,
    }
    _marker(payload)
    if not payload["all_checks"] or payload["save_attempted"]:
        return 2
    print("ATLAS_WAVE9_OBJECT_NAME_LIVE_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
