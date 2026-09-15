"""Closed, deterministic JSON-native serialization for Wave 5 topology reports."""

from typing import Any, Dict, Tuple

from planning.blender.topology_intelligence import TopologyComponent, TopologyReport, TOPOLOGY_SCHEMA_VERSION

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
    if d["schema_version"] != TOPOLOGY_SCHEMA_VERSION or type(d["schema_version"]) is not str:
        raise ValueError("unsupported topology schema version")
    if type(d["mesh_id"]) is not str or not d["mesh_id"]:
        raise ValueError("mesh_id must be a non-empty exact string")

    components_raw = d["components"]
    if type(components_raw) is not list:
        raise ValueError("components must be a list")
    components = []
    for raw in components_raw:
        c = _exact_dict(raw, "component")
        if set(c) != _COMPONENT_FIELDS:
            raise ValueError("component fields do not exactly match schema")
        components.append(TopologyComponent(
            component_id=_int(c["component_id"], "component_id"),
            face_indices=_int_tuple(c["face_indices"], "face_indices"),
            vertex_indices=_int_tuple(c["vertex_indices"], "vertex_indices"),
            edge_count=_int(c["edge_count"], "edge_count"),
            boundary_edge_count=_int(c["boundary_edge_count"], "boundary_edge_count"),
            manifold_edge_count=_int(c["manifold_edge_count"], "manifold_edge_count"),
            non_manifold_edge_count=_int(c["non_manifold_edge_count"], "non_manifold_edge_count"),
        ))
    if tuple(sorted(components, key=lambda c: c.component_id)) != tuple(components):
        raise ValueError("components must be ordered by component_id")

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
    if report.to_dict() != d:
        raise ValueError("topology report contains inconsistent derived fields")
    return report
