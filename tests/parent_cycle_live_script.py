"""Disposable Blender 4.4.x boundary probe for Wave 12.

This script proves only the real Blender detach primitive on an ACYCLIC parent
relationship, because Blender itself prevents constructing an illegal parent
cycle through the normal object API. Canonical cycle detection remains covered
by the engine-independent Wave-12 tests.
"""
from __future__ import annotations

import json
import math

import bpy


def vec_close(a, b, tol=1e-7):
    return all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def mat_close(a, b, tol=1e-7):
    return all(abs(float(a[r][c]) - float(b[r][c])) <= tol for r in range(4) for c in range(4))


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'

    parent_data = bpy.data.meshes.new('wave12_parent_mesh')
    parent_data.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    parent = bpy.data.objects.new('wave12_parent', parent_data)
    scene.collection.objects.link(parent)
    parent.location = (2.0, 3.0, 4.0)
    parent.rotation_euler = (0.2, -0.3, 0.1)
    parent.scale = (1.25, 0.75, 1.5)

    child_data = bpy.data.meshes.new('wave12_child_mesh')
    child_data.from_pydata([(0, 0, 0), (0.5, 0, 0), (0, 0.5, 0)], [], [(0, 1, 2)])
    child = bpy.data.objects.new('wave12_child', child_data)
    scene.collection.objects.link(child)
    child.location = (0.5, 1.0, -0.25)
    child.rotation_euler = (0.3, 0.1, -0.2)
    child.scale = (0.8, 1.1, 0.9)

    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()

    before_world = child.matrix_world.copy()
    before_location = tuple(child.location)
    before_rotation = tuple(child.rotation_euler)
    before_scale = tuple(child.scale)
    before_parent_mesh = child.parent.data.name
    object_names_before = tuple(sorted(o.name for o in scene.collection.objects))
    no_file_before = bpy.data.filepath == ''

    # Blender-side implementation primitive corresponding to the bounded semantic detach.
    child.parent = None
    child.matrix_world = before_world

    checks = {
        'parent_cleared': child.parent is None,
        'world_matrix_preserved': mat_close(child.matrix_world, before_world),
        'location_preserved': vec_close(child.location, before_location),
        'rotation_preserved': vec_close(child.rotation_euler, before_rotation),
        'scale_preserved': vec_close(child.scale, before_scale),
        'object_identity_preserved': child.name == 'wave12_child',
        'mesh_identity_preserved': child.data.name == before_parent_mesh,
        'objects_preserved': tuple(sorted(o.name for o in scene.collection.objects)) == object_names_before,
        'no_file_path_before': no_file_before,
        'no_file_path_after': bpy.data.filepath == '',
    }

    failed = [key for key, value in checks.items() if not value]
    payload = {
        'marker': 'ATLAS_WAVE12_PARENT_CYCLE_LIVE',
        'blender_version': list(bpy.app.version),
        'failed': failed,
        'save_attempted': False,
        'opened_frozen_asset': False,
        'checks': checks,
    }
    print(json.dumps(payload, sort_keys=True))
    if tuple(bpy.app.version) != (4, 4, 3) or failed:
        raise SystemExit(1)
    print('ATLAS_WAVE12_PARENT_CYCLE_LIVE_PASS')


main()
