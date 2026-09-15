import bpy
import json


def vec(v):
    return tuple(round(float(x), 8) for x in v)


def run_safe_case():
    mesh = bpy.data.meshes.new('Wave7Mesh')
    mesh.from_pydata(
        [
            (0, 0, 0),
            (1, 0, 0),
            (0, 1, 0),
            (1, 0, 0),
            (0, 1, 0),
            (3, 3, 3),
        ],
        [],
        [(0, 1, 2), (0, 3, 5)],
    )
    mesh.update()
    obj = bpy.data.objects.new('Wave7Target', mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = (3.0, 4.0, 5.0)
    obj.rotation_euler = (0.1, 0.2, 0.3)
    obj.scale = (1.2, 0.8, 1.5)
    other_mesh = bpy.data.meshes.new('Wave7OtherMesh')
    other_mesh.from_pydata([(20,20,20), (21,20,20), (20,21,20)], [], [(0,1,2)])
    other_mesh.update()
    other = bpy.data.objects.new('Wave7Other', other_mesh)
    bpy.context.collection.objects.link(other)

    before_vertices = tuple(vec(v.co) for v in mesh.vertices)
    before_faces = tuple(tuple(p.vertices) for p in mesh.polygons)
    before_matrix = tuple(tuple(round(float(x), 8) for x in row) for row in obj.matrix_world)
    before_other = tuple(vec(v.co) for v in other_mesh.vertices)
    before_file = bpy.data.filepath

    duplicates = {}
    for vertex in mesh.vertices:
        duplicates.setdefault(vec(vertex.co), []).append(vertex.index)
    groups = [tuple(indices) for indices in duplicates.values() if len(indices) >= 2]
    groups.sort()
    if groups != [(1,3), (2,4)]:
        raise RuntimeError('unexpected duplicate groups: %r' % (groups,))

    import bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    doomed_indices = [index for group in groups for index in group[1:]]
    doomed_vertices = [bm.verts[index] for index in doomed_indices]
    bmesh.ops.delete(bm, geom=doomed_vertices, context='VERTS')
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    after_vertices = tuple(vec(v.co) for v in mesh.vertices)
    after_faces = tuple(tuple(p.vertices) for p in mesh.polygons)
    after_matrix = tuple(tuple(round(float(x), 8) for x in row) for row in obj.matrix_world)
    after_other = tuple(vec(v.co) for v in other_mesh.vertices)

    checks = {
        'exact_duplicates_removed': len(mesh.vertices) == 4,
        'survivor_coordinates_preserved': after_vertices == (before_vertices[0], before_vertices[1], before_vertices[2], before_vertices[5]),
        'faces_preserved_by_remap': after_faces == ((0,1,2), (0,1,3)),
        'target_identity_preserved': obj.name == 'Wave7Target' and obj.data.name == 'Wave7Mesh',
        'transform_preserved': after_matrix == before_matrix,
        'unrelated_preserved': after_other == before_other,
        'no_file_path_mutation': bpy.data.filepath == before_file and before_file == '',
    }
    return checks


def run_collision_case():
    mesh = bpy.data.meshes.new('Wave7CollisionMesh')
    mesh.from_pydata(
        [(0,0,0), (1,0,0), (0,1,0), (1,0,0)],
        [],
        [(0,1,2), (0,3,2)],
    )
    mesh.update()
    referenced = {i for p in mesh.polygons for i in p.vertices}
    duplicates = {}
    for vertex in mesh.vertices:
        duplicates.setdefault(vec(vertex.co), []).append(vertex.index)
    groups = [tuple(indices) for indices in duplicates.values() if len(indices) >= 2]
    group = groups[0]
    same_face_collision = any(sum(index in group for index in p.vertices) >= 2 for p in mesh.polygons)
    remapped = tuple(tuple(group[0] if i == group[1] else i for i in p.vertices) for p in mesh.polygons)
    face_image_collision = len(set(remapped)) != len(remapped)
    return {
        'collision_detected': group == (1,3),
        'face_image_collision_detected': face_image_collision,
        'same_face_collision_absent': not same_face_collision,
        'source_faces_retained': tuple(tuple(p.vertices) for p in mesh.polygons) == ((0,1,2),(0,3,2)),
        'referenced_vertices_intact': referenced == {0,1,2,3},
    }


safe_checks = run_safe_case()
collision_checks = run_collision_case()
checks = {**{'safe_' + k: v for k, v in safe_checks.items()}, **{'collision_' + k: v for k, v in collision_checks.items()}}
if not all(checks.values()):
    raise RuntimeError('Wave7 live checks failed: %r' % checks)

print('ATLAS_WAVE7_DUPLICATE_VERTEX_LIVE_PASS')
print(json.dumps({'checks': checks, 'save_attempted': False}))
