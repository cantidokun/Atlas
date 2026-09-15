"""Canonical object-world transform model (Option 2) + single world-pose computation engine.

This is the authoritative, language-neutral representation of an object's POSE and the SINGLE place
world-space geometry is derived. It is used by AABB, scale/envelope, and any other kernel operation
that needs world coordinates. There is deliberately NO other transform implementation.

Canonical semantics (pinned; reproducible in C++):
- ``MeshModel.vertices`` are OBJECT-LOCAL coordinates. The producer emits the object's own local
  vertices; the kernel never treats them as world.
- ``ObjectModel`` carries an explicit immutable ``TransformModel`` pose mapping object-local -> its
  parent frame (-> ... -> world for nested parents).
- ``TransformModel`` fields (no Euler in the canonical representation):
    - ``location``  (tx, ty, tz)         translation applied LAST.
    - ``rotation``  quaternion (w, x, y, z); identity (1,0,0,0); active rotation.
    - ``scale``     (sx, sy, sz)         per-axis scale applied FIRST.
- Forward map (object-local v -> parent/world)::
    world(v) = R * (S * v) + t      (S=diag(scale), R=active rotation, t=location)
- Composition is defined POINTWISE over a chain::
    world(v) = root.apply( ... parent.apply(child.apply(v)) ... )
  The chain applies the CHILD transform first, then each ancestor up to the root (local ->
  parent -> ... -> world direction). A child without a parent maps directly to the world frame.
- ``TransformChain`` stores the ordered stages (self-first) and ``apply_points`` folds them;
  this is exact for arbitrary rotation/scale/parent nesting (no lossy single-matrix reduction).

Parent handling:
- A missing parent (parent_object_id references an object absent from the scene) yields NO world
  pose: ``world_pose_for`` returns ``None`` and the caller must translate that into a declared
  input failure / deterministic validation outcome (the scene-health hierarchy finding already does).
  No arbitrary fallback transform is introduced.
- A cyclic / self-referential parent chain also yields ``None`` (declared), not silent ignore.
- Identity transform (location 0, identity rotation, scale 1) is the default and maps to itself.
"""

from dataclasses import dataclass, field
from math import sqrt
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple


class TransformError(ValueError):
    """Declared error for an invalid/undefined world transform."""


def _finite_3(value: Any, label: str) -> Tuple[float, float, float]:
    if type(value) not in (tuple, list) or len(value) != 3:
        raise TransformError(f"{label} must be a 3-element tuple")
    out = []
    for c in value:
        if type(c) not in (int, float) or isinstance(c, bool):
            raise TransformError(f"{label} component must be an exact int/float")
        f = float(c)
        if f != f or abs(f) == float("inf"):
            raise TransformError(f"{label} component must be finite")
        out.append(f)
    return (out[0], out[1], out[2])


def _finite_4(value: Any, label: str) -> Tuple[float, float, float, float]:
    if type(value) not in (tuple, list) or len(value) != 4:
        raise TransformError(f"{label} must be a 4-element (w,x,y,z) tuple")
    out = []
    for c in value:
        if type(c) not in (int, float) or isinstance(c, bool):
            raise TransformError(f"{label} component must be an exact int/float")
        f = float(c)
        if f != f or abs(f) == float("inf"):
            raise TransformError(f"{label} component must be finite")
        out.append(f)
    return (out[0], out[1], out[2], out[3])


# ---------------------------------------------------------------------------
# Quaternion helpers (active rotation, right-handed).
# Unit quaternion (w, x, y, z). Rotation of vector v:  q * (0,v) * q^-1
# ---------------------------------------------------------------------------


def _quat_norm(q):
    return sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3])


def _quat_normalize(q):
    n = _quat_norm(q)
    if n <= 0.0:
        raise TransformError("quaternion must be non-zero")
    return (q[0] / n, q[1] / n, q[2] / n, q[3] / n)


def _quat_mult(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def _rot_vec(q, v):
    """Rotate vector v by unit quaternion q (active)."""
    qw, qx, qy, qz = q
    vx, vy, vz = v
    # t = 2 * cross(q.xyz, v)
    tx = 2.0 * (qy * vz - qz * vy)
    ty = 2.0 * (qz * vx - qx * vz)
    tz = 2.0 * (qx * vy - qy * vx)
    # v + t*qw + cross(q.xyz, t)
    cx = qy * tz - qz * ty
    cy = qz * tx - qx * tz
    cz = qx * ty - qy * tx
    return (vx + tx * qw + cx, vy + ty * qw + cy, vz + tz * qw + cz)


def euler_xyz_degrees_to_quaternion(ex: float, ey: float, ez: float) -> Tuple[float, float, float, float]:
    """Convert XYZ-Euler (degrees) to a canonical (w,x,y,z) quaternion (adapter-only helper).

    Used ONLY by the bpy adapter to represent Blender's ``rotation_euler``; the CANONICAL
    representation is always the quaternion. Active rotation, applied as R = Rz(ez)·Ry(ey)·Rx(ex).
    """
    import math

    er = tuple(math.radians(v) for v in (ex, ey, ez))
    cx, sx = math.cos(er[0] / 2), math.sin(er[0] / 2)
    cy, sy = math.cos(er[1] / 2), math.sin(er[1] / 2)
    cz, sz = math.cos(er[2] / 2), math.sin(er[2] / 2)
    return _quat_normalize((
        cx * cy * cz + sx * sy * sz,
        sx * cy * cz - cx * sy * sz,
        cx * sy * cz + sx * cy * sz,
        cx * cy * sz - sx * sy * cz,
    ))


# ---------------------------------------------------------------------------
# TransformModel
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransformModel:
    """Immutable, language-neutral object pose (no Euler in the canonical form)."""

    location: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: Tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)  # (w,x,y,z), identity
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)

    def __post_init__(self) -> None:
        object.__setattr__(self, "location", _finite_3(self.location, "transform.location"))
        object.__setattr__(
            self, "rotation", _quat_normalize(_finite_4(self.rotation, "transform.rotation"))
        )
        object.__setattr__(self, "scale", _finite_3(self.scale, "transform.scale"))
        if any(abs(s) <= 1e-12 for s in self.scale):
            raise TransformError("transform.scale must be non-zero on every axis")

    # -- forward map ---------------------------------------------------

    def apply(self, v: Sequence[float]) -> Tuple[float, float, float]:
        """Map one object-local point to its parent/world position: R*(S*v) + t."""
        if len(v) != 3:
            raise TransformError("apply requires a 3-vector")
        px = float(v[0]) * self.scale[0]
        py = float(v[1]) * self.scale[1]
        pz = float(v[2]) * self.scale[2]
        rx, ry, rz = _rot_vec(self.rotation, (px, py, pz))
        return (rx + self.location[0], ry + self.location[1], rz + self.location[2])

    @property
    def is_identity(self) -> bool:
        return (
            self.location == (0.0, 0.0, 0.0)
            and self.rotation == (1.0, 0.0, 0.0, 0.0)
            and self.scale == (1.0, 1.0, 1.0)
        )

    # -- composed representation ---------------------------------------

    def compose(self, child: "TransformModel", *, exact=True) -> "TransformChain":
        """Build a transform applying ``self`` (parent) after ``child``: world = self(child(v)).

        Returns a :class:`TransformChain` whose ``apply_points`` folds child then self exactly.
        When both transforms are pure translation-only, this is equivalent to concatenation; the
        chain representation keeps the math exact for rotation/scale/parent nesting.
        """
        return TransformChain((child, self))


@dataclass(frozen=True)
class TransformChain:
    """Ordered list of TransformModel stages applied child-first -> world.

    ``apply_points(v)`` = stages[-1].apply( ... stages[0].apply(v) ... ).
    """

    stages: Tuple[TransformModel, ...] = field(default_factory=lambda: (TransformModel(),))

    def __post_init__(self) -> None:
        if not self.stages or any(not isinstance(s, TransformModel) for s in self.stages):
            raise TransformError("TransformChain requires a non-empty tuple of TransformModel")

    def apply(self, v: Sequence[float]) -> Tuple[float, float, float]:
        pt = tuple(float(c) for c in v)
        for s in self.stages:
            pt = s.apply(pt)
        return pt

    def apply_points(self, points: Sequence[Sequence[float]]) -> Tuple[Tuple[float, float, float], ...]:
        return tuple(self.apply(p) for p in points)

    @property
    @staticmethod
    def identity() -> "TransformChain":
        return TransformChain((TransformModel(),))


def compose_stages(stages: Sequence[TransformModel]) -> TransformChain:
    """Compose a child-first sequence (self, parent, grandparent, ...) into one TransformChain.

    ``apply_points(v)`` applies each stage in order (child first, then ancestors), mapping
    local -> ... -> world. If ``stages`` is empty, returns identity. This is the ONLY world-pose
    composition used by the kernel.
    """
    st = tuple(stages)
    if not st:
        return TransformChain((TransformModel(),))
    return TransformChain(st)


def world_pose_for(objects_by_id: Mapping[str, "ObjectModelT"], object_id: str) -> Optional[TransformChain]:
    """Resolve the composed world transform chain for an object across its parent chain.

    Returns None (declared) when the chain is invalid: a parent reference is absent from
    ``objects_by_id``, or a cycle / self-reference is detected. The caller must translate None
    into a deterministic validation outcome (the scene-health hierarchy finding); no fallback
    transform is introduced.

    Order: world(v) = root.apply( ... parent.apply(child_local_v) ... ) — object (child) first,
    then each ancestor up to the root.
    """
    chain: list = []
    seen: set = set()
    cur_id = object_id
    depth = 0
    while cur_id is not None:
        if cur_id in seen or depth > len(objects_by_id):
            return None  # cycle / self-parent
        seen.add(cur_id)
        obj = objects_by_id.get(cur_id)
        if obj is None:
            return None  # missing parent
        try:
            pose = getattr(obj, "transform", TransformModel())
        except TransformError:
            return None  # invalid individual transform -> declared, no world pose
        chain.append(pose)
        parent_id = getattr(obj, "parent_object_id", None)
        if parent_id == cur_id:
            return None
        cur_id = parent_id
        depth += 1
    return compose_stages(tuple(chain))


def world_points(
    objects_by_id: Mapping[str, "ObjectModelT"],
    object_id: str,
    local_vertices: Sequence[Sequence[float]],
) -> Optional[Tuple[Tuple[float, float, float], ...]]:
    """Map object-local vertices to world coordinates via the object's composed pose.

    Returns None when the pose cannot be resolved (missing/cyclic parent). World derivation is
    centralized here — no other kernel code computes world space.
    """
    chain = world_pose_for(objects_by_id, object_id)
    if chain is None:
        return None
    return chain.apply_points(local_vertices)


# Type alias to defer the circular import of scene_model.ObjectModel.
"ObjectModelT"  # placeholder name resolved by the caller via duck typing


def object_by_id_map(scene) -> Dict[str, Any]:
    """Build an ``object_id -> ObjectModel`` map from a SceneModel (duck-typed)."""
    return {o.object_id: o for o in scene.objects}