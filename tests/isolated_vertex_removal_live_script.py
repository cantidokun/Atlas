import bpy
import json
import os


def vec(v):
    return tuple(round(float(x), 8) for x in v)


# Disposable in-memory scene. No file is opened or saved.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
mesh = bpy.data.meshes.new('Wave6Mesh')
mesh.from_pydata(
    [(0, 0, 0), (1, 0, 0), (0, 1, 0), (9, 9, 9), (8, 8, 8)],
    [],
    [(0, 1, 2)],
)
mesh.update()
obj = bpy.data.objects.new('Wave6Target', mesh)
bpy.context.collection.objects.link(obj)
# WAVE 14 material-slot fixture (RAW-BLENDER-BOUNDARY-ONLY evidence): two ASSIGNED data-linked slots
# with distinct names plus one UNASSIGNED data-linked slot, in a fixed order. The bmesh in-place
# primitive must leave this table untouched.
mesh.materials.append(bpy.data.materials.new('wave6_turf'))
mesh.materials.append(bpy.data.materials.new('wave6_line_markings'))
mesh.materials.append(None)


def slot_table(target):
    return [[str(slot.link), (slot.material.name if slot.material else None)]
            for slot in target.material_slots]


before_slots = slot_table(obj)
if (len(before_slots) != 3 or before_slots[0][1] is None or before_slots[1] is None
        or before_slots[2][1] is not None):
    raise RuntimeError('WAVE 14 anti-vacuity: expected 2 assigned + 1 unassigned slot, got %r'
                       % (before_slots,))

obj.location = (3.0, 4.0, 5.0)
obj.rotation_euler = (0.1, 0.2, 0.3)
obj.scale = (1.2, 0.8, 1.5)
other_mesh = bpy.data.meshes.new('Wave6OtherMesh')
other_mesh.from_pydata([(20, 20, 20), (21, 20, 20), (20, 21, 20)], [], [(0, 1, 2)])
other_mesh.update()
other = bpy.data.objects.new('Wave6Other', other_mesh)
bpy.context.collection.objects.link(other)

before_vertices = tuple(vec(v.co) for v in mesh.vertices)
before_faces = tuple(tuple(p.vertices) for p in mesh.polygons)
before_matrix = tuple(tuple(round(float(x), 8) for x in row) for row in obj.matrix_world)
before_other = tuple(vec(v.co) for v in other_mesh.vertices)
before_file = bpy.data.filepath

referenced = {i for p in mesh.polygons for i in p.vertices}
isolated = tuple(i for i in range(len(mesh.vertices)) if i not in referenced)
if isolated != (3, 4):
    raise RuntimeError('unexpected isolated set: %r' % (isolated,))

# Engine-side validation primitive. This is deliberately outside the pure canonical executor.
# Direct mesh vertex removal with bmesh is deterministic and keeps the operation narrowly scoped.
import bmesh
bm = bmesh.new()
bm.from_mesh(mesh)
bm.verts.ensure_lookup_table()
selected_vertices = [bm.verts[i] for i in isolated]
bmesh.ops.delete(bm, geom=selected_vertices, context='VERTS')
bm.to_mesh(mesh)
bm.free()
mesh.update()

after_vertices = tuple(vec(v.co) for v in mesh.vertices)
after_faces = tuple(tuple(p.vertices) for p in mesh.polygons)
after_matrix = tuple(tuple(round(float(x), 8) for x in row) for row in obj.matrix_world)
after_other = tuple(vec(v.co) for v in other_mesh.vertices)
after_slots = slot_table(obj)

checks = {
    'material_slots_preserved': after_slots == before_slots,
    'material_slot_count_preserved': len(after_slots) == len(before_slots),
    'material_slot_order_and_names_preserved':
        [s[1] for s in after_slots] == [s[1] for s in before_slots],
    'unassigned_slot_still_unassigned': after_slots[2] == ['DATA', None],
    'isolated_removed_only': len(mesh.vertices) == 3 and not ({i for p in mesh.polygons for i in p.vertices} ^ {0, 1, 2}),
    'surviving_vertices_preserved': after_vertices == before_vertices[:3],
    'face_semantics_preserved': after_faces == ((0, 1, 2),),
    'target_identity_preserved': obj.name == 'Wave6Target' and obj.data.name == 'Wave6Mesh',
    'transform_preserved': after_matrix == before_matrix,
    'unrelated_preserved': after_other == before_other,
    'no_save_attempt': bpy.data.filepath == before_file and before_file == '',
}
if not all(checks.values()):
    raise RuntimeError('Wave6 live checks failed: %r' % checks)

print('ATLAS_WAVE6_ISOLATED_VERTEX_LIVE_PASS')
print(json.dumps({'checks': checks, 'before_vertices': before_vertices, 'after_vertices': after_vertices, 'before_faces': before_faces, 'after_faces': after_faces, 'before_slots': before_slots, 'after_slots': after_slots, 'save_attempted': False}))
