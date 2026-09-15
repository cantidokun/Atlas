import pytest

from planning.blender.scene_model import MeshModel
from planning.blender.topology_intelligence import analyze_topology


def mesh(mesh_id, vertices, faces):
    return MeshModel(mesh_id=mesh_id, vertices=tuple(vertices), faces=tuple(tuple(f) for f in faces))


def test_single_triangle_is_open_boundary_component():
    report = analyze_topology(mesh("tri", [(0,0,0),(1,0,0),(0,1,0)], [(0,1,2)]))
    assert report.vertex_count == 3
    assert report.referenced_vertex_count == 3
    assert report.isolated_vertex_count == 0
    assert report.edge_count == 3
    assert report.boundary_edge_count == 3
    assert report.manifold_edge_count == 0
    assert report.non_manifold_edge_count == 0
    assert report.connected_component_count == 1
    assert report.components[0].face_indices == (0,)


def test_tetrahedron_is_closed_manifold():
    report = analyze_topology(mesh(
        "tetra",
        [(0,0,0),(1,0,0),(0,1,0),(0,0,1)],
        [(0,2,1),(0,1,3),(1,2,3),(2,0,3)],
    ))
    assert report.edge_count == 6
    assert report.boundary_edge_count == 0
    assert report.manifold_edge_count == 6
    assert report.non_manifold_edge_count == 0
    assert report.max_edge_valence == 2


def test_disconnected_components_are_separate():
    report = analyze_topology(mesh(
        "two",
        [(0,0,0),(1,0,0),(0,1,0),(10,0,0),(11,0,0),(10,1,0)],
        [(0,1,2),(3,4,5)],
    ))
    assert report.connected_component_count == 2
    assert [c.component_id for c in report.components] == [0, 1]
    assert report.components[0].vertex_indices == (0,1,2)
    assert report.components[1].vertex_indices == (3,4,5)


def test_isolated_vertex_is_reported_but_not_fabricated_into_component():
    report = analyze_topology(mesh(
        "isolated",
        [(0,0,0),(1,0,0),(0,1,0),(99,99,99)],
        [(0,1,2)],
    ))
    assert report.vertex_count == 4
    assert report.referenced_vertex_count == 3
    assert report.isolated_vertex_count == 1
    assert report.components[0].vertex_indices == (0,1,2)


def test_non_manifold_edge_valence_three():
    report = analyze_topology(mesh(
        "nonmanifold",
        [(0,0,0),(1,0,0),(0,1,0),(0,-1,0),(0,0,1)],
        [(0,1,2),(1,0,3),(0,1,4)],
    ))
    assert report.non_manifold_edge_count == 1
    assert report.max_edge_valence == 3
    assert report.edge_valence_histogram == ((1, 6), (3, 1))


def test_mixed_face_cardinality_histogram():
    report = analyze_topology(mesh(
        "mixed",
        [(0,0,0),(1,0,0),(1,1,0),(0,1,0),(2,0,0),(2,1,0),(3,0,0),(3,1,0)],
        [(0,1,2),(0,2,3),(4,5,6,7)],
    ))
    assert report.triangle_count == 2
    assert report.quad_count == 1
    assert report.ngon_count == 0
    assert report.face_cardinality_histogram == ((3, 2), (4, 1))


def test_report_is_deterministic_and_to_dict_is_fresh():
    m = mesh("det", [(0,0,0),(1,0,0),(0,1,0),(9,9,9)], [(0,1,2)])
    a = analyze_topology(m)
    b = analyze_topology(m)
    assert a == b
    first = a.to_dict()
    first["components"][0]["face_indices"].append(99)
    assert a.components[0].face_indices == (0,)


def test_invalid_index_fails_closed():
    with pytest.raises(Exception):
        analyze_topology(mesh("bad", [(0,0,0),(1,0,0),(0,1,0)], [(0,1,3)]))
