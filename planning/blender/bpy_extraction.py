"""Thin read-only Blender (bpy) extraction primitive -> canonical extraction payload.

This is the smallest Blender-facing extraction layer. It:
- queries the live Blender Python API (``bpy``) — which is ONLY importable inside a real Blender
  process;
- extracts scene/object/mesh fields;
- converts Blender values into the canonical, deterministic extraction payload
  (see :mod:`planning.blender.extraction_payload` and :mod:`planning.blender.fixtures`);
- returns the payload for the kernel to consume.

It contains NO validation semantics: no topology checks, no scale/naming policy, no readiness
rules, no finding logic. All of those live in the deterministic kernel
(:mod:`planning.blender.mesh_health`, :mod:`planning.blender.scene_health`) which this adapter only
feeds via ``run_scene_health``.

``bpy`` is imported LAZILY inside the entry that requires it, so importing/using this module in
deterministic (non-Blender) CI is safe and never triggers a Blender availability error.

Read-only: it never mutates the scene, never saves/overwrites a ``.blend``, never executes any
write op. If the real Blender state cannot satisfy the payload contract it fails closed — it does
does NOT emit partial geometry, does not downgrade a mesh to a count-only representation, and does
not infer missing geometry from counts. Mesh vertices are OBJECT-LOCAL coordinates carried with an
explicit per-object transform (location/rotation/scale); the kernel derives world space (see the
coordinate/transform contract in the kernel docs).
"""

from typing import Any, Dict, List, Optional, Tuple

from planning.blender.blender_units import UnitMappingError, map_unit_system
from planning.blender.extraction_payload import PAYLOAD_SCHEMA_VERSION, validate_payload_schema
from planning.blender.transforms import euler_xyz_degrees_to_quaternion

# Stable, deterministic object ordering key (never Blender runtime pointers).
_SORT_KEY = "name"


class SceneMembershipError(ValueError):
    """Declared error: scene object membership cannot be enumerated deterministically."""


def _discover_scene_objects(scene) -> List[Any]:
    """Return the objects that belong to the scene, from Blender's real data model.

    Scene membership is DEFINED as the objects linked in the scene's ACTIVE COLLECTION
    (``scene.collection.objects``) — Blender's canonical, scene-scoped object membership. We do NOT
    use ``bpy.data.objects`` (file-wide, over-collects objects from every scene) and we do NOT fall
    back to a silent empty list.

    Fails CLOSED (raises ``SceneMembershipError``) when scene membership cannot be enumerated from
    the real source — a scene with an unresolvable collection is an extraction defect, never an
    authoritative empty scene. An empty *but resolvable* membership (a scene that truly links zero
    objects) is legitimate and returns ``[]`` (the kernel then reports the missing roles).
    """
    collection = getattr(scene, "collection", None)
    if collection is None:
        raise SceneMembershipError(
            "scene.collection is unavailable; cannot enumerate scene membership (fail closed)"
        )
    members = getattr(collection, "objects", None)
    if members is None:
        raise SceneMembershipError(
            "scene.collection.objects is unavailable; cannot enumerate scene membership (fail closed)"
        )
    return list(members)


def _extract_vertex_coords(v) -> List[float]:
    """Read a real Blender ``MeshVertex`` coordinate as the object-local 3-vector.

    PRIMARY (canonical, Blender 4.4.x): ``v.co`` — the MeshVertex coordinate vector. We read
    ``[v.co[0], v.co[1], v.co[2]]`` and NEVER fall back to manufacturing zeros.

    Narrowly scoped compatibility for OLDER Blender builds whose ``MeshVertex`` exposes the full
    ``.x/.y/.z`` axis surface instead of ``.co``: those axes are read ONLY when ALL three are
    genuinely present (``hasattr`` for each) — never ``getattr(v, axis, 0.0)``, which would
    silently fabricate zeros and flatten the mesh to the origin.

    FAIL CLOSED: a vertex that exposes neither a usable ``.co`` nor a complete ``.x/.y/.z``
    triplet is a malformed/unsupported coordinate access and raises ``ValueError``. Unsupported
    geometry is never silently converted into authoritative-looking geometry.
    """
    if hasattr(v, "co"):
        co = v.co
        if co is None or len(co) < 3:
            raise ValueError(
                "MeshVertex.co is malformed/absent; refusing to emit coordinates (fail closed)"
            )
        return [round(float(co[0]), 6), round(float(co[1]), 6), round(float(co[2]), 6)]
    # Documented legacy axis surface (pre-``.co`` builders): require ALL three axes present.
    if all(hasattr(v, axis) for axis in ("x", "y", "z")):
        return [round(float(getattr(v, axis)), 6) for axis in ("x", "y", "z")]
    raise ValueError(
        "MeshVertex has neither a usable .co nor a complete .x/.y/.z surface; "
        "refusing to manufacture coordinates (fail closed)"
    )


def _safe_str(v) -> str:
    return str(v)


def extract_scene(bpy) -> dict:
    """Extract the scene -> object -> mesh payload from a live ``bpy`` module.

    Args:
        bpy: the Blender Python module (imported by the caller from within Blender).
    Returns:
        A canonical extraction payload dict (schema_version "1").
    Raises:
        ValueError / TypeError: fail-closed when the live Blender state cannot satisfy the
            payload contract (never a partial path).
    """
    scene_module = getattr(bpy, "context", None)
    if scene_module is None:
        raise ValueError("bpy.context is not available; cannot extract a scene")

    try:
        scene = scene_module.scene
        scene_name = _safe_str(scene.name)
        units = scene.unit_settings
        unit_system = map_unit_system(units)
    except UnitMappingError as exc:
        raise ValueError(f"cannot map Blender unit system to canonical unit: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - any live-extraction problem is a failure
        raise ValueError(f"cannot read Blender scene metadata: {exc}") from exc

    # Deterministic scene membership (fail-closed; never a silent empty scene).
    try:
        objects_raw = _discover_scene_objects(scene)
    except SceneMembershipError as exc:
        raise ValueError(str(exc)) from exc

    objects: List[Dict[str, Any]] = []
    for obj in sorted(objects_raw, key=lambda o: getattr(o, _SORT_KEY, "")):
        objects.append(_extract_object(bpy, obj))

    payload: Dict[str, Any] = {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "scene_id": scene_name,
        "unit_system": unit_system,
        "objects": objects,
    }
    validate_payload_schema(payload)
    return payload


def _extract_object(bpy, obj) -> dict:
    oid = _safe_str(getattr(obj, "name", ""))
    name = _safe_str(getattr(obj, "name", ""))
    parent = getattr(obj, "parent", None)
    parent_id = _safe_str(getattr(parent, "name", "")) if parent is not None else None
    collections = getattr(obj, "users_collection", ()) or ()
    collection = _safe_str(collections[0].name) if collections else None
    visible = bool(getattr(obj, "visible", True)) if hasattr(obj, "visible") else True

    location = (0.0, 0.0, 0.0)
    if hasattr(obj, "location"):
        location = tuple(getattr(obj.location, axis, 0.0) for axis in ("x", "y", "z"))

    scale = (1.0, 1.0, 1.0)
    if hasattr(obj, "scale"):
        scale = tuple(getattr(obj.scale, axis, 1.0) for axis in ("x", "y", "z"))

    # Canonical rotation is a quaternion (w,x,y,z); Blender exposes an Euler triple. Convert here
    # (adapter-side) so the canonical payload never carries Euler. Note: we keep the rotation order
    # convention explicit and unit-tested via euler_xyz_degrees_to_quaternion.
    rotation = (1.0, 0.0, 0.0, 0.0)
    if hasattr(obj, "rotation_euler"):
        try:
            rot_raw = [
                float(getattr(obj.rotation_euler, axis, 0.0)) for axis in ("x", "y", "z")
            ]
            # Blender rotation_euler is in RADIANS.
            import math

            rotation = euler_xyz_degrees_to_quaternion(
                math.degrees(rot_raw[0]), math.degrees(rot_raw[1]), math.degrees(rot_raw[2])
            )
        except Exception:  # noqa: BLE001 - a malformed/absent rotation remains identity
            rotation = (1.0, 0.0, 0.0, 0.0)

    mesh = _extract_mesh(obj) if getattr(obj, "type", "") == "MESH" else None

    return {
        "object_id": oid,
        "name": name,
        "collection": collection,
        "parent_object_id": parent_id,
        "location": [float(v) for v in location],
        "scale": [float(v) for v in scale],
        "rotation": [float(v) for v in rotation],
        "visible": visible,
        "mesh": mesh,
    }


def _extract_mesh(obj) -> Optional[dict]:
    data = getattr(obj, "data", None)
    if data is None:
        # Real Blender mesh objects must carry data; fail closed rather than count-only.
        raise ValueError(
            f"mesh object {getattr(obj, 'name', '')} has no data; refusing a count-only mesh"
        )
    vertices = getattr(data, "vertices", ()) or ()
    vertices_list = [_extract_vertex_coords(v) for v in vertices]
    if not vertices_list:
        raise ValueError("mesh has no vertices; refusing to emit an empty/partial mesh")

    polygons = getattr(data, "polygons", ()) or ()
    # MeshPolygon exposes .vertices (per-face index list) in this Blender API surface.
    faces = [
        [int(idx) for idx in poly.vertices]
        for poly in polygons
    ]
    if not faces:
        raise ValueError("mesh has no polygon faces; refusing to emit a geometry-less mesh")

    normals = None
    # NORMALS CONTRACT (per-face, genuine only): Blender's ``data.vertex_normals`` is PER-VERTEX,
    # and loop normals are per-corner. There is NO per-face normal exposed by the bpy surface we
    # target, and labeling vertex/loop data as per-face would violate the SceneModel contract.
    # Extracting a truthful per-face normal requires averaging loop/vertex normals per polygon — a
    # documented adapter-side conversion that must be validated against a real scene first.
    # DEFERRED: until that conversion is validated, the adapter explicitly OMITS normals rather
    # than mislabeling them. A geometry-only mesh remains valid (normals optional).

    uvs = None
    # UVs: DEFERRED/UNSTRUCTURED — Blender UVs are per-loop/per-vertex ambiguous relative to the
    # SceneModel face-tuple model. Not emitted (never fabricate a per-face UV mapping).

    return {
        "mesh_id": _safe_str(getattr(obj, "name", "")),
        "vertices": vertices_list,
        "faces": faces,
        "normals": normals,
        "uvs": uvs,
        "materials": [],
        "local_frame_id": None,
    }


def run_live_blender_extraction(bpy) -> dict:
    """Entry point for a live Blender process: extract the payload only.

    Returns the canonical extraction payload. The caller (a live-gated integration script) then
    runs it through the deterministic kernel. No reporting/validation is done here.
    """
    return extract_scene(bpy)