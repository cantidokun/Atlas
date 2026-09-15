"""Thin read-only Blender bpy extraction primitive -> canonical extraction payload."""

from typing import Any, Dict, List, Optional

from planning.blender.blender_units import UnitMappingError, map_unit_system
from planning.blender.extraction_payload import PAYLOAD_SCHEMA_VERSION, validate_payload_schema
from planning.blender.transforms import euler_xyz_degrees_to_quaternion

_SORT_KEY = "name"


class SceneMembershipError(ValueError):
    """Scene membership cannot be enumerated deterministically."""


def _discover_scene_objects(scene) -> List[Any]:
    collection = getattr(scene, "collection", None)
    if collection is None:
        raise SceneMembershipError("scene.collection is unavailable; cannot enumerate scene membership")
    members = getattr(collection, "objects", None)
    if members is None:
        raise SceneMembershipError("scene.collection.objects is unavailable; cannot enumerate scene membership")
    return list(members)


def _extract_vertex_coords(v) -> List[float]:
    if hasattr(v, "co"):
        co = v.co
        if co is None or len(co) < 3:
            raise ValueError("MeshVertex.co is malformed/absent; refusing coordinates")
        return [round(float(co[0]), 6), round(float(co[1]), 6), round(float(co[2]), 6)]
    if all(hasattr(v, axis) for axis in ("x", "y", "z")):
        return [round(float(getattr(v, axis)), 6) for axis in ("x", "y", "z")]
    raise ValueError("MeshVertex exposes neither usable .co nor complete .x/.y/.z")


def _safe_str(v) -> str:
    return str(v)


def extract_scene(bpy) -> dict:
    context = getattr(bpy, "context", None)
    if context is None:
        raise ValueError("bpy.context is not available")
    try:
        scene = context.scene
        scene_name = _safe_str(scene.name)
        unit_system = map_unit_system(scene.unit_settings)
    except UnitMappingError as exc:
        raise ValueError(f"cannot map Blender unit system: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"cannot read Blender scene metadata: {exc}") from exc

    try:
        objects_raw = _discover_scene_objects(scene)
    except SceneMembershipError as exc:
        raise ValueError(str(exc)) from exc

    objects = [_extract_object(bpy, obj) for obj in sorted(objects_raw, key=lambda o: getattr(o, _SORT_KEY, ""))]
    payload = {"schema_version": PAYLOAD_SCHEMA_VERSION, "scene_id": scene_name, "unit_system": unit_system, "objects": objects}
    validate_payload_schema(payload)
    return payload


def _extract_object(bpy, obj) -> dict:
    oid = _safe_str(getattr(obj, "name", ""))
    parent = getattr(obj, "parent", None)
    parent_id = _safe_str(getattr(parent, "name", "")) if parent is not None else None
    collections = getattr(obj, "users_collection", ()) or ()
    collection = _safe_str(collections[0].name) if collections else None
    visible = bool(getattr(obj, "visible", True)) if hasattr(obj, "visible") else True
    location = tuple(getattr(obj.location, axis, 0.0) for axis in ("x", "y", "z")) if hasattr(obj, "location") else (0.0,0.0,0.0)
    scale = tuple(getattr(obj.scale, axis, 1.0) for axis in ("x", "y", "z")) if hasattr(obj, "scale") else (1.0,1.0,1.0)
    rotation = (1.0,0.0,0.0,0.0)
    if hasattr(obj, "rotation_euler"):
        try:
            import math
            raw = [float(getattr(obj.rotation_euler, axis, 0.0)) for axis in ("x","y","z")]
            rotation = euler_xyz_degrees_to_quaternion(*(math.degrees(v) for v in raw))
        except Exception:
            rotation = (1.0,0.0,0.0,0.0)
    mesh = _extract_mesh(obj) if getattr(obj, "type", "") == "MESH" else None
    return {"object_id": oid, "name": oid, "collection": collection, "parent_object_id": parent_id, "location": [float(v) for v in location], "scale": [float(v) for v in scale], "rotation": [float(v) for v in rotation], "visible": visible, "mesh": mesh}


def _extract_mesh(obj) -> Optional[dict]:
    data = getattr(obj, "data", None)
    if data is None:
        raise ValueError(f"mesh object {getattr(obj, 'name', '')} has no data")
    vertices_raw = getattr(data, "vertices", ()) or ()
    vertices = [_extract_vertex_coords(v) for v in vertices_raw]
    if not vertices:
        raise ValueError("mesh has no vertices; refusing empty geometry")
    polygons = getattr(data, "polygons", ()) or ()
    faces = [[int(idx) for idx in poly.vertices] for poly in polygons]
    # Wave 11: zero polygon faces are a truthful canonical state; do not fabricate a face or fail closed.
    # Normals and UVs remain omitted because the canonical model requires per-face data that Blender
    # does not expose through this adapter contract without an explicit conversion.
    return {"mesh_id": _safe_str(getattr(obj, "name", "")), "vertices": vertices, "faces": faces, "normals": None, "uvs": None, "materials": [], "local_frame_id": None}


def run_live_blender_extraction(bpy) -> dict:
    return extract_scene(bpy)
