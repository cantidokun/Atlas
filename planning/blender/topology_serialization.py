"""Closed, deterministic JSON-native serialization for Wave 5 topology reports."""

from typing import Any, Dict, Tuple

from planning.blender.topology_intelligence import (
    TOPOLOGY_SCHEMA_VERSION,
    TopologyComponent,
    TopologyReport,
)

_REPORT_FIELDS = frozenset({
    "schema_version", "mesh_id", "vertex_count", "referenced_vertex_count", "isolated_vertex_count",
    "edge_count", "boundary_edge_count", "manifold_edge_count", "non_manifold_edge_count",
    "max_edge_valence", "edge_valence_histogram", "face_count", "triangle_count", "quad_count",
    "ngon_count", "face_cardinality_histogram", "connected_component_count", "components",
})
_COMPONENT_FIELDS = frozenset({
    "component_id", "face_indices", "vertex_indices", "edge_count", "boundary_edge_count",
    "manifold_edge_count", "non_manifold_edge_count",
})


def _exact_dict(value: Any, label: str) -> Dict[str, Any]:
    if type(value) is not dict:
        raise ValueError(label + " must be an exact dict")
    return value


def _int(value: Any, label: str) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        raise ValueError(label + " must be a non-negative exact int")
    return value


def _int_tuple(value: Any, label: str) -> Tuple[int, ...]:
    if type(value) is not list:
        raise ValueError(label + " must be a list")
    return tuple(_int(v, label + "[]") for v in value)


def _hist(value: Any, label: str) -> Tuple[Tuple[int, int], ...]:
    if type(value) is not list:
        raise ValueError(label + " must be a list")
    out = []
    previous = -1
    for pair in value:
        if type(pair) is not list or len(pair) != 2:
            raise ValueError(label + " entries must be [key, count]")
        key = _int(pair[0], label + " key")
        count = _int(pair[1], label + " count")
        if key <= previous:
            raise ValueError(label + " keys must be strictly increasing")
        previous = key
        out.append((key, count))
    return tuple(out)


def topology_report_from_dict(value: Any) -> TopologyReport:
    """Strictly parse a Wave 5 report; unknown/missing/inconsistent fields fail closed."""
    d = _exact_dict(value, "topology report")
    if set(d) != _REPORT_FIELDS:
        raise ValueError("topology report fields do not exactly match schema")
    if type(d["schema_version"]) is not str or d["schema_version"] != TOPOLOGY_SCHEMA_VERSION:
        raise ValueError("unsupported topology schema version")
    if type(d["mesh_id"]) is not str or not d["mesh_id"]:
        raise ValueError("mesh_id must be a non-empty exact string")

    components_raw = d["components"]
    if type(components_raw) is not list:
        raise ValueError("components must be a list")
    components = []
    component_ids = set()
    for raw in components_raw:
        c = _exact_dict(raw, "component")
        if set(c) != _COMPONENT_FIELDS:
            raise ValueError("component fields do not exactly match schema")
        component_id = _int(c["component_id"], "component_id")
        if component_id in component_ids:
            raise ValueError("component_id values must be unique")
        component_ids.add(component_id)
        face_indices = _int_tuple(c["face_indices"], "face_indices")
        vertex_indices = _int_tuple(c["vertex_indices"], "vertex_indices")
        if not face_indices:
            raise ValueError("components must contain at least one face")
        if tuple(sorted(face_indices)) != face_indices or len(set(face_indices)) != len(face_indices):
            raise ValueError("face_indices must be sorted and unique")
        if tuple(sorted(vertex_indices)) != vertex_indices or len(set(vertex_indices)) != len(vertex_indices):
            raise ValueError("vertex_indices must be sorted and unique")
        components.append(TopologyComponent(
            component_id=component_id,
            face_indices=face_indices,
            vertex_indices=vertex_indices,
            edge_count=_int(c["edge_count"], "edge_count"),
            boundary_edge_count=_int(c["boundary_edge_count"], "boundary_edge_count"),
            manifold_edge_count=_int(c["manifold_edge_count"], "manifold_edge_count"),
            non_manifold_edge_count=_int(c["non_manifold_edge_count"], "non_manifold_edge_count"),
        ))
    if tuple(sorted(components, key=lambda c: c.component_id)) != tuple(components):
        raise ValueError("components must be ordered by component_id")
    if any(c.component_id != c.face_indices[0] for c in components):
        raise ValueError("component_id must equal the minimum face index")

    report = TopologyReport(
        schema_version=d["schema_version"], mesh_id=d["mesh_id"],
        vertex_count=_int(d["vertex_count"], "vertex_count"),
        referenced_vertex_count=_int(d["referenced_vertex_count"], "referenced_vertex_count"),
        isolated_vertex_count=_int(d["isolated_vertex_count"], "isolated_vertex_count"),
        edge_count=_int(d["edge_count"], "edge_count"),
        boundary_edge_count=_int(d["boundary_edge_count"], "boundary_edge_count"),
        manifold_edge_count=_int(d["manifold_edge_count"], "manifold_edge_count"),
        non_manifold_edge_count=_int(d["non_manifold_edge_count"], "non_manifold_edge_count"),
        max_edge_valence=_int(d["max_edge_valence"], "max_edge_valence"),
        edge_valence_histogram=_hist(d["edge_valence_histogram"], "edge_valence_histogram"),
        face_count=_int(d["face_count"], "face_count"),
        triangle_count=_int(d["triangle_count"], "triangle_count"),
        quad_count=_int(d["quad_count"], "quad_count"),
        ngon_count=_int(d["ngon_count"], "ngon_count"),
        face_cardinality_histogram=_hist(d["face_cardinality_histogram"], "face_cardinality_histogram"),
        connected_component_count=_int(d["connected_component_count"], "connected_component_count"),
        components=tuple(components),
    )

    edge_hist = dict(report.edge_valence_histogram)
    face_hist = dict(report.face_cardinality_histogram)
    if report.vertex_count != report.referenced_vertex_count + report.isolated_vertex_count:
        raise ValueError("vertex counts are inconsistent")
    if report.edge_count != sum(edge_hist.values()):
        raise ValueError("edge histogram does not match edge_count")
    if report.max_edge_valence != (max(edge_hist) if edge_hist else 0):
        raise ValueError("max_edge_valence does not match edge histogram")
    if report.boundary_edge_count != edge_hist.get(1, 0):
        raise ValueError("boundary edge count does not match histogram")
    if report.manifold_edge_count != edge_hist.get(2, 0):
        raise ValueError("manifold edge count does not match histogram")
    if report.non_manifold_edge_count != sum(v for k, v in edge_hist.items() if k > 2):
        raise ValueError("non-manifold edge count does not match histogram")
    if report.face_count != sum(face_hist.values()):
        raise ValueError("face histogram does not match face_count")
    if report.triangle_count != face_hist.get(3, 0) or report.quad_count != face_hist.get(4, 0):
        raise ValueError("triangle/quad counts do not match face histogram")
    if report.ngon_count != sum(v for k, v in face_hist.items() if k >= 5):
        raise ValueError("ngon count does not match face histogram")
    if report.connected_component_count != len(report.components):
        raise ValueError("component count does not match components")

    covered_faces = [fi for c in report.components for fi in c.face_indices]
    if sorted(covered_faces) != list(range(report.face_count)):
        raise ValueError("components must partition all face indices")

    if report.to_dict() != d:
        raise ValueError("topology report contains inconsistent derived fields")
    return report
