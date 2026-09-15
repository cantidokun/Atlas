"""Boundary-faithful Blender live validation for Wave 4 parent-reference repair.

This script deliberately validates the Blender-side primitive rather than attempting
 to manufacture a dangling bpy.types.Object.parent reference. Blender maintains ID
relationships and normally clears an invalid parent relationship when the parent
object is removed. The canonical malformed-reference case is therefore validated
outside the bpy boundary; this script proves the live detach semantics and
preservation guarantees that Wave 4 relies on.

The script is disposable/in-memory only. It never opens the frozen Atlas asset and
never saves a .blend file.
"""

from __future__ import annotations

import json
import math
import sys
from typing import Any

import bpy
from mathutils import Matrix, Vector


MARKER = "ATLAS_WAVE4_PARENT_REFERENCE_LIVE"


def _matrix_close(a: Matrix, b: Matrix, tol: float = 1e-6) -> bool:
    return all(abs(a[r][c] - b[r][c]) <= tol for r in range(4) for c in range(4))


def _vec_close(a: Vector, b: Vector, tol: float = 1e-6) -> bool:
    return all(abs(a[i] - b[i]) <= tol for i in range(len(a)))


def main() -> int:
    # Start from a disposable empty scene. No existing Atlas asset is touched.
    bpy.ops.wm.read_factory_settings(use_empty=True)

    mesh = bpy.data.meshes.new("atlas_wave4_mesh")
    mesh.from_pydata(
        [(-1.0, -1.0, 0.0), (1.0, -1.0, 0.0), (0.0, 1.0, 0.5)],
        [],
        [(0, 1, 2)],
    )
    mesh.update()

    child = bpy.data.objects.new("atlas_wave4_child", mesh)
    parent = bpy.data.objects.new("atlas_wave4_parent", None)
    bpy.context.scene.collection.objects.link(child)
    bpy.context.scene.collection.objects.link(parent)

    # Non-trivial local transforms make accidental transform loss observable.
    child.location = (2.25, -3.5, 1.75)
    child.rotation_euler = (0.2, -0.35, 0.4)
    child.scale = (1.25, 0.8, 1.1)
    parent.location = (-4.0, 2.0, 1.5)
    parent.rotation_euler = (0.1, 0.3, -0.2)
    parent.scale = (1.4, 0.9, 1.2)

    bpy.context.view_layer.update()

    # Establish a non-trivial parent inverse so CLEAR_KEEP_TRANSFORM has real work.
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()
    bpy.context.view_layer.update()

    before_parent = child.parent
    before_world = child.matrix_world.copy()
    before_location = child.location.copy()
    before_rotation = child.rotation_quaternion.copy()
    before_scale = child.scale.copy()
    before_name = child.name
    before_data_name = child.data.name
    before_object_names = tuple(sorted(obj.name for obj in bpy.context.scene.objects))
    before_file = bpy.data.filepath

    if before_parent is not parent:
        raise AssertionError("setup did not establish the expected parent")

    # This is the exact Blender-side primitive used by the Wave 4 live proof.
    bpy.context.view_layer.objects.active = child
    child.select_set(True)
    parent.select_set(False)
    result = bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.context.view_layer.update()

    after_world = child.matrix_world.copy()
    after_location = child.location.copy()
    after_rotation = child.rotation_quaternion.copy()
    after_scale = child.scale.copy()
    after_object_names = tuple(sorted(obj.name for obj in bpy.context.scene.objects))

    checks: dict[str, Any] = {
        "operator_result": list(result),
        "parent_cleared": child.parent is None,
        "world_matrix_preserved": _matrix_close(before_world, after_world),
        "location_preserved": _vec_close(before_location, after_location),
        "rotation_preserved": _vec_close(before_rotation, after_rotation),
        "scale_preserved": _vec_close(before_scale, after_scale),
        "object_identity_preserved": child.name == before_name,
        "mesh_identity_preserved": child.data.name == before_data_name,
        "objects_preserved": after_object_names == before_object_names,
        "parent_datablock_preserved": parent.name in bpy.data.objects,
        "no_file_path_before": before_file == "",
        "no_file_path_after": bpy.data.filepath == "",
    }

    failed = [name for name, value in checks.items() if value is not True and name != "operator_result"]
    if result != {"FINISHED"}:
        failed.append("operator_result")

    payload = {
        "marker": MARKER,
        "blender_version": tuple(bpy.app.version),
        "checks": checks,
        "failed": failed,
        "save_attempted": False,
        "opened_frozen_asset": False,
    }
    print(json.dumps(payload, sort_keys=True))

    if failed:
        return 1

    print(f"{MARKER}_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
