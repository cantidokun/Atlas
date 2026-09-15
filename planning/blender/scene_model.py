"""Language-agnostic canonical SceneReport INPUT contract for the mesh/scene health kernel.

This is the deterministic, engine-independent representation that the health kernel consumes.
It must never contain ``bpy`` objects or any engine-specific behavior: it is composed purely of
canonical primitive values (exact built-in scalars, tuples, dicts with exact-str keys) inside
immutable (``frozen``) dataclasses that are validated in ``__post_init__``.

The representation deliberately reuses the project's existing Atlas-V3 canonical-value
philosophy:
- deterministic primitive values (no NaN/Infinity, no subclass/custom-container coercion),
- immutable/canonical representations (frozen, no mutable aliasing),
- no caller-controlled rich behavior inside the validation kernel.

Only fields already understood and typed are accepted. Unknown keys in the raw/mapping forms are
rejected (fail-closed), never ignored.

Contract summary
================
Required input for a completeness meaning:
- ``SceneModel`` requires: ``scene_id`` (str), ``unit_system`` (str), ``objects`` (non-empty tuple).
- ``ObjectModel`` requires: ``object_id`` (str), ``name`` (str). ``mesh`` is optional — an object
  may lack geometry in a pure-organization pass, but the kernel then emits no mesh findings for it.
- ``MeshModel`` requires: ``mesh_id`` (str), ``vertices`` (non-empty tuple of 3-vectors),
  ``faces`` (non-empty tuple of ordered index tuples; per-face cardinality is derived from ``len(face)`` — mixed triangle/quad/n-gon meshes are valid),
  (int; the kernel validates faces against it when > 0).
Optional (defaulted, documented): ``parent_object_id``, ``collection``, ``location``,
``scale``, ``visible``, ``normals``, ``uvs``, ``materials``.

All vector coordinates must be finite exact ``int``/``float``; ``bool`` is rejected as a
coordinate (bool/int confusion is intentionally rejected).
"""

from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple

# ---------------------------------------------------------------------------


class SceneReportInputError(ValueError):
    """Declared error for the canonical scene/mesh input contract.

    Every malformed/unknown/missing input field fails closed through this type.
    """


def _exact_str(value: Any, label: str) -> str:
    if type(value) is not str:
        raise SceneReportInputError(f"{label} must be an exact built-in string (no subclasses)")
    if not value.strip():
        raise SceneReportInputError(f"{label} must be a non-empty string")
    return value


def _exact_finite_number(value: Any, label: str) -> float:
    if type(value) not in (int, float) or isinstance(value, bool):
        raise SceneReportInputError(f"{label} must be an exact int/float (no bool/subclass)")
    try:
        as_float = float(value)
    except (OverflowError, ValueError) as exc:
        raise SceneReportInputError(f"{label} is not representable as a finite float") from exc
    if not isfinite(as_float):
        raise SceneReportInputError(f"{label} must be finite (no NaN/Infinity)")
    return as_float


def _canon_vector3(value: Any, label: str) -> Tuple[float, float, float]:
    if type(value) not in (tuple, list):
        raise SceneReportInputError(f"{label} must be a 3-element tuple/list")
    if len(value) != 3:
        raise SceneReportInputError(f"{label} must contain exactly three coordinates")
    return (
        _exact_finite_number(value[0], f"{label}[0]"),
        _exact_finite_number(value[1], f"{label}[1]"),
        _exact_finite_number(value[2], f"{label}[2]"),
    )


def _exact_string_tuple(value: Any, label: str) -> Tuple[str, ...]:
    if type(value) not in (tuple, list):
        raise SceneReportInputError(f"{label} must be a tuple/list of strings")
    return tuple(_exact_str(v, label) for v in value)


@dataclass(frozen=True)
class MeshModel:
    """Canonical, immutable mesh description (language-agnostic)."""

    mesh_id: str
    vertices: Tuple[Tuple[float, float, float], ...]  # non-empty, index-aligned with faces
    faces: Tuple[Tuple[int, ...], ...]  # each face is an ordered tuple of vertex indices (n-gon OK)
    # per-face cardinality is DERIVED from each face tuple (len(face) == its vertex count).
    # NOTE: vertices_per_face was REMOVED — topology is authoritative, mixed n-gons are valid.
    normals: Tuple[Tuple[float, float, float], ...] = ()  # optional, one 3-vec PER FACE (face order)
    uvs: Tuple[Tuple[float, float], ...] = ()  # optional, DEFERRED/UNSTRUCTURED (loop-vs-vertex TBD)
    materials: Tuple[str, ...] = ()
    local_frame_id: Optional[str] = None  # declared object-local or coordinate frame

    def __post_init__(self) -> None:
        object.__setattr__(self, "mesh_id", _exact_str(self.mesh_id, "mesh.mesh_id"))
        if type(self.vertices) is not tuple or not self.vertices:
            raise SceneReportInputError("mesh.vertices must be a non-empty tuple")
        vertices = tuple(_canon_vector3(v, "mesh.vertices") for v in self.vertices)
        object.__setattr__(self, "vertices", vertices)
        if type(self.faces) is not tuple or not self.faces:
            raise SceneReportInputError("mesh.faces must be a non-empty tuple")
        faces = tuple(self._canon_face(f) for f in self.faces)
        object.__setattr__(self, "faces", faces)
        if self.normals:
            normals = tuple(_canon_vector3(n, "mesh.normals") for n in self.normals)
            if len(normals) != len(faces):
                raise SceneReportInputError("mesh.normals must have one entry per face")
            object.__setattr__(self, "normals", normals)
        if self.uvs:
            uvs = tuple(self._canon_uv(u) for u in self.uvs)
            if len(uvs) != len(faces):
                raise SceneReportInputError("mesh.uvs must have one entry per face")
            object.__setattr__(self, "uvs", uvs)
        object.__setattr__(
            self, "materials", _exact_string_tuple(self.materials, "mesh.materials")
        )
        if self.local_frame_id is not None:
            object.__setattr__(
                self, "local_frame_id", _exact_str(self.local_frame_id, "mesh.local_frame_id")
            )

    @staticmethod
    def _canon_face(value: Any) -> Tuple[int, ...]:
        if type(value) not in (tuple, list):
            raise SceneReportInputError("mesh.face must be a tuple/list of int indices")
        if not value:
            raise SceneReportInputError("mesh.face must be non-empty")
        face = tuple(value)
        for idx in face:
            if type(idx) is not int or isinstance(idx, bool):
                raise SceneReportInputError("mesh face index must be an exact int")
        if len(set(face)) != len(face):
            raise SceneReportInputError("mesh face must not repeat a vertex index")
        return face

    @staticmethod
    def _canon_uv(value: Any) -> Tuple[float, float]:
        if type(value) not in (tuple, list) or len(value) != 2:
            raise SceneReportInputError("mesh.uvs entry must be a 2-element tuple")
        return (
            _exact_finite_number(value[0], "uv[0]"),
            _exact_finite_number(value[1], "uv[1]"),
        )


@dataclass(frozen=True)
class ObjectModel:
    """Canonical, immutable object description (organization + mesh reference + pose)."""

    object_id: str
    name: str
    collection: Optional[str] = None
    parent_object_id: Optional[str] = None
    location: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    rotation: Tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)  # quaternion (w,x,y,z)
    visible: bool = True
    mesh: Optional[MeshModel] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "object_id", _exact_str(self.object_id, "object.object_id"))
        object.__setattr__(self, "name", _exact_str(self.name, "object.name"))
        if self.collection is not None:
            object.__setattr__(self, "collection", _exact_str(self.collection, "object.collection"))
        if self.parent_object_id is not None:
            object.__setattr__(
                self, "parent_object_id", _exact_str(self.parent_object_id, "object.parent_object_id")
            )
        object.__setattr__(self, "location", _canon_vector3(self.location, "object.location"))
        object.__setattr__(self, "scale", _canon_vector3(self.scale, "object.scale"))
        rot = self._canon_rotation(self.rotation)
        object.__setattr__(self, "rotation", rot)
        if type(self.visible) is not bool:
            raise SceneReportInputError("object.visible must be an exact bool")
        if self.mesh is not None:
            object.__setattr__(self, "mesh", self._require_mesh())

    @property
    def transform(self) -> "TransformModel":
        """The immutable object pose mapping object-local vertices -> parent/world, composed from
        ``location``, ``rotation``, and ``scale``. World-space derivation uses this ONE source.

        Back-compat: ``location``/``scale``/``rotation`` remain the canonical individual fields;
        ``transform`` is the composed ``TransformModel`` the kernel world-pose engine consumes.
        """
        from planning.blender.transforms import TransformModel

        return TransformModel(location=self.location, rotation=self.rotation, scale=self.scale)

    @staticmethod
    def _canon_rotation(value: Any) -> Tuple[float, float, float, float]:
        if type(value) not in (tuple, list) or len(value) != 4:
            raise SceneReportInputError("object.rotation must be a 4-element (w,x,y,z) tuple")
        out = []
        for c in value:
            if type(c) not in (int, float) or isinstance(c, bool):
                raise SceneReportInputError("object.rotation components must be exact int/float")
            f = float(c)
            if f != f or abs(f) == float("inf"):
                raise SceneReportInputError("object.rotation components must be finite")
            out.append(f)
        return (out[0], out[1], out[2], out[3])

    def _require_mesh(self) -> MeshModel:
        if not isinstance(self.mesh, MeshModel):
            return MeshModel(
                mesh_id="",
                vertices=(),
                faces=(),
            )
        return self.mesh
@dataclass(frozen=True)
class SceneModel:
    """Canonical, immutable scene description consumed by the health kernel."""

    scene_id: str
    unit_system: str
    objects: Tuple[ObjectModel, ...] = ()
    coordinate_frame: Optional[str] = None
    world_bounds: Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "scene_id", _exact_str(self.scene_id, "scene.scene_id"))
        object.__setattr__(self, "unit_system", _exact_str(self.unit_system, "scene.unit_system"))
        if self.coordinate_frame is not None:
            object.__setattr__(
                self, "coordinate_frame", _exact_str(self.coordinate_frame, "scene.coordinate_frame")
            )
        if self.world_bounds is not None:
            if type(self.world_bounds) is not tuple or len(self.world_bounds) != 2:
                raise SceneReportInputError("scene.world_bounds must be a (min,max) 2-tuple")
            mn = _canon_vector3(self.world_bounds[0], "scene.world_bounds[0]")
            mx = _canon_vector3(self.world_bounds[1], "scene.world_bounds[1]")
            if not (mn[0] <= mx[0] and mn[1] <= mx[1] and mn[2] <= mx[2]):
                raise SceneReportInputError("scene.world_bounds min must not exceed max")
            object.__setattr__(self, "world_bounds", (mn, mx))
        objs = tuple(self.objects)
        if any(not isinstance(o, ObjectModel) for o in objs):
            raise SceneReportInputError("scene.objects must contain ObjectModel instances")
        object.__setattr__(self, "objects", objs)


# ---------------------------------------------------------------------------
# Deterministic mapping/JSON adapter — closed-grammar parse from plain dicts.
# (The health kernel does not read raw engines directly; this is for fixtures/tests and for
#  the thin Blender adapter to normalize into the canonical model.)
# ---------------------------------------------------------------------------


def _require_exact_dict(value: Any, label: str) -> Dict[str, Any]:
    if type(value) is not dict:
        raise SceneReportInputError(f"{label} must be an exact built-in dict")
    return dict(value)


_OBJECT_ALLOWED = frozenset(
    {"object_id", "name", "collection", "parent_object_id", "location", "scale", "rotation", "visible", "mesh"}
)
_MESH_ALLOWED = frozenset(
    {
        "mesh_id",
        "vertices",
        "faces",
        "normals",
        "uvs",
        "materials",
        "local_frame_id",
    }
)
_SCENE_ALLOWED = frozenset(
    {"scene_id", "unit_system", "objects", "coordinate_frame", "world_bounds"}
)


def parse_scene_report_input(value: Any) -> SceneModel:
    """Parse a plain mapping into the canonical SceneModel (fail-closed, closed grammar)."""
    root = _require_exact_dict(value, "scene")
    unknown = set(root) - _SCENE_ALLOWED
    if unknown:
        raise SceneReportInputError(f"unknown scene fields: {sorted(unknown)}")
    objects_raw = root.get("objects", ())
    if type(objects_raw) not in (tuple, list):
        raise SceneReportInputError("scene.objects must be a tuple/list")
    objects = tuple(_parse_object(o) for o in objects_raw)
    return SceneModel(
        scene_id=root.get("scene_id", ""),
        unit_system=root.get("unit_system", ""),
        objects=objects,
        coordinate_frame=root.get("coordinate_frame"),
        world_bounds=root.get("world_bounds"),
    )


def _parse_object(value: Any) -> ObjectModel:
    d = _require_exact_dict(value, "object")
    unknown = set(d) - _OBJECT_ALLOWED
    if unknown:
        raise SceneReportInputError(f"unknown object fields: {sorted(unknown)}")
    mesh_raw = d.get("mesh")
    mesh = _parse_mesh(mesh_raw) if mesh_raw is not None else None
    return ObjectModel(
            object_id=d.get("object_id", ""),
            name=d.get("name", ""),
            collection=d.get("collection"),
            parent_object_id=d.get("parent_object_id"),
            location=d.get("location", (0.0, 0.0, 0.0)),
            scale=d.get("scale", (1.0, 1.0, 1.0)),
            rotation=d.get("rotation", (1.0, 0.0, 0.0, 0.0)),
            visible=d.get("visible", True),
            mesh=mesh,
        )


def _parse_mesh(value: Any) -> MeshModel:
    d = _require_exact_dict(value, "mesh")
    unknown = set(d) - _MESH_ALLOWED
    if unknown:
        raise SceneReportInputError(f"unknown mesh fields: {sorted(unknown)}")
    # Normalize JSON-native lists into tuples so the canonical frozen model is satisfied.
    def _t(v):
        if type(v) is list:
            return tuple(v)
        return v

    def _tt(v):
        if type(v) is list:
            return tuple(tuple(x) if type(x) is list else x for x in v)
        return v

    return MeshModel(
        mesh_id=d.get("mesh_id", ""),
        vertices=_tt(d.get("vertices", ())),
        faces=_tt(d.get("faces", ())),
        normals=_tt(d.get("normals", ())),
        uvs=_tt(d.get("uvs", ())),
        materials=_t(d.get("materials", ())),
        local_frame_id=d.get("local_frame_id"),
    )