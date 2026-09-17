"""Thin read-only Blender bpy extraction primitive -> canonical extraction payload.

Contract: ``planning/blender/BLENDER_EXTRACTION_FIDELITY_COMPLETION_DESIGN.md`` (design revision 7,
cleared at ``32eb4f76``). Section references below are to that document.

Scope of this producer (v1): scene membership and the deterministic representative collection (§5),
object visibility sourcing (§7.3), transform sourcing closed by ``rotation_mode`` (§7.2), truthful
location/scale (§7.1), source-order geometry (§6) with the existing six-decimal numeric policy (§8.1),
material-slot semantics (§4.3), and the explicit omission of normals/UVs/local-frame (§4.1/§4.2/§4.4).

Two rules govern every line of this module:

* **truth-preserving** — an available value is emitted exactly; an unrepresentable state is omitted
  where the contract defines an omission, and otherwise the extraction FAILS CLOSED (§10);
* **never fabricate** — no default, no identity substitution, no normalization, no sorting, no
  partial payload (§10, §6, §4.3). No ``bpy.data.objects`` membership source, no evaluated/modifier
  geometry, no mutation, no save, no authorization or execution authority (§2).

This module is READ-ONLY with respect to Blender: it reads attributes and returns a JSON-native
payload. It never writes a datablock, never calls an operator, never saves.
"""
import math
from typing import Any, Dict, List, Optional, Tuple

from planning.blender.blender_units import UnitMappingError, map_unit_system
from planning.blender.extraction_payload import PAYLOAD_SCHEMA_VERSION, validate_payload_schema
from planning.blender.transforms import euler_xyz_degrees_to_quaternion

# §7.2 — the only two rotation modes with an in-tree conversion contract.
_EULER_MODE_XYZ = "XYZ"
_QUATERNION_MODE = "QUATERNION"
# §4.3 — object-level material link that the canonical field cannot represent.
_OBJECT_LINK = "OBJECT"
# §8.1 — the existing producer numeric policy for vertex coordinates.
_COORD_DECIMALS = 6


class SceneMembershipError(ValueError):
    """Declared failure: scene membership cannot be enumerated (fail closed, §5.2)."""


# ---------------------------------------------------------------------------
# small fail-closed readers (§10)
# ---------------------------------------------------------------------------


def _object_label(obj: Any) -> str:
    """Best-effort label for error messages only; never emitted into the payload."""
    name = getattr(obj, "name", None)
    return name if type(name) is str else "<unnamed>"


def _finite_number(value: Any, label: str) -> float:
    """Read an exact int/float source number; refuse bool, non-numeric and non-finite (§10)."""
    if type(value) not in (int, float) or isinstance(value, bool):
        raise ValueError(f"{label} must be a number; refusing a non-numeric source value (fail closed)")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{label} must be finite; refusing {value!r} (fail closed)")
    return out


def _read_axes(vec: Any, label: str) -> Tuple[float, float, float]:
    """Read an (x, y, z) source vector verbatim — no per-axis default (§7.1)."""
    if vec is None:
        raise ValueError(f"{label} is absent; refusing to substitute default components (fail closed)")
    out: List[float] = []
    for axis in ("x", "y", "z"):
        if not hasattr(vec, axis):
            raise ValueError(f"{label}.{axis} is missing; refusing to default it (fail closed)")
        out.append(_finite_number(getattr(vec, axis), f"{label}.{axis}"))
    return (out[0], out[1], out[2])


def _read_name(value: Any, label: str) -> str:
    """Read a required non-empty exact string source name (§3: object_id == source object name)."""
    if type(value) is not str or not value.strip():
        raise ValueError(f"{label} must be a non-empty string; refusing {value!r} (fail closed)")
    return value


def _identity_key(entity: Any) -> Any:
    """In-process source-identity key (§5.2). Never emitted, never ordered on, never hashed."""
    pointer = getattr(entity, "as_pointer", None)
    if callable(pointer):
        try:
            return ("ptr", int(pointer()))
        except Exception:  # pragma: no cover - defensive; a lying pointer falls back to id()
            pass
    return ("id", id(entity))


# ---------------------------------------------------------------------------
# §5 — scene membership: domain, traversal, deduplication, representative
# ---------------------------------------------------------------------------


def _read_collection_members(collection: Any) -> List[Any]:
    members = getattr(collection, "objects", None)
    if members is None:
        raise SceneMembershipError(
            "collection.objects is unavailable; cannot enumerate scene membership (fail closed)"
        )
    return list(members)


def _read_collection_children(collection: Any) -> List[Any]:
    children = getattr(collection, "children", None)
    if children is None:
        raise SceneMembershipError(
            "collection.children is unavailable; cannot walk the scene collection graph (fail closed)"
        )
    return list(children)


def _discover_scene_membership(scene: Any) -> Tuple[List[Any], Dict[Any, Optional[str]]]:
    """Enumerate §5.1's domain and each object's §5.4 representative collection name.

    Domain: objects linked into some collection reachable from ``scene.collection`` through
    ``collection.child`` links, recursively, including ``scene.collection`` itself (§5.1).
    Deduplication is by SOURCE-OBJECT IDENTITY, never by name, so distinct objects that share a
    name are both emitted (§5.2). ``bpy.data.objects`` is never consulted (§5.2).
    """
    root = getattr(scene, "collection", None)
    if root is None:
        raise SceneMembershipError(
            "scene.collection is unavailable; cannot enumerate scene membership (fail closed)"
        )
    root_key = _identity_key(root)
    objects: List[Any] = []
    seen_objects: set = set()
    containing_names: Dict[Any, List[str]] = {}
    seen_collections: set = set()
    stack: List[Any] = [root]
    while stack:
        collection = stack.pop()
        ck = _identity_key(collection)
        if ck in seen_collections:
            continue
        seen_collections.add(ck)
        is_root = ck == root_key
        if not is_root:
            # §5.4 step 1/2: only reachable child collections are candidates, and the master
            # collection is never eligible as a representative (excluded by identity).
            collection_name = _read_name(getattr(collection, "name", None), "collection.name")
        else:
            collection_name = ""
        for obj in _read_collection_members(collection):
            ok = _identity_key(obj)
            if ok not in seen_objects:
                seen_objects.add(ok)
                objects.append(obj)
            if not is_root:
                containing_names.setdefault(ok, []).append(collection_name)
        stack.extend(_read_collection_children(collection))

    representatives: Dict[Any, Optional[str]] = {}
    for obj in objects:
        names = containing_names.get(_identity_key(obj))
        # §5.4 step 3/4: code-point lexical minimum, else null (master-only objects).
        representatives[_identity_key(obj)] = min(names) if names else None
    return objects, representatives


# ---------------------------------------------------------------------------
# §7 — transform and visibility
# ---------------------------------------------------------------------------


def _read_rotation(obj: Any, label: str) -> Tuple[float, float, float, float]:
    """Select the rotation channel by ``rotation_mode`` (§7.2) and never substitute identity."""
    if not hasattr(obj, "rotation_mode"):
        raise ValueError(f"{label}.rotation_mode is absent; refusing an unreadable mode (fail closed)")
    mode = getattr(obj, "rotation_mode")
    if type(mode) is not str:
        raise ValueError(f"{label}.rotation_mode is not a readable mode (fail closed)")

    if mode == _EULER_MODE_XYZ:
        if not hasattr(obj, "rotation_euler"):
            raise ValueError(f"{label}.rotation_euler is absent for mode 'XYZ' (fail closed)")
        ex, ey, ez = _read_axes(getattr(obj, "rotation_euler"), f"{label}.rotation_euler")
        return euler_xyz_degrees_to_quaternion(
            math.degrees(ex), math.degrees(ey), math.degrees(ez)
        )

    if mode == _QUATERNION_MODE:
        if not hasattr(obj, "rotation_quaternion"):
            raise ValueError(f"{label}.rotation_quaternion is absent for mode 'QUATERNION' (fail closed)")
        quat = getattr(obj, "rotation_quaternion")
        if quat is None:
            raise ValueError(f"{label}.rotation_quaternion is absent (fail closed)")
        components: List[float] = []
        for index, axis in enumerate(("w", "x", "y", "z")):
            if not hasattr(quat, axis):
                raise ValueError(f"{label}.rotation_quaternion.{axis} is missing (fail closed)")
            components.append(_finite_number(getattr(quat, axis), f"{label}.rotation_quaternion[{index}]"))
        # §7.2.1 rule 2/3: non-finite components are refused by _finite_number; an all-zero source
        # quaternion is refused here because nothing downstream validates it.
        if all(c == 0.0 for c in components):
            raise ValueError(
                f"{label}.rotation_quaternion is all-zero; refusing an invalid rotation (fail closed)"
            )
        # §7.2.1 rule 1: verbatim copy, Blender (w, x, y, z) -> payload (w, x, y, z).
        return (components[0], components[1], components[2], components[3])

    raise ValueError(
        f"{label}.rotation_mode {mode!r} is unsupported; no conversion is defined in-tree (§7.2) (fail closed)"
    )


def _read_visibility(obj: Any, label: str) -> bool:
    """§7.3: ``visible = not obj.hide_viewport`` — the data property only, never a substitute."""
    if not hasattr(obj, "hide_viewport"):
        raise ValueError(f"{label}.hide_viewport is absent; refusing to substitute True (fail closed)")
    hide_viewport = getattr(obj, "hide_viewport")
    if type(hide_viewport) is not bool:
        raise ValueError(
            f"{label}.hide_viewport is not a bool ({hide_viewport!r}); refusing to interpret it (fail closed)"
        )
    return not hide_viewport


# ---------------------------------------------------------------------------
# §4.3 — materials: ordered, single-valued decision tree
# ---------------------------------------------------------------------------


def _extract_materials(obj: Any, label: str) -> Optional[List[str]]:
    """Return the mesh datablock's slot names, ``[]``, or ``None`` meaning "omit the key" (§4.3).

    Branch precedence is normative and single-valued:
      1. any slot whose material is assigned but carries a malformed/empty name -> FAIL CLOSED;
      2. any unrepresentable object-level slot (``link == 'OBJECT'`` or unassigned) -> OMIT the key
         entirely, and this branch dominates even when the mesh datablock has zero data slots;
      3. zero data slots (and, by branch 2, no OBJECT-linked slot) -> ``[]``;
      4. otherwise the data-slot names in exact source slot order (never lexically sorted).
    """
    object_slots = getattr(obj, "material_slots", None)
    if object_slots is None:
        raise ValueError(
            f"{label}.material_slots is unavailable; cannot determine slot representability (fail closed)"
        )
    data_slots = getattr(getattr(obj, "data", None), "materials", None)
    if data_slots is None:
        raise ValueError(f"{label}.data.materials is unavailable (fail closed)")

    # Branch 1 — fail closed on any present-but-invalid material name.
    for slot in object_slots:
        material = getattr(slot, "material", None)
        if material is None:
            continue
        name = getattr(material, "name", None)
        if type(name) is not str or not name.strip():
            raise ValueError(
                f"{label} has a material slot with a malformed/empty material name; "
                "refusing to invent a token (§4.3 branch 1) (fail closed)"
            )

    # Branch 2 — all-or-nothing omission; dominates over the empty-data-slot case.
    for slot in object_slots:
        link = getattr(slot, "link", None)
        if link not in ("DATA", _OBJECT_LINK):
            raise ValueError(
                f"{label} has a material slot with an unreadable link ({link!r}) (fail closed)"
            )
        if link == _OBJECT_LINK or getattr(slot, "material", None) is None:
            return None

    # Branch 3 — a legitimately empty material domain.
    if len(data_slots) == 0:
        return []

    # Branch 4 — exact source slot order.
    names: List[str] = []
    for material in data_slots:
        if material is None:
            raise ValueError(
                f"{label}.data.materials contains an unassigned slot mid-list; refusing a partial list (fail closed)"
            )
        names.append(_read_name(getattr(material, "name", None), f"{label}.data.materials[i].name"))
    return names


# ---------------------------------------------------------------------------
# §6 — mesh identity and source-order geometry
# ---------------------------------------------------------------------------


def _vertex_coords(vertex: Any) -> List[float]:
    """Read one vertex verbatim under §8.1 (six decimals, correctly-rounded half-even)."""
    if hasattr(vertex, "co"):
        co = getattr(vertex, "co")
        if co is None or len(co) < 3:
            raise ValueError("MeshVertex.co is malformed/absent; refusing to emit coordinates (fail closed)")
        return [
            round(_finite_number(co[axis], f"MeshVertex.co[{axis}]"), _COORD_DECIMALS)
            for axis in range(3)
        ]
    if all(hasattr(vertex, axis) for axis in ("x", "y", "z")):
        return [
            round(_finite_number(getattr(vertex, axis), f"MeshVertex.{axis}"), _COORD_DECIMALS)
            for axis in ("x", "y", "z")
        ]
    raise ValueError(
        "MeshVertex has neither a usable .co nor a complete .x/.y/.z surface; "
        "refusing to manufacture coordinates (fail closed)"
    )


def _face_indices(polygon: Any, label: str) -> List[int]:
    """Read one polygon's vertex indices in source loop order — no sorting, no reindexing (§6)."""
    indices = getattr(polygon, "vertices", None)
    if indices is None:
        raise ValueError(f"{label} is malformed/absent; refusing to invent topology (fail closed)")
    out: List[int] = []
    for index in indices:
        if type(index) is not int or isinstance(index, bool):
            raise ValueError(f"{label} contains a non-integer vertex index ({index!r}) (fail closed)")
        out.append(index)
    return out


def _extract_mesh(obj: Any, label: str) -> Optional[dict]:
    """Emit the §3 mesh record: ``{mesh_id, vertices, faces}`` plus ``materials`` as §4.3 permits."""
    data = getattr(obj, "data", None)
    if data is None:
        raise ValueError(f"mesh object {label} has no data; refusing a count-only mesh")
    vertices_raw = getattr(data, "vertices", None)
    if vertices_raw is None:
        raise ValueError(f"mesh object {label} exposes no vertex table (fail closed)")
    vertices = [_vertex_coords(v) for v in vertices_raw]
    if not vertices:
        raise ValueError("mesh has no vertices; refusing to emit an empty/partial mesh")

    polygons = getattr(data, "polygons", None)
    if polygons is None:
        raise ValueError(f"mesh object {label} exposes no polygon table (fail closed)")
    faces = [_face_indices(p, f"mesh object {label} polygon") for p in polygons]
    # Wave 11: zero polygons are a truthful source state. Never invent topology.

    mesh: dict = {
        "mesh_id": label,
        "vertices": vertices,
        "faces": faces,
    }
    # §4.1/§4.2/§4.4: normals, uvs and local_frame_id are omitted in v1 — the keys are never emitted
    # and never emitted as null. §4.3: materials is emitted only when the decision tree permits it.
    materials = _extract_materials(obj, label)
    if materials is not None:
        mesh["materials"] = materials
    return mesh


# ---------------------------------------------------------------------------
# §3 — object record
# ---------------------------------------------------------------------------


def _extract_object(bpy: Any, obj: Any, representative: Optional[str]) -> dict:
    label = _object_label(obj)
    object_id = _read_name(getattr(obj, "name", None), "object.name")

    parent = getattr(obj, "parent", None)
    parent_id: Optional[str] = None
    if parent is not None:
        parent_id = _read_name(getattr(parent, "name", None), f"object {object_id} parent name")

    location = _read_axes(getattr(obj, "location", None), f"object {object_id}.location")
    scale = _read_axes(getattr(obj, "scale", None), f"object {object_id}.scale")
    rotation = _read_rotation(obj, f"object {object_id}")
    visible = _read_visibility(obj, f"object {object_id}")

    obj_type = getattr(obj, "type", None)
    if type(obj_type) is not str:
        raise ValueError(f"object {object_id} exposes an unreadable type; refusing to guess its class")
    mesh = _extract_mesh(obj, object_id) if obj_type == "MESH" else None

    return {
        "object_id": object_id,
        "name": object_id,
        "collection": representative,
        "parent_object_id": parent_id,
        "location": [float(v) for v in location],
        "scale": [float(v) for v in scale],
        "rotation": [float(v) for v in rotation],
        "visible": visible,
        "mesh": mesh,
    }


# ---------------------------------------------------------------------------
# entry points
# ---------------------------------------------------------------------------


def extract_scene(bpy: Any) -> dict:
    """Extract the v1 read-only payload from the live Blender scene (§3, §5, §10).

    Any failure on any required object fails the whole extraction: no partial payload is ever
    returned as a successful result (§10).
    """
    context = getattr(bpy, "context", None)
    if context is None:
        raise ValueError("bpy.context is not available; cannot extract a scene")
    scene = getattr(context, "scene", None)
    if scene is None:
        raise ValueError("bpy.context.scene is not available; cannot extract a scene")
    scene_name = _read_name(getattr(scene, "name", None), "scene.name")
    try:
        unit_system = map_unit_system(getattr(scene, "unit_settings", None))
    except UnitMappingError as exc:
        raise ValueError(f"cannot map Blender unit system to canonical unit: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"cannot read Blender scene metadata: {exc}") from exc

    try:
        objects_raw, representatives = _discover_scene_membership(scene)
    except SceneMembershipError as exc:
        raise ValueError(str(exc)) from exc

    # §5.3: objects are emitted sorted by object_id (Unicode code-point order, Python str ordering);
    # §5.2: deduplication already happened by source-object identity, never by name.
    pairs = [(_read_name(getattr(o, "name", None), "object.name"), o) for o in objects_raw]
    pairs.sort(key=lambda pair: pair[0])
    objects = [
        _extract_object(bpy, obj, representatives.get(_identity_key(obj))) for _, obj in pairs
    ]

    payload = {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "scene_id": scene_name,
        "unit_system": unit_system,
        "objects": objects,
    }
    validate_payload_schema(payload)
    return payload


def run_live_blender_extraction(bpy: Any) -> dict:
    """Live entry point used by the operator-gated Blender gates."""
    return extract_scene(bpy)
