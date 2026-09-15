"""Deterministic tests for the mesh-geometry checks. No Blender/bpy."""

import pytest

from planning.blender import FindingCode, check_mesh, check_mesh_in_envelope
from planning.blender.scene_model import MeshModel


def _codes(mesh: MeshModel):
    return sorted(f.code.value for f in check_mesh(mesh))


def test_nonfinite_coordinate_rejected_at_construction():
    with pytest.raises(ValueError):
        MeshModel(mesh_id="m", vertices=((0, 0, float("nan")), (1, 0, 0), (0, 1, 0)), faces=((0, 1, 2),))


def test_invalid_vertex_index():
    mesh = MeshModel(mesh_id="m", vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0)), faces=((0, 1, 7),))
    assert FindingCode.MESH_INVALID_INDEX.value in _codes(mesh)


def test_valid_index_no_invalid_finding():
    mesh = MeshModel(mesh_id="m", vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0)), faces=((0, 1, 2),))
    assert FindingCode.MESH_INVALID_INDEX.value not in _codes(mesh)


def test_duplicate_vertex():
    mesh = MeshModel(
        mesh_id="m",
        vertices=((0, 0, 0), (0, 0, 0), (1, 0, 0), (0, 1, 0)),
        faces=((0, 2, 3), (1, 2, 3)),
    )
    assert FindingCode.MESH_DUPLICATE_VERTEX.value in _codes(mesh)


def test_duplicate_face():
    mesh = MeshModel(mesh_id="m", vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0)), faces=((0, 1, 2), (0, 1, 2)))
    assert FindingCode.MESH_DUPLICATE_FACE.value in _codes(mesh)


def test_degenerate_collinear_face():
    mesh = MeshModel(mesh_id="m", vertices=((0, 0, 0), (1, 0, 0), (2, 0, 0)), faces=((0, 1, 2),))
    assert FindingCode.MESH_DEGENERATE_FACE.value in _codes(mesh)


def test_degenerate_repeated_index_face_rejected():
    with pytest.raises(ValueError):
        MeshModel(mesh_id="m", vertices=((0, 0, 0), (1, 0, 0)), faces=((0, 0, 1),))


def test_non_manifold_edge():
    mesh = MeshModel(
        mesh_id="m",
        vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, -1, 0), (1, 1, 0)),
        faces=((0, 1, 2), (0, 3, 1), (0, 1, 4)),
    )
    assert FindingCode.MESH_NON_MANIFOLD_EDGE.value in _codes(mesh)


def test_boundary_edge_not_error():
    mesh = MeshModel(mesh_id="m", vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0)), faces=((0, 1, 2),))
    assert FindingCode.MESH_NON_MANIFOLD_EDGE.value not in _codes(mesh)


def test_winding_inconsistency_detected():
    mesh = MeshModel(
        mesh_id="m",
        vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)),
        faces=((0, 1, 2), (0, 1, 3)),
    )
    assert FindingCode.MESH_WINDING_INCONSISTENT.value in _codes(mesh)


def test_consistent_winding_no_finding():
    mesh = MeshModel(
        mesh_id="m",
        vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)),
        faces=((0, 1, 2), (1, 3, 2)),
    )
    assert FindingCode.MESH_WINDING_INCONSISTENT.value not in _codes(mesh)


def test_normal_consistency_ok_and_mismatch():
    ok = MeshModel(
        mesh_id="m",
        vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0)),
        faces=((0, 1, 2),),
        normals=((0, 0, 1),),
    )
    assert FindingCode.MESH_NORMAL_INCONSISTENT.value not in _codes(ok)
    bad = MeshModel(
        mesh_id="m",
        vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0)),
        faces=((0, 1, 2),),
        normals=((1, 0, 0),),
    )
    assert FindingCode.MESH_NORMAL_INCONSISTENT.value in _codes(bad)


def test_unavailable_normals_not_a_finding():
    mesh = MeshModel(mesh_id="m", vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0)), faces=((0, 1, 2),))
    assert FindingCode.MESH_NORMAL_INCONSISTENT.value not in _codes(mesh)


def test_scale_out_of_range_and_inside():
    big = MeshModel(mesh_id="m", vertices=((2000, 0, 0), (1, 0, 0), (0, 1, 0)), faces=((0, 1, 2),))
    found = check_mesh_in_envelope(big, (-50, -40, 0), (50, 40, 12))
    assert any(f.code is FindingCode.MESH_SCALE_OUT_OF_RANGE for f in found)
    small = MeshModel(mesh_id="m", vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0)), faces=((0, 1, 2),))
    assert check_mesh_in_envelope(small, (-50, -40, 0), (50, 40, 12)) == []


def test_scale_offset_applies():
    mesh = MeshModel(mesh_id="m", vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0)), faces=((0, 1, 2),))
    assert check_mesh_in_envelope(mesh, (0, 0, 0), (2, 2, 2)) == []
    # world_vertices are the caller-computed world-space positions (e.g. an object translated
    # by +100 on x); the envelope check itself performs no transform math.
    world = tuple((v[0] + 100, v[1], v[2]) for v in mesh.vertices)
    assert any(
        f.code is FindingCode.MESH_SCALE_OUT_OF_RANGE
        for f in check_mesh_in_envelope(mesh, (0, 0, 0), (2, 2, 2), world_vertices=world)
    )
