"""Disposable Blender 4.4.x boundary probe for Wave 12.

This script proves only the real Blender detach primitive on an ACYCLIC parent
relationship, because Blender itself prevents constructing an illegal parent
cycle through the normal object API. Canonical cycle detection remains covered
by the engine-independent Wave-12 tests.
"""
from __future__ import annotations

import json

import bpy


def matrix_delta(a, b):
    return max(abs(float(a[r][c]) - float(b[r][c])) for r in range(4) for c in range(4))


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
    parent.scale = (1.25, 1.25, 1.25)

    child_data = bpy.data.meshes.new('wave12_child_mesh')
    child_data.from_pydata([(0, 0, 0), (0.5, 0, 0), (0, 0.5, 0)], [], [(0, 1, 2)])
    child = bpy.data.objects.new('wave12_child', child_data)
    scene.collection.objects.link(child)
    child.location = (0.5, 1.0, -0.25)
    child.rotation_euler = (0.3, 0.1, -0.2)
    child.scale = (0.8, 1.1, 0.9)

    child.parent = parent
    bpy.context.view_layer.update()

    before_world = child.matrix_world.copy()
    before_mesh_name = child.data.name
    object_names_before = tuple(sorted(o.name for o in scene.collection.objects))
    no_file_before = bpy.data.filepath == ''

    bpy.context.view_layer.objects.active = child
    child.select_set(True)
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    bpy.context.view_layer.update()

    after_world = child.matrix_world.copy()
    delta = matrix_delta(after_world, before_world)
    # Blender stores object transforms as 32-bit floats. The observed detach
    # delta is ~1.2e-7 on Blender 4.4.3, so the live boundary gate must allow
    # normal float32 round-off while still rejecting material transform drift.
    checks = {
        'parent_cleared': child.parent is None,
        'world_matrix_preserved': delta <= 1e-6,
        'object_identity_preserved': child.name == 'wave12_child',
        'mesh_identity_preserved': child.data.name == before_mesh_name,
        'objects_preserved': tuple(sorted(o.name for o in scene.collection.objects)) == object_names_before,
        'no_file_path_before': no_file_before,
        'no_file_path_after': bpy.data.filepath == '',
    }

    failed = [key for key, value in checks.items() if not value]
    payload = {
        'marker': 'ATLAS_WAVE12_PARENT_CYCLE_LIVE',
        'blender_version': list(bpy.app.version),
        'failed': failed,
        'matrix_max_delta': delta,
        'before_world': [[float(before_world[r][c]) for c in range(4)] for r in range(4)],
        'after_world': [[float(after_world[r][c]) for c in range(4)] for r in range(4)],
        'save_attempted': False,
        'opened_frozen_asset': False,
        'checks': checks,
    }
    print(json.dumps(payload, sort_keys=True))
    if tuple(bpy.app.version) != (4, 4, 3) or failed:
        raise SystemExit(1)
    print('ATLAS_WAVE12_PARENT_CYCLE_LIVE_PASS')


main()
