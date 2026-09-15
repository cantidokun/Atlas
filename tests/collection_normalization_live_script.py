"""Disposable Blender boundary probe for Wave 10 object-collection normalization."""
from __future__ import annotations

import json
import pathlib
import sys

import bpy


def _marker(payload):
    print("ATLAS_WAVE10_COLLECTION_LIVE_RESULT=" + json.dumps(payload, sort_keys=True))


def main() -> int:
    scene = bpy.context.scene
    offworld = bpy.data.collections.new("Offworld")
    field = bpy.data.collections.new("Field")
    goals = bpy.data.collections.new("Goals")
    scene.collection.children.link(offworld)
    scene.collection.children.link(field)
    scene.collection.children.link(goals)

    mesh = bpy.data.meshes.new("Wave10Mesh")
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    mesh.update()
    target = bpy.data.objects.new("pitch", mesh)
    offworld.objects.link(target)

    sibling_mesh = bpy.data.meshes.new("Wave10SiblingMesh")
    sibling = bpy.data.objects.new("goal", sibling_mesh)
    field.objects.link(sibling)

    target.location = (3.0, 4.0, 5.0)
    target.scale = (1.25, 0.75, 1.0)
    target.rotation_mode = "QUATERNION"
    target.rotation_quaternion = (0.9238795, 0.0, 0.3826834, 0.0)

    before_vertex_coords = tuple(tuple(v.co) for v in mesh.vertices)
    before_location = tuple(target.location)
    before_scale = tuple(target.scale)
    before_rotation = tuple(target.rotation_quaternion)
    before_mesh_name = target.data.name
    before_sibling_collection = tuple(c.name for c in sibling.users_collection)
    before_filepath = pathlib.Path(bpy.data.filepath)

    offworld.objects.unlink(target)
    field.objects.link(target)

    target_collections = tuple(c.name for c in target.users_collection)
    checks = {
        "target_moved_to_explicit_collection": target_collections == ("Field",),
        "stable_data_identity": target.data.name == before_mesh_name,
        "vertices_preserved": tuple(tuple(v.co) for v in mesh.vertices) == before_vertex_coords,
        "location_preserved": tuple(target.location) == before_location,
        "scale_preserved": tuple(target.scale) == before_scale,
        "rotation_preserved": tuple(target.rotation_quaternion) == before_rotation,
        "sibling_preserved": tuple(c.name for c in sibling.users_collection) == before_sibling_collection,
        "target_name_preserved": target.name == "pitch",
        "filepath_unchanged": pathlib.Path(bpy.data.filepath) == before_filepath,
        "allowlist_boundary_visible": "Goals" not in target_collections,
    }

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
    print("ATLAS_WAVE10_COLLECTION_LIVE_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
