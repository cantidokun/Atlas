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
for v in sorted((bm.verts[i] for i in isolated), key=lambda x: x.index, reverse=True):
    bmesh.utils.vert_dissolve(bm, v, use_face_split=False) if False else None
# Isolated verts have no linked faces; delete only the explicitly selected vertices.
bmesh.ops.delete(bm, geom=[bm.verts[i] for i in isolated], context='VERTS')
bm.to_mesh(mesh)
bm.free()
mesh.update()

after_vertices = tuple(vec(v.co) for v in mesh.vertices)
after_faces = tuple(tuple(p.vertices) for p in mesh.polygons)
after_matrix = tuple(tuple(round(float(x), 8) for x in row) for row in obj.matrix_world)
after_other = tuple(vec(v.co) for v in other_mesh.vertices)

checks = {
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
print(json.dumps({'checks': checks, 'before_vertices': before_vertices, 'after_vertices': after_vertices, 'before_faces': before_faces, 'after_faces': after_faces, 'save_attempted': False}))
