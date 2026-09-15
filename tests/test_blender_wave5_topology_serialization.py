import copy
import pytest

from planning.blender.scene_model import MeshModel
from planning.blender.topology_intelligence import analyze_topology
from planning.blender.topology_serialization import topology_report_from_dict


def _mesh():
    return MeshModel(
        mesh_id="roundtrip",
        vertices=((0,0,0),(1,0,0),(0,1,0),(0,0,1),(9,9,9)),
        faces=((0,2,1),(0,1,3),(1,2,3),(2,0,3)),
    )


def test_report_round_trip_is_exact():
    report = analyze_topology(_mesh())
    raw = report.to_dict()
    assert topology_report_from_dict(raw) == report
    assert topology_report_from_dict(raw).to_dict() == raw


def test_unknown_report_field_fails_closed():
    raw = analyze_topology(_mesh()).to_dict()
    raw["unexpected"] = True
    with pytest.raises(ValueError):
        topology_report_from_dict(raw)


def test_missing_report_field_fails_closed():
    raw = analyze_topology(_mesh()).to_dict()
    del raw["edge_count"]
    with pytest.raises(ValueError):
        topology_report_from_dict(raw)


def test_inconsistent_derived_metric_fails_closed():
    raw = analyze_topology(_mesh()).to_dict()
    raw["isolated_vertex_count"] += 1
    with pytest.raises(ValueError):
        topology_report_from_dict(raw)


def test_unsorted_histogram_fails_closed():
    raw = analyze_topology(_mesh()).to_dict()
    raw["edge_valence_histogram"] = [[2, 1], [1, 7]]
    with pytest.raises(ValueError):
        topology_report_from_dict(raw)


def test_component_mutation_cannot_modify_source_report():
    report = analyze_topology(_mesh())
    raw = copy.deepcopy(report.to_dict())
    raw["components"][0]["face_indices"].append(100)
    assert report.components[0].face_indices != tuple(raw["components"][0]["face_indices"])
