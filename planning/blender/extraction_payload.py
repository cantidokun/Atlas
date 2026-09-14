"""Versioned, language-agnostic Blender extraction payload schema (read-only).

This is the canonical, machine-readable payload a (future live) bpy extraction primitive — or a
C++ producer — emits so the deterministic mesh/scene health kernel can consume it. It is the
stable seam between a real Blender state and the kernel's canonical ``SceneModel``/``MeshModel``.

The payload contains NO ``bpy`` objects: only exact JSON-native values (exact str/int/float/bool,
lists, dicts with exact-str keys). It is emitted deterministically (see the deterministic
ordering notes below) and parsed by :func:`planning.blender.scene_model.parse_scene_report_input`.

Schema version: bump this when the payload contract changes in a non-backward-compatible way.
"""

PAYLOAD_SCHEMA_VERSION = "1"

# Allowable keys at each level (closed grammar; unknown keys are rejected by the parser).
_SCENE_KEYS = frozenset(
    {"schema_version", "scene_id", "unit_system", "coordinate_frame", "world_bounds", "objects"}
)
_OBJECT_KEYS = frozenset(
    {"object_id", "name", "collection", "parent_object_id", "location", "scale", "rotation",
     "visible", "mesh"}
)
_MESH_KEYS = frozenset(
    {"mesh_id", "vertices", "faces", "normals", "uvs", "materials",
     "local_frame_id"}
)


def validate_payload_schema(payload: dict, *, owner: str = "payload") -> None:
    """Fail-closed structural validation of the extraction payload's shape.

    This is the ONLY schema-level check the extraction boundary performs: it ensures the version
    is recognized and that every field maps to a valid Kernel-parseable payload. It does NOT
    duplicate the geometry/organization/readiness rules in ``mesh_health``/``scene_health`` — those
    belong to the kernel and are invoked via ``run_scene_health``.
    """
    if not isinstance(payload, dict):
        raise TypeError(f"{owner} must be a dict")
    unknown = set(payload) - _SCENE_KEYS
    if unknown:
        raise ValueError(f"{owner}: unknown scene payload keys: {sorted(unknown)}")
    if payload.get("schema_version") != PAYLOAD_SCHEMA_VERSION:
        raise ValueError(
            f"{owner}: unsupported payload schema_version {payload.get('schema_version')!r}"
        )
    for req in ("scene_id", "unit_system", "objects"):
        if req not in payload:
            raise ValueError(f"{owner}: missing required field {req!r}")
    objects = payload["objects"]
    if not isinstance(objects, list):
        raise TypeError(f"{owner}.objects must be a list")
    for i, obj in enumerate(objects):
        _validate_object(obj, f"{owner}.objects[{i}]")


def _validate_object(obj, owner: str) -> None:
    if not isinstance(obj, dict):
        raise TypeError(f"{owner} must be a dict")
    unknown = set(obj) - _OBJECT_KEYS
    if unknown:
        raise ValueError(f"{owner}: unknown object payload keys: {sorted(unknown)}")
    for req in ("object_id", "name"):
        if req not in obj:
            raise ValueError(f"{owner}: missing required object field {req!r}")
    mesh = obj.get("mesh")
    if mesh is not None:
        if not isinstance(mesh, dict):
            raise TypeError(f"{owner}.mesh must be a dict or null")
        _validate_mesh(mesh, f"{owner}.mesh")


def _validate_mesh(mesh: dict, owner: str) -> None:
    unknown = set(mesh) - _MESH_KEYS
    if unknown:
        raise ValueError(f"{owner}: unknown mesh payload keys: {sorted(unknown)}")
    if "mesh_id" not in mesh:
        raise ValueError(f"{owner}: missing required mesh field 'mesh_id'")
    if not isinstance(mesh.get("vertices"), list):
        raise TypeError(f"{owner}: 'vertices' must be a list")
    if not isinstance(mesh.get("faces"), list):
        raise TypeError(f"{owner}: 'faces' must be a list")
    # Optional per-face normals/uvs must be lists if present.
    for opt in ("normals", "uvs"):
        if opt in mesh and mesh[opt] is not None and not isinstance(mesh[opt], list):
            raise TypeError(f"{owner}: '{opt}' must be a list or absent")


# Deterministic ordering: the kernel sorts findings and canonical-keys the report, but the
# extraction payload itself should be emitted in a STABLE object order (derived from the source
# scene's stable, non-pointer identifiers). The bpy primitive must sort objects by a deterministic
# key (e.g. name/object_id) before emitting — never by Blender runtime pointer/order.


def payload_to_scene_model(payload: dict):
    """Convert a validated extraction payload into a canonical SceneModel.

    This is the ONLY payload->kernel seam: it (a) runs the fail-closed structural payload schema
    check (including schema_version recognition) and (b) delegates to the kernel's canonical
    parser after dropping the payload-only ``schema_version`` key. The SceneModel grammar does not
    know about the extraction payload version — that is this boundary's concern.
    """
    from planning.blender.scene_model import parse_scene_report_input

    validate_payload_schema(payload)
    kernel_payload = {k: v for k, v in payload.items() if k != "schema_version"}
    return parse_scene_report_input(kernel_payload)