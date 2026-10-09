"""A-REF fixture specification (FIX) model and validator — conformance scope only.

Design authority: REV46_M1_R4F_AREF_DESIGN_FIXTURE_CONTRACT_CLOSURE.txt
SHA-256 14f9c0c95c3db255f7f9122d05cd1b807caa9f6649ceb652fd387b4985b73b9b
(sections 8.1/8.2 marker contract; 9.10 plan rules P1-P3; 25 fixture spec; 23 G41/G48/G53).

This module is TEST/CONFORMANCE code: no production module imports it (R4F section 22).
It performs NO execution: it validates a fixture specification and exposes its parts.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# --- reserved marker and schema constants (R4F 8.2, 25) --------------------------------
MARKER = "AREF-TEST-"
FIXTURE_SCHEMA_VERSION = "aref-fix-v1"
OPERATIONS = (
    "REMOVE_DUPLICATE_FACE",
    "REMOVE_DEGENERATE_FACE",
    "REPAIR_FACE_WINDING",
    "REPAIR_MERGE_VERTEX",
)
#: Construction rules. "PM" (R4F 16.6(1) "each fixture declares its construction rule") = the
#: planner's explicit merge pass plan_merge_vertex_correction, the sole producer of a
#: REPAIR_MERGE_VERTEX correction at the pinned baseline (correction_planner.py:687-694).
PLAN_RULES = ("P1", "P2", "P3", "PM")

#: profile name_pattern of the kernel's default soccer profile (soccer_field_profile.py:68)
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

#: authorization artifact fields the pinned schema permits (correction_authorization.py:95-111)
AUTH_ALLOWED_FIELDS = frozenset({
    "authorization_version", "authorization_policy_version", "decision",
    "correction_type", "correction_id", "plan_id", "source_report_digest",
    "authorized_by", "authorized_at_utc", "designated_face_index",
    "expected_face_tuple", "expected_merge_mapping_digest", "scope_note",
})
AUTH_REQUIRED_FIELDS = frozenset({
    "authorization_version", "authorization_policy_version", "decision",
    "correction_type", "correction_id", "plan_id", "source_report_digest",
    "authorized_by", "authorized_at_utc",
})

#: free-text fields that MAY carry the AREF-TEST- marker (R4F 8.1/8.2: only these)
MARKER_PERMITTED_AUTH_FIELDS = ("authorized_by", "scope_note")
#: format-constrained fields that MUST NOT carry the marker (R4F G53)
HEX64_FIELDS = ("plan_id", "source_report_digest", "expected_merge_mapping_digest")

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
#: planner-derived correction id: {code}-{scope}-{hash8} (correction_planner.py:443-466)
CORRECTION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.]+-[A-Za-z0-9_.:\-]+-[0-9a-f]{8}$")

DISPOSITIONS = frozenset({
    "POSITIVELY_DEMONSTRATED", "STRUCTURALLY_UNREACHABLE", "NOT_APPLICABLE",
    "ENVIRONMENT_LIMITED", "INSUFFICIENT_EVIDENCE", "NON_COMPARABLE",
})

_ALLOWED_TOP_KEYS = frozenset({
    "fixture_id", "schema_version", "case", "operation", "scene", "datablocks",
    "objects", "sharing", "params", "plan_construction", "plan_source",
    "authorization_fixture", "expected",
})
_ALLOWED_DB_KEYS = frozenset({"db_key", "db_name", "vertices", "faces", "materials"})
_ALLOWED_OBJ_KEYS = frozenset({
    "object_id", "datablock_key", "type", "collection", "parent_object_id",
    "location", "scale", "rotation", "visible", "material_slots",
})
_ALLOWED_PLAN_CONSTRUCTION_KEYS = frozenset({"rule", "selected_pair", "keep_only_target", "repoint"})
#: Operations that consume an authorization artifact at the pinned baseline (executor gates).
AUTH_GATED_OPS = frozenset({"REPAIR_FACE_WINDING", "REPAIR_MERGE_VERTEX"})
_ALLOWED_EXPECTED_KEYS = frozenset({
    "pre_digest", "graph_witness", "plan", "outcomes", "child_digest", "oc_class", "disposition",
})


BINDING_CLASSES = frozenset({"BIND-BY-DIGEST", "BIND-BY-WITNESS", "BIND-BY-SPEC-ASSERT",
                             "DECLARED-ABSENT", "DECLARED-OUT"})

# R4F 9.9 / section 26 inventory: every executor-consumed field carries exactly one binding
# class. Row names mirror the frozen inventory; the two object-ordering rows are the design's
# own dual row split into its two single-class facts (digest list order; witness order).
FIELD_BINDING_CLASSES = {
    "scene_id": "BIND-BY-DIGEST",
    "unit_system": "BIND-BY-DIGEST",
    "coordinate_frame": "BIND-BY-DIGEST",
    "object_id": "BIND-BY-DIGEST",
    "name": "BIND-BY-DIGEST",
    "collection": "BIND-BY-DIGEST",
    "parent_object_id": "BIND-BY-DIGEST",
    "location": "BIND-BY-DIGEST",
    "scale": "BIND-BY-DIGEST",
    "rotation": "BIND-BY-DIGEST",
    "visible": "BIND-BY-DIGEST",
    "mesh_id": "BIND-BY-DIGEST",
    "vertices": "BIND-BY-DIGEST",
    "faces": "BIND-BY-DIGEST",
    "source_report_digest": "BIND-BY-DIGEST",
    "report_findings_and_codes": "BIND-BY-DIGEST",
    "object_ordering_digest_list_order": "BIND-BY-DIGEST",
    "object_type": "BIND-BY-WITNESS",
    "datablock_name": "BIND-BY-WITNESS",
    "sharing_relation": "BIND-BY-WITNESS",
    "material_slots": "BIND-BY-WITNESS",
    "object_ordering_witness_order": "BIND-BY-WITNESS",
    "materials": "BIND-BY-SPEC-ASSERT",
    "plan_parameters": "BIND-BY-SPEC-ASSERT",
    "authorization_artifact_fields": "BIND-BY-SPEC-ASSERT",
    "plan_entry_fields": "BIND-BY-SPEC-ASSERT",
    "plan_artifact_identity": "BIND-BY-SPEC-ASSERT",
    "world_bounds": "DECLARED-ABSENT",
    "normals": "DECLARED-ABSENT",
    "uvs": "DECLARED-ABSENT",
    "local_frame_id": "DECLARED-ABSENT",
    "blender_session_internals": "DECLARED-OUT",
    "edit_counts_and_history": "DECLARED-OUT",
    "engine_side_data_not_captured": "DECLARED-OUT",
    "timing": "DECLARED-OUT",
    "transport_metadata": "DECLARED-OUT",
    "unrelated_environment_state": "DECLARED-OUT",
}


def validate_binding_map(mapping=None) -> dict:
    """Closed-set + completeness check for the field-binding map (R4F 9.9, 26)."""
    m = dict(FIELD_BINDING_CLASSES if mapping is None else mapping)
    bad = sorted(k for k, v in m.items() if v not in BINDING_CLASSES)
    if bad:
        raise FixtureError(f"field-binding map: unknown class for {bad} (closed set {sorted(BINDING_CLASSES)})")
    if not m:
        raise FixtureError("field-binding map: empty")
    return m


def digest_bound_fields() -> frozenset:
    return frozenset(k for k, v in FIELD_BINDING_CLASSES.items() if v == "BIND-BY-DIGEST")


class FixtureError(Exception):
    """A fixture specification violated the R4F section 25 contract (fail closed)."""


def _require_exact(cond: bool, message: str) -> None:
    if not cond:
        raise FixtureError(message)


def _is_int(v: Any) -> bool:
    return type(v) is int


def _validate_coordinate(v: Any, label: str) -> float:
    """R4F 25 numeric rules: finite; round(v,6)==v; float32-exact; -0.0 rejected."""
    _require_exact(type(v) in (int, float) and not isinstance(v, bool),
                   f"{label}: must be an exact number, got {type(v).__name__}")
    f = float(v)
    _require_exact(f == f and f not in (float("inf"), float("-inf")), f"{label}: non-finite value rejected")
    _require_exact(round(f, 6) == f, f"{label}: not idempotent under the six-decimal extraction policy")
    _require_exact(struct.unpack("f", struct.pack("f", f))[0] == f, f"{label}: not exactly representable in float32")
    _require_exact(not (f == 0.0 and str(f).startswith("-")), f"{label}: negative zero is excluded")
    return f


def _validate_vec3(v: Any, label: str) -> List[float]:
    _require_exact(isinstance(v, (list, tuple)) and len(v) == 3, f"{label}: must be 3 values")
    return [_validate_coordinate(x, f"{label}[{i}]") for i, x in enumerate(v)]


def _validate_quaternion(v: Any, label: str) -> List[float]:
    _require_exact(isinstance(v, (list, tuple)) and len(v) == 4, f"{label}: must be 4 values [w,x,y,z]")
    return [_validate_coordinate(x, f"{label}[{i}]") for i, x in enumerate(v)]


def _validate_face(face: Any, label: str) -> List[int]:
    _require_exact(isinstance(face, (list, tuple)), f"{label}: face must be a list/tuple")
    _require_exact(len(face) >= 3, f"{label}: a face needs at least 3 indices")
    out = []
    for i, idx in enumerate(face):
        _require_exact(_is_int(idx), f"{label}[{i}]: face indices must be exact ints (bool rejected)")
        out.append(idx)
    return out


def _validate_marker_free_hex(v: Any, label: str) -> str:
    _require_exact(type(v) is str, f"{label}: must be a str")
    _require_exact(not v.startswith(MARKER), f"{label}: the {MARKER} marker must not be prefixed to a format-constrained field")
    _require_exact(bool(_HEX64.match(v)), f"{label}: must be exactly 64 lowercase hex characters")
    return v


def validate_authorization_fixture(auth: Any, *, case_requires_auth: bool) -> Optional[Dict[str, Any]]:
    """Validate one authorization fixture against the frozen schema (R4F 8.2/K1).

    ``case_requires_auth`` enforces a real invariant, not a comment: an authorization artifact is
    only meaningful for an authorization-gated operation (REPAIR_FACE_WINDING / REPAIR_MERGE_VERTEX
    at the pinned baseline). A non-gated case that DECLARES one is refused; a gated case may declare
    one or declare null (the AUTHORIZATION_REQUIRED negative case).

    Validates the fixture's authorization block (R4F 8.2 marker contract; G41/G53):

    - null is permitted (required for the AUTHORIZATION_REQUIRED negative case, 16.6(2)).
    - a present fixture must satisfy the pinned schema field sets (unknown fields rejected),
      carry the marker ONLY in `authorized_by` (and optionally `scope_note`), and keep
      plan_id / source_report_digest / correction_id marker-free and format-bound.
    """
    if not case_requires_auth:
        if auth is not None:
            raise FixtureError(
                "authorization_fixture: declared for a non-authorization-gated operation "
                f"(only {sorted(AUTH_GATED_OPS)} consume an authorization artifact)")
        return None
    if auth is None:
        return None
    _require_exact(isinstance(auth, dict), "authorization_fixture: must be an object or null")
    unknown = sorted(set(auth) - AUTH_ALLOWED_FIELDS)
    _require_exact(not unknown, f"authorization_fixture: unknown field(s) {unknown} (pinned schema rejects them)")
    missing = sorted(AUTH_REQUIRED_FIELDS - set(auth))
    _require_exact(not missing, f"authorization_fixture: missing required field(s) {missing}")
    for fname in ("plan_id", "source_report_digest"):
        _validate_marker_free_hex(auth[fname], f"authorization_fixture.{fname}")
    if "expected_merge_mapping_digest" in auth:
        _validate_marker_free_hex(auth["expected_merge_mapping_digest"], "authorization_fixture.expected_merge_mapping_digest")
    cid = auth["correction_id"]
    _require_exact(type(cid) is str, "authorization_fixture.correction_id: must be a str")
    _require_exact(not cid.startswith(MARKER), "authorization_fixture.correction_id: the marker must not be prefixed to a planner-derived identifier")
    _require_exact(bool(CORRECTION_ID_PATTERN.match(cid)),
                   "authorization_fixture.correction_id: must have the planner-derived {code}-{scope}-{hash8} form")
    ab = auth["authorized_by"]
    _require_exact(type(ab) is str, "authorization_fixture.authorized_by: must be a str")
    _require_exact(ab.startswith(MARKER),
                   f"authorization_fixture.authorized_by: must carry the {MARKER} marker (harness refusal rule, R4F 8.2)")
    if "scope_note" in auth and auth["scope_note"] is not None:
        _require_exact(type(auth["scope_note"]) is str, "authorization_fixture.scope_note: must be a str")
    for key in ("authorization_version", "authorization_policy_version", "decision",
                "correction_type", "authorized_at_utc"):
        _require_exact(type(auth[key]) is str and auth[key] != "", f"authorization_fixture.{key}: must be a non-empty str")
    if "designated_face_index" in auth and auth["designated_face_index"] is not None:
        _require_exact(_is_int(auth["designated_face_index"]), "authorization_fixture.designated_face_index: exact int required")
    if "expected_face_tuple" in auth and auth["expected_face_tuple"] is not None:
        _validate_face(auth["expected_face_tuple"], "authorization_fixture.expected_face_tuple")
    return dict(auth)


@dataclass
class FixtureSpec:
    """A validated R4F section 25 fixture specification (immutable copy of the input)."""

    fixture_id: str
    case: str
    operation: str
    scene: Dict[str, Any]
    datablocks: List[Dict[str, Any]]
    objects: List[Dict[str, Any]]
    sharing: Dict[str, List[str]]
    params: Dict[str, Any]
    plan_construction: Dict[str, Any]
    authorization_fixture: Optional[Dict[str, Any]]
    expected: Dict[str, Any]
    raw: Dict[str, Any] = field(repr=False, default_factory=dict)

    # -- graph helpers used by the pure builder -------------------------------------------------
    def datablock_by_key(self, db_key: str) -> Dict[str, Any]:
        for db in self.datablocks:
            if db["db_key"] == db_key:
                return db
        raise FixtureError(f"datablock_key {db_key!r} not declared")

    def objects_referencing(self, db_key: str) -> List[str]:
        return [o["object_id"] for o in self.objects if o["datablock_key"] == db_key]

    def object_names_sorted(self) -> List[str]:
        return sorted(o["object_id"] for o in self.objects)

    def case_requires_auth(self) -> bool:
        """A case 'requires' an authorization fixture iff the fixture declares one.

        R4F 8.2 marker refusal rule as clarified for the null case: the harness refuses a case
        that DECLARES an authorization fixture whose authorized_by lacks the marker. The
        AUTHORIZATION_REQUIRED negative case declares null and must reach the executor
        (R4F 16.6(2); R4F-review minor finding 2).
        """
        return self.authorization_fixture is not None


def validate_fixture(spec: Any) -> FixtureSpec:
    """Fail-closed validation of one FIX specification against R4F section 25."""
    _require_exact(isinstance(spec, dict), "fixture: must be an object")
    unknown = sorted(set(spec) - _ALLOWED_TOP_KEYS)
    _require_exact(not unknown, f"fixture: unknown top-level key(s) {unknown} (closed grammar)")
    for key in ("fixture_id", "schema_version", "case", "operation", "scene",
                "datablocks", "objects", "sharing", "params", "plan_construction", "expected"):
        _require_exact(key in spec, f"fixture: missing required key {key!r}")
    _require_exact(spec["schema_version"] == FIXTURE_SCHEMA_VERSION,
                   f"fixture.schema_version: unsupported {spec['schema_version']!r}")
    fid = spec["fixture_id"]
    _require_exact(type(fid) is str and fid.startswith(MARKER),
                   f"fixture.fixture_id: must carry the harness-side {MARKER} marker (R4F 8.2)")
    _require_exact(spec["case"] in ("C1", "C2", "C3", "C4"), "fixture.case: must be C1..C4")
    _require_exact(spec["operation"] in OPERATIONS, f"fixture.operation: unsupported {spec['operation']!r}")
    _require_exact(spec.get("plan_source") == "REAL_PLANNER", "fixture.plan_source: must be REAL_PLANNER")

    scene = spec["scene"]
    _require_exact(isinstance(scene, dict) and set(scene) <= {"scene_id", "unit_system", "coordinate_frame"},
                   "fixture.scene: keys must be scene_id/unit_system/coordinate_frame")
    _require_exact(type(scene.get("scene_id")) is str and scene["scene_id"], "fixture.scene.scene_id required")
    _require_exact(type(scene.get("unit_system")) is str and scene["unit_system"], "fixture.scene.unit_system required")

    dbs = spec["datablocks"]
    _require_exact(isinstance(dbs, list) and dbs, "fixture.datablocks: non-empty list required")
    db_keys = set()
    for i, db in enumerate(dbs):
        _require_exact(isinstance(db, dict) and not (set(db) - _ALLOWED_DB_KEYS),
                       f"datablocks[{i}]: unknown keys {sorted(set(db) - _ALLOWED_DB_KEYS)}")
        _require_exact(type(db.get("db_key")) is str and db["db_key"], f"datablocks[{i}].db_key required")
        _require_exact(db["db_key"] not in db_keys, f"datablocks[{i}].db_key duplicate")
        db_keys.add(db["db_key"])
        _require_exact(type(db.get("db_name")) is str and NAME_PATTERN.match(db["db_name"]),
                       f"datablocks[{i}].db_name: must satisfy the profile name pattern")
        verts = db.get("vertices")
        _require_exact(isinstance(verts, list) and verts, f"datablocks[{i}].vertices: non-empty list required")
        for vi, v in enumerate(verts):
            _validate_vec3(v, f"datablocks[{i}].vertices[{vi}]")
        faces = db.get("faces")
        _require_exact(isinstance(faces, list), f"datablocks[{i}].faces: list required")
        for fi, face in enumerate(faces):
            f = _validate_face(face, f"datablocks[{i}].faces[{fi}]")
            for j, idx in enumerate(f):
                _require_exact(0 <= idx < len(verts),
                               f"datablocks[{i}].faces[{fi}][{j}]: index {idx} out of range [0,{len(verts)})")
        if "materials" in db and db["materials"] != "OMITTED":
            _require_exact(isinstance(db["materials"], list) and all(type(m) is str for m in db["materials"]),
                           f"datablocks[{i}].materials: list of str or \"OMITTED\"")

    objs = spec["objects"]
    _require_exact(isinstance(objs, list) and objs, "fixture.objects: non-empty list required")
    names = set()
    for i, obj in enumerate(objs):
        _require_exact(isinstance(obj, dict) and not (set(obj) - _ALLOWED_OBJ_KEYS),
                       f"objects[{i}]: unknown keys {sorted(set(obj) - _ALLOWED_OBJ_KEYS)}")
        oid = obj.get("object_id")
        _require_exact(type(oid) is str and NAME_PATTERN.match(oid),
                       f"objects[{i}].object_id: must satisfy the profile name pattern (unique, lowercase)")
        _require_exact(oid not in names, f"objects[{i}].object_id: duplicate object name {oid!r} (invalid fixture)")
        names.add(oid)
        _require_exact(obj.get("type") in ("MESH", "EMPTY", "OTHER"), f"objects[{i}].type invalid")
        dk = obj.get("datablock_key")
        if obj["type"] == "MESH":
            _require_exact(dk in db_keys, f"objects[{i}].datablock_key: must reference a declared datablock")
        else:
            _require_exact(dk is None, f"objects[{i}].datablock_key: must be null for non-MESH objects")
        if "collection" in obj and obj["collection"] is not None:
            _require_exact(type(obj["collection"]) is str, f"objects[{i}].collection: str or null")
        if "parent_object_id" in obj and obj["parent_object_id"] is not None:
            _require_exact(obj["parent_object_id"] in names, f"objects[{i}].parent_object_id: must reference a declared object")
        _validate_vec3(obj.get("location", [0.0, 0.0, 0.0]), f"objects[{i}].location")
        _validate_vec3(obj.get("scale", [1.0, 1.0, 1.0]), f"objects[{i}].scale")
        _validate_quaternion(obj.get("rotation", [1.0, 0.0, 0.0, 0.0]), f"objects[{i}].rotation")
        _require_exact(type(obj.get("visible", True)) is bool, f"objects[{i}].visible: exact bool required")
        slots = obj.get("material_slots")
        if slots is not None:
            _require_exact(isinstance(slots, list), f"objects[{i}].material_slots: list required")
            for si, slot in enumerate(slots):
                _require_exact(isinstance(slot, list) and len(slot) == 2,
                               f"objects[{i}].material_slots[{si}]: [link, name] pair required")
                _require_exact(slot[0] in ("OBJECT", "DATA"),
                               f"objects[{i}].material_slots[{si}][0]: link must be OBJECT or DATA")
                _require_exact(slot[1] is None or (type(slot[1]) is str and NAME_PATTERN.match(slot[1])),
                               f"objects[{i}].material_slots[{si}][1]: null or a pattern-valid name (R4F 9.8/25)")

    sharing = spec["sharing"]
    _require_exact(isinstance(sharing, dict), "fixture.sharing: object required")
    _require_exact(set(sharing) == db_keys, "fixture.sharing: must name exactly the declared datablocks")
    for db_key, lst in sharing.items():
        refs = sorted(o["object_id"] for o in objs if o["datablock_key"] == db_key)
        _require_exact(isinstance(lst, list) and sorted(lst) == refs,
                       f"fixture.sharing[{db_key}]: must match the object -> datablock references exactly")

    pc = spec["plan_construction"]
    _require_exact(isinstance(pc, dict) and not (set(pc) - _ALLOWED_PLAN_CONSTRUCTION_KEYS),
                   f"plan_construction: unknown keys {sorted(set(pc) - _ALLOWED_PLAN_CONSTRUCTION_KEYS)}")
    rule = pc.get("rule")
    _require_exact(rule in PLAN_RULES, f"plan_construction.rule: must be one of {PLAN_RULES}")
    if rule == "P1":
        _require_exact(pc.get("selected_pair") is None and pc.get("keep_only_target") is None,
                       "plan_construction: P1 must not declare selected_pair/keep_only_target")
    if rule == "P2":
        sp = pc.get("selected_pair")
        _require_exact(isinstance(sp, list) and len(sp) == 2 and all(_is_int(x) for x in sp) and sp[0] != sp[1],
                       "plan_construction.selected_pair: two distinct exact ints required for P2")
    if rule == "P3":
        kot = pc.get("keep_only_target")
        _require_exact(isinstance(kot, list) and len(kot) >= 1 and all(type(x) is str for x in kot),
                       "plan_construction.keep_only_target: list of mesh_id strings required for P3")
    rp = pc.get("repoint")
    if rp is not None:
        _require_exact(rule == "P1",
                       "plan_construction.repoint: only meaningful with rule P1 (a pre-re-pointed real plan; R4F 16.2(b))")
        _require_exact(isinstance(rp, dict) and set(rp) == {"face_ids"},
                       'plan_construction.repoint must be {"face_ids": [a, b]}')
        fp = rp["face_ids"]
        _require_exact(isinstance(fp, list) and len(fp) == 2 and all(_is_int(x) for x in fp) and fp[0] != fp[1],
                       "plan_construction.repoint.face_ids: two distinct exact ints required")

    auth = validate_authorization_fixture(
        spec.get("authorization_fixture"), case_requires_auth=spec["operation"] in AUTH_GATED_OPS)

    exp = spec["expected"]
    _require_exact(isinstance(exp, dict) and not (set(exp) - _ALLOWED_EXPECTED_KEYS),
                   f"expected: unknown keys {sorted(set(exp) - _ALLOWED_EXPECTED_KEYS)}")
    _validate_marker_free_hex(exp.get("pre_digest", ""), "expected.pre_digest")
    gw = exp.get("graph_witness")
    _require_exact(isinstance(gw, dict), "expected.graph_witness: object required")
    order = gw.get("order")
    _require_exact(isinstance(order, list) and order == sorted(names),
                   "expected.graph_witness.order: must be the global ascending object-name order")
    mslots = gw.get("material_slots")
    if mslots is not None:
        _require_exact(isinstance(mslots, list), "expected.graph_witness.material_slots: list required (R4F 9.8)")
    pl = exp.get("plan")
    _require_exact(isinstance(pl, dict), "expected.plan: object required")
    for key in ("artifact_sha256", "plan_id", "source_report_digest"):
        _validate_marker_free_hex(pl.get(key, ""), f"expected.plan.{key}")
    cids = pl.get("correction_ids")
    _require_exact(isinstance(cids, list) and cids and all(type(c) is str and CORRECTION_ID_PATTERN.match(c) for c in cids),
                   "expected.plan.correction_ids: planner-derived ids required")
    oc = exp.get("oc_class")
    _require_exact(type(oc) is str and re.match(r"^OC[1-8]$", oc), "expected.oc_class: OC1..OC8")
    disp = exp.get("disposition")
    _require_exact(disp in DISPOSITIONS, f"expected.disposition: must be one of {sorted(DISPOSITIONS)}")

    import copy
    norm = copy.deepcopy(spec)
    norm["authorization_fixture"] = auth
    return FixtureSpec(
        fixture_id=fid, case=spec["case"], operation=spec["operation"], scene=dict(scene),
        datablocks=norm["datablocks"], objects=norm["objects"], sharing=norm["sharing"],
        params=norm["params"], plan_construction=norm["plan_construction"],
        authorization_fixture=auth, expected=norm["expected"], raw=norm,
    )

