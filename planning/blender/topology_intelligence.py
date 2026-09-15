"""Deterministic, engine-independent Wave 5 mesh topology intelligence.

Analysis only: no bpy, no mutation, no execution/authorization authority.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from planning.blender.scene_model import MeshModel

TOPOLOGY_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class TopologyComponent:
    """One face-connected topology component, identified deterministically by min face index."""
    component_id: int
    face_indices: Tuple[int, ...]
    vertex_indices: Tuple[int, ...]
    edge_count: int
    boundary_edge_count: int
    manifold_edge_count: int
    non_manifold_edge_count: int


@dataclass(frozen=True)
class TopologyReport:
    """Immutable canonical topology summary for one MeshModel."""
    schema_version: str
    mesh_id: str
    vertex_count: int
    referenced_vertex_count: int
    isolated_vertex_count: int
    edge_count: int
    boundary_edge_count: int
    manifold_edge_count: int
    non_manifold_edge_count: int
    max_edge_valence: int
    edge_valence_histogram: Tuple[Tuple[int, int], ...]
    face_count: int
    triangle_count: int
    quad_count: int
    ngon_count: int
    face_cardinality_histogram: Tuple[Tuple[int, int], ...]
    connected_component_count: int
    components: Tuple[TopologyComponent, ...]

    def to_dict(self) -> Dict[str, object]:
        """Return deterministic JSON-native data; nested containers are freshly allocated."""
        return {
            "schema_version": self.schema_version,
            "mesh_id": self.mesh_id,
            "vertex_count": self.vertex_count,
            "referenced_vertex_count": self.referenced_vertex_count,
            "isolated_vertex_count": self.isolated_vertex_count,
            "edge_count": self.edge_count,
            "boundary_edge_count": self.boundary_edge_count,
            "manifold_edge_count": self.manifold_edge_count,
            "non_manifold_edge_count": self.non_manifold_edge_count,
            "max_edge_valence": self.max_edge_valence,
            "edge_valence_histogram": [[k, v] for k, v in self.edge_valence_histogram],
            "face_count": self.face_count,
            "triangle_count": self.triangle_count,
            "quad_count": self.quad_count,
            "ngon_count": self.ngon_count,
            "face_cardinality_histogram": [[k, v] for k, v in self.face_cardinality_histogram],
            "connected_component_count": self.connected_component_count,
            "components": [
                {
                    "component_id": c.component_id,
                    "face_indices": list(c.face_indices),
                    "vertex_indices": list(c.vertex_indices),
                    "edge_count": c.edge_count,
                    "boundary_edge_count": c.boundary_edge_count,
                    "manifold_edge_count": c.manifold_edge_count,
                    "non_manifold_edge_count": c.non_manifold_edge_count,
                }
                for c in self.components
            ],
        }


def _validate_mesh(mesh: MeshModel) -> None:
    """Fail closed if a caller bypassed the normal MeshModel construction contract."""
    if not isinstance(mesh, MeshModel):
        raise TypeError("mesh must be a MeshModel")
    vertex_count = len(mesh.vertices)
    for face_index, face in enumerate(mesh.faces):
        if len(face) < 1:
            raise ValueError("mesh contains an empty face")
        for index in face:
            if type(index) is not int or index < 0 or index >= vertex_count:
                raise ValueError(
                    "mesh contains invalid vertex index at face {}: {}".format(face_index, index)
                )


def analyze_topology(mesh: MeshModel) -> TopologyReport:
    """Compute deterministic indexed topology in O(face-corners + vertices + edges)."""
    _validate_mesh(mesh)
    vertices = mesh.vertices
    faces = mesh.faces
    vertex_count = len(vertices)

    referenced = set()
    edge_faces: Dict[Tuple[int, int], List[int]] = {}
    face_edges: List[Tuple[Tuple[int, int], ...]] = []
    face_hist: Dict[int, int] = {}

    for fi, face in enumerate(faces):
        cardinality = len(face)
        face_hist[cardinality] = face_hist.get(cardinality, 0) + 1
        for index in face:
            referenced.add(index)
        edges = []
        for i, a in enumerate(face):
            b = face[(i + 1) % cardinality]
            edge = (a, b) if a < b else (b, a)
            edges.append(edge)
            edge_faces.setdefault(edge, []).append(fi)
        face_edges.append(tuple(edges))

    edge_valence = {}
    boundary = manifold = non_manifold = 0
    for edge in sorted(edge_faces):
        valence = len(edge_faces[edge])
        edge_valence[valence] = edge_valence.get(valence, 0) + 1
        if valence == 1:
            boundary += 1
        elif valence == 2:
            manifold += 1
        elif valence > 2:
            non_manifold += 1

    # Face adjacency through shared undirected edges.
    adjacency: List[set] = [set() for _ in faces]
    for edge in sorted(edge_faces):
        incident = sorted(edge_faces[edge])
        for pos, left in enumerate(incident):
            for right in incident[pos + 1:]:
                adjacency[left].add(right)
                adjacency[right].add(left)

    components: List[TopologyComponent] = []
    visited = set()
    for seed in range(len(faces)):
        if seed in visited:
            continue
        stack = [seed]
        visited.add(seed)
        component_faces = []
        while stack:
            current = stack.pop()
            component_faces.append(current)
            for neighbor in sorted(adjacency[current], reverse=True):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        component_faces.sort()
        component_face_set = set(component_faces)
        component_vertices = set()
        component_edges = set()
        component_boundary = component_manifold = component_non_manifold = 0
        for fi in component_faces:
            component_vertices.update(faces[fi])
            component_edges.update(face_edges[fi])
        for edge in sorted(component_edges):
            valence = len([fi for fi in edge_faces[edge] if fi in component_face_set])
            if valence == 1:
                component_boundary += 1
            elif valence == 2:
                component_manifold += 1
            elif valence > 2:
                component_non_manifold += 1
        components.append(
            TopologyComponent(
                component_id=min(component_faces),
                face_indices=tuple(component_faces),
                vertex_indices=tuple(sorted(component_vertices)),
                edge_count=len(component_edges),
                boundary_edge_count=component_boundary,
                manifold_edge_count=component_manifold,
                non_manifold_edge_count=component_non_manifold,
            )
        )

    components.sort(key=lambda c: c.component_id)
    return TopologyReport(
        schema_version=TOPOLOGY_SCHEMA_VERSION,
        mesh_id=mesh.mesh_id,
        vertex_count=vertex_count,
        referenced_vertex_count=len(referenced),
        isolated_vertex_count=vertex_count - len(referenced),
        edge_count=len(edge_faces),
        boundary_edge_count=boundary,
        manifold_edge_count=manifold,
        non_manifold_edge_count=non_manifold,
        max_edge_valence=max(edge_valence) if edge_valence else 0,
        edge_valence_histogram=tuple(sorted(edge_valence.items())),
        face_count=len(faces),
        triangle_count=face_hist.get(3, 0),
        quad_count=face_hist.get(4, 0),
        ngon_count=sum(count for cardinality, count in face_hist.items() if cardinality >= 5),
        face_cardinality_histogram=tuple(sorted(face_hist.items())),
        connected_component_count=len(components),
        components=tuple(components),
    )
