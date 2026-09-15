"""Language-agnostic canonical SceneReport input model."""

from dataclasses import dataclass
from math import isfinite
from typing import Any, Dict, Optional, Tuple


class SceneReportInputError(ValueError):
    """Malformed canonical scene/mesh input."""


def _exact_str(value: Any, label: str) -> str:
    if type(value) is not str:
        raise SceneReportInputError(f"{label} must be an exact built-in string (no subclasses)")
    if not value.strip():
        raise SceneReportInputError(f"{label} must be a non-empty string")
    return value


def _exact_finite_number(value: Any, label: str) -> float:
    if type(value) not in (int, float) or isinstance(value, bool):
        raise SceneReportInputError(f"{label} must be an exact int/float (no bool/subclass)")
    out = float(value)
    if not isfinite(out):
        raise SceneReportInputError(f"{label} must be finite (no NaN/Infinity)")
    return out


def _canon_vector3(value: Any, label: str) -> Tuple[float, float, float]:
    if type(value) not in (tuple, list) or len(value) != 3:
        raise SceneReportInputError(f"{label} must be a 3-element tuple/list")
    return tuple(_exact_finite_number(v, f"{label}[{i}]") for i, v in enumerate(value))  # type: ignore[return-value]


def _exact_string_tuple(value: Any, label: str) -> Tuple[str, ...]:
    if type(value) not in (tuple, list):
        raise SceneReportInputError(f"{label} must be a tuple/list of strings")
    return tuple(_exact_str(v, label) for v in value)


@dataclass(frozen=True)
class MeshModel:
    """Canonical immutable mesh description.

    Wave 11 semantic boundary: ``vertices`` may be empty only when ``faces`` is also empty.
    This represents the exact result of removing every isolated vertex from an all-isolated mesh.
    A mesh with vertices and zero faces is also valid. A non-empty face set always requires
    non-empty vertices and valid face indices.
    """

    mesh_id: str
    vertices: Tuple[Tuple[float, float, float], ...]
    faces: Tuple[Tuple[int, ...], ...]
    normals: Tuple[Tuple[float, float, float], ...] = ()
    uvs: Tuple[Tuple[float, float], ...] = ()
    materials: Tuple[str, ...] = ()
    local_frame_id: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "mesh_id", _exact_str(self.mesh_id, "mesh.mesh_id"))
        if type(self.vertices) is not tuple:
            raise SceneReportInputError("mesh.vertices must be a tuple")
        if type(self.faces) is not tuple:
            raise SceneReportInputError("mesh.faces must be a tuple")
        if not self.vertices and self.faces:
            raise SceneReportInputError("mesh.faces must be empty when mesh.vertices is empty")
        object.__setattr__(self, "vertices", tuple(_canon_vector3(v, "mesh.vertices") for v in self.vertices))
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
        object.__setattr__(self, "materials", _exact_string_tuple(self.materials, "mesh.materials"))
        if self.local_frame_id is not None:
            object.__setattr__(self, "local_frame_id", _exact_str(self.local_frame_id, "mesh.local_frame_id"))

    @staticmethod
    def _canon_face(value: Any) -> Tuple[int, ...]:
        if type(value) not in (tuple, list) or not value:
            raise SceneReportInputError("mesh.face must be a non-empty tuple/list")
        face = tuple(value)
        if any(type(i) is not int or isinstance(i, bool) for i in face):
            raise SceneReportInputError("mesh face index must be an exact int")
        if len(set(face)) != len(face):
            raise SceneReportInputError("mesh face must not repeat a vertex index")
        return face

    @staticmethod
    def _canon_uv(value: Any) -> Tuple[float, float]:
        if type(value) not in (tuple, list) or len(value) != 2:
            raise SceneReportInputError("mesh.uvs entry must be a 2-element tuple")
        return (_exact_finite_number(value[0], "uv[0]"), _exact_finite_number(value[1], "uv[1]"))


@dataclass(frozen=True)
class ObjectModel:
    object_id: str
    name: str
    collection: Optional[str] = None
    parent_object_id: Optional[str] = None
    location: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    rotation: Tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)
    visible: bool = True
    mesh: Optional[MeshModel] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "object_id", _exact_str(self.object_id, "object.object_id"))
        object.__setattr__(self, "name", _exact_str(self.name, "object.name"))
        if self.collection is not None:
            object.__setattr__(self, "collection", _exact_str(self.collection, "object.collection"))
        if self.parent_object_id is not None:
            object.__setattr__(self, "parent_object_id", _exact_str(self.parent_object_id, "object.parent_object_id"))
        object.__setattr__(self, "location", _canon_vector3(self.location, "object.location"))
        object.__setattr__(self, "scale", _canon_vector3(self.scale, "object.scale"))
        if type(self.rotation) not in (tuple, list) or len(self.rotation) != 4:
            raise SceneReportInputError("object.rotation must be a 4-element tuple")
        rot = tuple(_exact_finite_number(v, "object.rotation") for v in self.rotation)
        object.__setattr__(self, "rotation", rot)
        if type(self.visible) is not bool:
            raise SceneReportInputError("object.visible must be an exact bool")
        if self.mesh is not None and not isinstance(self.mesh, MeshModel):
            raise SceneReportInputError("object.mesh must be a MeshModel")

    @property
    def transform(self):
        from planning.blender.transforms import TransformModel
        return TransformModel(location=self.location, rotation=self.rotation, scale=self.scale)


@dataclass(frozen=True)
class SceneModel:
    scene_id: str
    unit_system: str
    objects: Tuple[ObjectModel, ...] = ()
    coordinate_frame: Optional[str] = None
    world_bounds: Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "scene_id", _exact_str(self.scene_id, "scene.scene_id"))
        object.__setattr__(self, "unit_system", _exact_str(self.unit_system, "scene.unit_system"))
        if self.coordinate_frame is not None:
            object.__setattr__(self, "coordinate_frame", _exact_str(self.coordinate_frame, "scene.coordinate_frame"))
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


_OBJECT_ALLOWED = frozenset({"object_id","name","collection","parent_object_id","location","scale","rotation","visible","mesh"})
_MESH_ALLOWED = frozenset({"mesh_id","vertices","faces","normals","uvs","materials","local_frame_id"})
_SCENE_ALLOWED = frozenset({"scene_id","unit_system","objects","coordinate_frame","world_bounds"})


def _require_exact_dict(value: Any, label: str) -> Dict[str, Any]:
    if type(value) is not dict:
        raise SceneReportInputError(f"{label} must be an exact built-in dict")
    return dict(value)


def parse_scene_report_input(value: Any) -> SceneModel:
    root = _require_exact_dict(value, "scene")
    unknown = set(root) - _SCENE_ALLOWED
    if unknown:
        raise SceneReportInputError(f"unknown scene fields: {sorted(unknown)}")
    raw_objects = root.get("objects", ())
    if type(raw_objects) not in (tuple, list):
        raise SceneReportInputError("scene.objects must be a tuple/list")
    return SceneModel(scene_id=root.get("scene_id", ""), unit_system=root.get("unit_system", ""), objects=tuple(_parse_object(o) for o in raw_objects), coordinate_frame=root.get("coordinate_frame"), world_bounds=root.get("world_bounds"))


def _parse_object(value: Any) -> ObjectModel:
    d = _require_exact_dict(value, "object")
    unknown = set(d) - _OBJECT_ALLOWED
    if unknown:
        raise SceneReportInputError(f"unknown object fields: {sorted(unknown)}")
    return ObjectModel(object_id=d.get("object_id", ""), name=d.get("name", ""), collection=d.get("collection"), parent_object_id=d.get("parent_object_id"), location=d.get("location", (0.0,0.0,0.0)), scale=d.get("scale", (1.0,1.0,1.0)), rotation=d.get("rotation", (1.0,0.0,0.0,0.0)), visible=d.get("visible", True), mesh=_parse_mesh(d["mesh"]) if d.get("mesh") is not None else None)


def _parse_mesh(value: Any) -> MeshModel:
    d = _require_exact_dict(value, "mesh")
    unknown = set(d) - _MESH_ALLOWED
    if unknown:
        raise SceneReportInputError(f"unknown mesh fields: {sorted(unknown)}")
    def _t(v):
        return tuple(v) if type(v) is list else v
    def _tt(v):
        return tuple(tuple(x) if type(x) is list else x for x in v) if type(v) is list else v
    return MeshModel(mesh_id=d.get("mesh_id", ""), vertices=_tt(d.get("vertices", ())), faces=_tt(d.get("faces", ())), normals=_tt(d.get("normals", ())), uvs=_tt(d.get("uvs", ())), materials=_t(d.get("materials", ())), local_frame_id=d.get("local_frame_id"))
