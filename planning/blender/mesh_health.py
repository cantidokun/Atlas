"""Deterministic mesh-geometry health checks (kernel core).

Pure Python, no ``bpy``, no engine. Operates on the canonical ``MeshModel`` and returns a list of
``Finding`` objects. Every check is deterministic, fail-closed, and documented with its complexity.

Complexity notes (n = vertex count, f = face count, e = edge count):
- coordinate/index checks          O(n + f)
- duplicate vertices               O(n log n) via sort on rounded coordinates
- duplicate faces                   O(f log f) via canonical face key
- degenerate faces                  O(f)
- non-manifold edge                 O(f) edge-incidence map
- winding consistency               O(f) worst case (bounded by face × edge traversal)
- normal consistency                O(f)
- scale check                       O(n)
"""

from collections import defaultdict
from math import acos, degrees, isfinite, sqrt
from typing import Any, Dict, List, Optional, Sequence, Tuple

from planning.blender.finding_codes import FindingCode
from planning.blender.scene_model import MeshModel
from planning.blender.scene_report import Finding

EPS = 1e-6
_EDGE_TOLERANCE = 1e-4


def _cross(ax, ay, az, bx, by, bz):
    return (
        ay * bz - az * by,
        az * bx - ax * bz,
        ax * by - ay * bx,
    )


def _dot(ax, ay, az, bx, by, bz):
    return ax * bx + ay * by + az * bz


def _norm3(values):
    x, y, z = values
    mag = sqrt(x * x + y * y + z * z)
    if mag <= 0.0:
        return None
    return (x / mag, y / mag, z / mag)


class _MeshContext:
    """Precomputed lookup helpers for one mesh (built lazily, deterministic)."""

    def __init__(self, mesh: MeshModel):
        self.mesh = mesh
        self.vertices = mesh.vertices
        self.faces = mesh.faces
        self._edge_map: Optional[Dict[Tuple[int, int], int]] = None

    @property
    def edge_map(self) -> Dict[Tuple[int, int], int]:
        if self._edge_map is None:
            counts: Dict[Tuple[int, int], int] = defaultdict(int)
            for face in self.faces:
                n = len(face)
                for i in range(n):
                    a = face[i]
                    b = face[(i + 1) % n]
                    counts[(min(a, b), max(a, b))] += 1
            self._edge_map = dict(counts)
        return self._edge_map


def _rounded_vertex_key(vertex: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (round(vertex[0], 6), round(vertex[1], 6), round(vertex[2], 6))


def _signed_area(face: Sequence[int], vertices: Sequence[Tuple[float, float, float]]) -> float:
    """Signed area of a face projected onto its dominant axis (shoelace).

    Used only for degeneracy and winding-orientation signals. Not a Blender-normal semantic.
    Returns 0.0 (treat as degenerate) if any face vertex index is out of range, so the
    invalid-index check reports the defect without this helper crashing.
    """
    n = len(face)
    if n < 3:
        return 0.0
    if any(not (0 <= idx < len(vertices)) for idx in face):
        return 0.0
    p0 = vertices[face[0]]
    p1 = vertices[face[1]]
    p2 = vertices[face[2]]
    cx, cy, cz = _cross(
        p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2],
        p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2],
    )
    axis = max(range(3), key=lambda i: abs((cx, cy, cz)[i]))
    area2 = 0.0
    for i in range(n):
        px = vertices[face[i]]
        py = vertices[face[(i + 1) % n]]
        if axis == 0:
            area2 += px[1] * py[2] - py[1] * px[2]
        elif axis == 1:
            area2 += px[2] * py[0] - py[2] * px[0]
        else:
            area2 += px[0] * py[1] - py[0] * px[1]
    return area2 * 0.5


def check_mesh_in_envelope(
    mesh: MeshModel,
    envelope_min: Tuple[float, float, float],
    envelope_max: Tuple[float, float, float],
    *,
    world_vertices: Optional[Sequence[Sequence[float]]] = None,
    tolerance: float = 0.05,
) -> List[Finding]:
    """Emit ``MESH_SCALE_OUT_OF_RANGE`` for vertices outside the profile envelope.

    This is an OPTIONAL profile-driven check: the generic kernel does not itself assume any
    particular production scale. The caller (e.g. the orchestrator) supplies the profile's
    envelope PLUS the WORLD-SPACE vertex positions (``world_vertices``), which the caller computes
    through the single world-pose engine — this check performs NO transform math itself. When
    ``world_vertices`` is None, the mesh's own (object-local) vertices are used unchanged (no
    translation) — only valid when the object's pose is identity. Positions within ``tolerance``
    of the boundary are accepted (documented). Returns a single finding per offending vertex, or
    an empty list.
    """
    findings: List[Finding] = []
    pts = world_vertices if world_vertices is not None else mesh.vertices
    mn = envelope_min
    mx = envelope_max
    for i, v in enumerate(pts):
        wx = float(v[0])
        wy = float(v[1])
        wz = float(v[2])
        in_x = (mn[0] - tolerance) <= wx <= (mx[0] + tolerance)
        in_y = (mn[1] - tolerance) <= wy <= (mx[1] + tolerance)
        in_z = (mn[2] - tolerance) <= wz <= (mx[2] + tolerance)
        if not (in_x and in_y and in_z):
            findings.append(Finding(
                code=FindingCode.MESH_SCALE_OUT_OF_RANGE,
                mesh_id=mesh.mesh_id,
                measured={"vertex": i, "world": [round(wx, 4), round(wy, 4), round(wz, 4)]},
                expected={
                    "envelope_min": list(mn),
                    "envelope_max": list(mx),
                    "tolerance": tolerance,
                },
                message=f"vertex {i} of {mesh.mesh_id!r} lies outside the profile envelope",
            ))
            break  # one representative finding per mesh avoids flooding large meshes
    return findings


def check_mesh(mesh: MeshModel) -> List[Finding]:
    """Run every deterministic mesh-health check and return findings (stable order)."""
    ctx = _MeshContext(mesh)
    findings: List[Finding] = []
    _collect_coordinate_validity(ctx, findings)
    _collect_polygon_index_validity(ctx, findings)
    _collect_duplicate_vertices(ctx, findings)
    _collect_duplicate_faces(ctx, findings)
    _collect_degenerate_faces(ctx, findings)
    _collect_non_manifold_edges(ctx, findings)
    _collect_normal_consistency(ctx, findings)
    _collect_winding_consistency(ctx, findings)
    findings.sort(key=lambda f: (f.code.value, f.object_id or "", f.mesh_id or ""))
    return findings


# ---- A ------------------------------------------------------------------


def _collect_coordinate_validity(ctx: _MeshContext, findings: List[Finding]) -> None:
    mesh = ctx.mesh
    for i, v in enumerate(mesh.vertices):
        if any(not isfinite(c) for c in v):
            findings.append(Finding(
                code=FindingCode.MESH_INVALID_INDEX,
                mesh_id=mesh.mesh_id,
                measured={"vertex": i, "coordinate": list(v)},
                message=f"vertex {i} has a non-finite coordinate",
            ))


# ---- B ------------------------------------------------------------------


def _collect_polygon_index_validity(ctx: _MeshContext, findings: List[Finding]) -> None:
    mesh = ctx.mesh
    n_verts = len(mesh.vertices)
    for fi, face in enumerate(mesh.faces):
        for idx in face:
            if not (0 <= idx < n_verts):
                findings.append(Finding(
                    code=FindingCode.MESH_INVALID_INDEX,
                    mesh_id=mesh.mesh_id,
                    measured={"face": fi, "index": idx},
                    expected={"vertex_count": n_verts},
                    message=f"face {fi} references vertex index {idx} outside range",
                ))


# ---- C ------------------------------------------------------------------


def _collect_duplicate_vertices(ctx: _MeshContext, findings: List[Finding]) -> None:
    mesh = ctx.mesh
    seen: Dict[Tuple[float, float, float], int] = {}
    for i, v in enumerate(mesh.vertices):
        key = _rounded_vertex_key(v)
        if key in seen:
            findings.append(Finding(
                code=FindingCode.MESH_DUPLICATE_VERTEX,
                mesh_id=mesh.mesh_id,
                measured={"vertex_a": seen[key], "vertex_b": i, "coordinate": list(v)},
                message=f"vertices {seen[key]} and {i} are coincident",
            ))
        else:
            seen[key] = i


def _collect_duplicate_faces(ctx: _MeshContext, findings: List[Finding]) -> None:
    mesh = ctx.mesh
    seen: Dict[Tuple[Tuple[int, ...], bool], int] = {}
    for fi, face in enumerate(mesh.faces):
        s = tuple(sorted(face))
        winding = _signed_area(face, mesh.vertices) >= 0.0
        key = (s, winding)
        if key in seen:
            findings.append(Finding(
                code=FindingCode.MESH_DUPLICATE_FACE,
                mesh_id=mesh.mesh_id,
                measured={"face_a": seen[key], "face_b": fi, "vertices": list(face)},
                message=f"faces {seen[key]} and {fi} are duplicates",
            ))
        else:
            seen[key] = fi


# ---- D ------------------------------------------------------------------


def _collect_degenerate_faces(ctx: _MeshContext, findings: List[Finding]) -> None:
    mesh = ctx.mesh
    for fi, face in enumerate(mesh.faces):
        if len(face) < 3:
            findings.append(Finding(
                code=FindingCode.MESH_DEGENERATE_FACE,
                mesh_id=mesh.mesh_id,
                measured={"face": fi, "vertex_count": len(face)},
                message=f"face {fi} has fewer than 3 vertices",
            ))
            continue
        area2 = _signed_area(face, mesh.vertices)
        if abs(area2) <= _EDGE_TOLERANCE:
            findings.append(Finding(
                code=FindingCode.MESH_DEGENERATE_FACE,
                mesh_id=mesh.mesh_id,
                measured={"face": fi, "signed_area": round(area2, 6)},
                message=f"face {fi} is degenerate (zero area)",
            ))


# ---- E ------------------------------------------------------------------


def _collect_non_manifold_edges(ctx: _MeshContext, findings: List[Finding]) -> None:
    """An edge shared by != 2 faces is non-manifold (valence > 2) or boundary (valence 1).

    The kernel reports valence > 2 as non-manifold. Boundary edges (valence 1) are a normal
    property of open meshes and are only reported by policy; the core does not assume a closed
    mesh, so it does not flag them as errors here.
    """
    mesh = ctx.mesh
    for (a, b), count in sorted(ctx.edge_map.items()):
        if count > 2:
            findings.append(Finding(
                code=FindingCode.MESH_NON_MANIFOLD_EDGE,
                mesh_id=mesh.mesh_id,
                measured={"edge": [a, b], "face_incidence": count},
                expected={"face_incidence": 2},
                message=f"edge ({a},{b}) is shared by {count} faces (non-manifold)",
            ))


# ---- F ------------------------------------------------------------------


def _collect_winding_consistency(ctx: _MeshContext, findings: List[Finding]) -> None:
    """Detect conflicting face orientation within a connected component.

    Combinatorial orientation check (no Blender semantics): for each undirected edge shared by
    exactly two faces, the two faces must traverse the edge in OPPOSITE directions. If both
    faces traverse the same DIRECTED edge (a->b in both), that is a winding inconsistency. An
    edge shared by != 2 faces is handled by the non-manifold check.
    """
    mesh = ctx.mesh
    if len(mesh.faces) < 2:
        return
    edge_entries: Dict[Tuple[int, int], List[Tuple[int, int, int]]] = defaultdict(list)
    for fi, face in enumerate(mesh.faces):
        n = len(face)
        for i in range(n):
            a = face[i]
            b = face[(i + 1) % n]
            edge_entries[(min(a, b), max(a, b))].append((fi, a, b))
    for edge, entries in edge_entries.items():
        if len(entries) == 2:
            (f1, a1, b1), (f2, a2, b2) = entries
            # Same directed edge (a->b in both faces) means both faces wind the edge the same
            # way, which is a winding inconsistency. Opposite traversal is consistent.
            if (a1, b1) == (a2, b2):
                findings.append(Finding(
                    code=FindingCode.MESH_WINDING_INCONSISTENT,
                    mesh_id=mesh.mesh_id,
                    measured={"edge": list(edge), "faces": [f1, f2]},
                    message=f"faces {f1} and {f2} wind edge in the same direction",
                ))


# ---- F-bis: normal consistency ----------------------------------------


def _collect_normal_consistency(ctx: _MeshContext, findings: List[Finding]) -> None:
    """If normals are supplied (one per face), verify finite, unit, and agree with geometry.

    Unavailable normals are NOT a finding — only invalid or contradictory normals are. Winding
    consistency and normals are separate signals; we do not invent Blender normal semantics.
    """
    mesh = ctx.mesh
    if not mesh.normals:
        return
    for fi, normal in enumerate(mesh.normals):
        n = _norm3(normal)
        if n is None:
            findings.append(Finding(
                code=FindingCode.MESH_NORMAL_INCONSISTENT,
                mesh_id=mesh.mesh_id,
                measured={"face": fi, "normal": list(normal)},
                message="declared normal is zero-length",
            ))
            continue
        face = mesh.faces[fi]
        if len(face) < 3 or any(not (0 <= idx < len(mesh.vertices)) for idx in face):
            findings.append(Finding(
                code=FindingCode.MESH_NORMAL_INCONSISTENT,
                mesh_id=mesh.mesh_id,
                measured={"face": fi},
                message="cannot validate normal of a degenerate or out-of-range face",
            ))
            continue
        p0 = mesh.vertices[face[0]]
        p1 = mesh.vertices[face[1]]
        p2 = mesh.vertices[face[2]]
        cx, cy, cz = _cross(
            p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2],
            p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2],
        )
        computed = _norm3((cx, cy, cz))
        if computed is None:
            continue
        dot = abs(_dot(*n, *computed))
        angle = degrees(acos(max(-1.0, min(1.0, dot))))
        if angle > 1.0:  # documented 1-degree normal agreement tolerance
            findings.append(Finding(
                code=FindingCode.MESH_NORMAL_INCONSISTENT,
                mesh_id=mesh.mesh_id,
                measured={"face": fi, "angle_deg": round(angle, 4)},
                expected={"tolerance_deg": 1.0},
                message=f"face {fi} declared normal disagrees with geometry by {angle:.2f} deg",
            ))