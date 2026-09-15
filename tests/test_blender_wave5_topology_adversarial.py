"""Hostile deterministic cases for the Wave 5 topology intelligence boundary."""

import copy

import pytest

from planning.blender.scene_model import MeshModel
from planning.blender.topology_intelligence import analyze_topology
from planning.blender.topology_serialization import topology_report_from_dict


def _mesh(faces=((0, 1, 2),)):
    return MeshModel(
        mesh_id="adversarial",
        vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0)),
        faces=tuple(tuple(face) for face in faces),
    )


def _report_dict():
    return analyze_topology(_mesh()).to_dict()


@pytest.mark.parametrize(
    "mutator",
    [
        lambda d: d.update(schema_version=1),
        lambda d: d.update(mesh_id=1),
        lambda d: d.update(vertex_count=True),
        lambda d: d.update(edge_count=-1),
        lambda d: d.update(edge_valence_histogram=[[1, 3], [1, 0]]),
        lambda d: d.update(edge_valence_histogram=[[0, 3]]),
        lambda d: d.update(face_cardinality_histogram=[[3, 1], [2, 1]]),
        lambda d: d.update(components=[]),
        lambda d: d["components"].__setitem__(0, dict(d["components"][0], component_id=99)),
        lambda d: d["components"].__setitem__(0, dict(d["components"][0], face_indices=[0, 0])),
        lambda d: d["components"].__setitem__(0, dict(d["components"][0], vertex_indices=[2, 1, 0])),
        lambda d: d["components"].__setitem__(0, dict(d["components"][0], edge_count=999)),
        lambda d: d["components"].__setitem__(0, dict(d["components"][0], face_indices=[])),
        lambda d: d["components"].append(dict(d["components"][0])),
    ],
)
def test_hostile_report_mutations_fail_closed(mutator):
    raw = copy.deepcopy(_report_dict())
    mutator(raw)
    with pytest.raises((ValueError, TypeError)):
        topology_report_from_dict(raw)


def test_analyzer_is_not_mutative():
    mesh = _mesh()
    before = (mesh.vertices, mesh.faces)
    analyze_topology(mesh)
    assert (mesh.vertices, mesh.faces) == before


def test_repeated_face_edge_is_counted_deterministically():
    report = analyze_topology(_mesh(faces=((0, 1, 2), (0, 1, 2))))
    assert report.edge_count == 3
    assert report.edge_valence_histogram == ((2, 3),)
    assert report.boundary_edge_count == 0
    assert report.manifold_edge_count == 3
