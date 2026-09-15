"""Disposable Blender probe for Wave 5 topology intelligence.

Blender is used only to provide an independent source topology. The expected
metrics are calculated directly from bpy mesh polygons/vertices in this probe;
the canonical Atlas analyzer remains engine-independent and is validated
separately against the resulting canonical MeshModel.

No Atlas asset is opened and no .blend file is saved.
"""

import json
import sys

import bpy

MARKER = "ATLAS_WAVE5_TOPOLOGY_LIVE"


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)

    mesh = bpy.data.meshes.new("atlas_wave5_live_mesh")
    mesh.from_pydata(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (10.0, 10.0, 10.0),
        ],
        [],
        [(0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)],
    )
    mesh.update()
    obj = bpy.data.objects.new("atlas_wave5_live_object", mesh)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.update()

    vertices = len(mesh.vertices)
    polygons = tuple(tuple(poly.vertices) for poly in mesh.polygons)
    referenced = {index for face in polygons for index in face}
    edges = set()
    edge_valence = {}
    for face in polygons:
        for i, a in enumerate(face):
            b = face[(i + 1) % len(face)]
            edge = (a, b) if a < b else (b, a)
            edges.add(edge)
            edge_valence[edge] = edge_valence.get(edge, 0) + 1

    valences = {}
    for valence in edge_valence.values():
        valences[valence] = valences.get(valence, 0) + 1

    checks = {
        "vertex_count": vertices == 5,
        "face_count": len(polygons) == 4,
        "edge_count": len(edges) == 6,
        "boundary_edges": sum(1 for value in edge_valence.values() if value == 1) == 0,
        "manifold_edges": sum(1 for value in edge_valence.values() if value == 2) == 6,
        "non_manifold_edges": sum(1 for value in edge_valence.values() if value > 2) == 0,
        "max_edge_valence": max(edge_valence.values()) == 2,
        "isolated_vertices": vertices - len(referenced) == 1,
        "triangle_faces": sum(1 for face in polygons if len(face) == 3) == 4,
        "objects_preserved": tuple(obj.name for obj in bpy.context.scene.objects) == (obj.name,),
        "no_file_path": bpy.data.filepath == "",
    }
    failed = [key for key, value in checks.items() if value is not True]
    payload = {
        "marker": MARKER,
        "blender_version": tuple(bpy.app.version),
        "checks": checks,
        "failed": failed,
        "source_vertex_count": vertices,
        "source_face_count": len(polygons),
        "source_edge_count": len(edges),
        "source_edge_valence_histogram": sorted(valences.items()),
        "source_faces": polygons,
        "save_attempted": False,
        "opened_frozen_asset": False,
    }
    print(json.dumps(payload, sort_keys=True))
    if failed:
        return 1
    print(MARKER + "_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
