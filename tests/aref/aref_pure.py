"""A-REF pure object/datablock graph, canonical projection, and the pure mutator mirror.

Design authority: R4F sections 4.A (pure engine state), 4.B (pure extractor), 4.C (pure mutator),
5 (no duplicated predicate authority), 6 (executor-owned occurrence selection), 9.1/9.2
(canonical child + digest), 9.6 (fixture purity), 25 (fixture rules).

Test/conformance scope only. The pure path invokes the EXISTING executor unchanged; it never
reimplements the execution policy (R4F sections 3, 5). The mutator mirror raises the
harness-owned EnvelopeRefusal (RC-* codes; R4F 4.C, 10.6).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from planning.blender.extraction_payload import PAYLOAD_SCHEMA_VERSION
from planning.blender.extraction_payload import payload_to_scene_model
from planning.blender.kernel import run_scene_health, soccer_field_profile_default

from tests.aref.aref_fixture import FixtureSpec, FixtureError


class EnvelopeRefusal(Exception):
    """Harness-owned pure-envelope refusal (RC-* reason codes; R4F 4.C, 10.6).

    The pure mutator is a faithful mirror: it raises ONLY this type for its refusal conditions.
    The executor converts ANY exception into its own outcome exactly as on the live path
    (correction_executor.py:643-646), so this type never escapes to production semantics.
    """

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass
class Datablock:
    """A pure mesh datablock record (shared identity; R4F 4.A)."""

    db_key: str
    db_name: str
    vertices: List[List[float]]
    faces: List[List[int]]
    materials: Optional[List[str]] = None


@dataclass
class PureObject:
    """A pure object record (R4F 4.A)."""

    object_id: str
    name: str
    type: str
    db_key: Optional[str] = None
    collection: Optional[str] = None
    parent_object_id: Optional[str] = None
    location: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    scale: List[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])
    rotation: List[float] = field(default_factory=lambda: [1.0, 0.0, 0.0, 0.0])
    visible: bool = True
    # NON-canonical (R4F 26: material_slots row is OUT of the digest) -> BIND-BY-WITNESS only.
    material_slots: List[List[Any]] = field(default_factory=list)


class PureGraph:
    """Pure object/datablock graph. Multiple objects may reference ONE datablock (R4F 4.A).

    The sharing relation is represented by SHARED IDENTITY (references to the same Datablock
    instance), never by independently copied tables: a mutation through one object's datablock
    is observed by every referencing object on the next projection, exactly as the live
    in-place rebuild behaves (correction_execution_bridge_runtime.py:133-146, :207-212;
    bpy_extraction.py:325).
    """

    def __init__(self, datablocks: Dict[str, Datablock], objects: Dict[str, PureObject]) -> None:
        self.datablocks = datablocks
        self.objects = objects

    def canonical_state(self) -> Dict[str, Any]:
        """Deterministic JSON-able state of the whole graph (witness arguments-digest input)."""
        return {
            "datablocks": {k: {"db_name": db.db_name, "vertices": [list(v) for v in db.vertices],
                               "faces": [list(f) for f in db.faces], "materials": db.materials}
                           for k, db in sorted(self.datablocks.items())},
            "objects": {n: {"object_id": o.object_id, "name": o.name, "type": o.type,
                            "db_key": o.db_key, "collection": o.collection,
                            "parent_object_id": o.parent_object_id, "location": list(o.location),
                            "scale": list(o.scale), "rotation": list(o.rotation),
                            "visible": o.visible, "material_slots": [list(s) for s in o.material_slots]}
                        for n, o in sorted(self.objects.items())},
        }

    def object_names_sorted(self) -> List[str]:
        """Canonical emission order: global ascending object-name order (R4F 25; bpy_extraction.py:421-425)."""
        return sorted(self.objects)

    def project_payload(self, scene_id: str, unit_system: str,
                        coordinate_frame: Optional[str] = None) -> Dict[str, Any]:
        """Project the canonical extraction payload (R4F 4.A; bpy_extraction.py:342, :376).

        mesh_id is the OBJECT label (never the datablock name); vertices/faces are the
        referenced datablock's tables at projection time; objects are emitted in name order.
        """
        objects: List[Dict[str, Any]] = []
        for name in self.object_names_sorted():
            obj = self.objects[name]
            entry: Dict[str, Any] = {
                "object_id": obj.object_id,
                "name": obj.name,
                "collection": obj.collection,
                "parent_object_id": obj.parent_object_id,
                "location": [float(v) for v in obj.location],
                "scale": [float(v) for v in obj.scale],
                "rotation": [float(v) for v in obj.rotation],
                "visible": obj.visible,
                "mesh": None,
            }
            if obj.type == "MESH" and obj.db_key is not None:
                db = self.datablocks[obj.db_key]
                mesh: Dict[str, Any] = {
                    "mesh_id": obj.object_id,  # R4F 4.A: mesh_id is the OBJECT label
                    "vertices": [[float(c) for c in v] for v in db.vertices],
                    "faces": [list(f) for f in db.faces],
                }
                if db.materials is not None:
                    mesh["materials"] = list(db.materials)
                entry["mesh"] = mesh
            objects.append(entry)
        payload: Dict[str, Any] = {
            "schema_version": PAYLOAD_SCHEMA_VERSION,
            "scene_id": scene_id,
            "unit_system": unit_system,
            "objects": objects,
        }
        if coordinate_frame is not None:
            payload["coordinate_frame"] = coordinate_frame
        return payload


def build_graph(spec: FixtureSpec) -> PureGraph:
    """Build the pure graph ONLY from the fixture spec literals (R4F 9.6 purity rule).

    Never derived from any live value: this function's sole input is the validated FIX spec.
    """
    dbs: Dict[str, Datablock] = {}
    for db in spec.datablocks:
        materials = db.get("materials")
        dbs[db["db_key"]] = Datablock(
            db_key=db["db_key"], db_name=db["db_name"],
            vertices=[[float(c) for c in v] for v in db["vertices"]],
            faces=[list(f) for f in db["faces"]],
            materials=None if materials in (None, "OMITTED") else list(materials),
        )
    objs: Dict[str, PureObject] = {}
    for obj in spec.objects:
        objs[obj["object_id"]] = PureObject(
            object_id=obj["object_id"], name=obj["object_id"], type=obj["type"],
            db_key=obj.get("datablock_key"), collection=obj.get("collection"),
            parent_object_id=obj.get("parent_object_id"),
            location=[float(c) for c in obj.get("location", [0.0, 0.0, 0.0])],
            scale=[float(c) for c in obj.get("scale", [1.0, 1.0, 1.0])],
            rotation=[float(c) for c in obj.get("rotation", [1.0, 0.0, 0.0, 0.0])],
            visible=bool(obj.get("visible", True)),
            material_slots=[[s[0], s[1]] for s in obj.get("material_slots", [])],
        )
    return PureGraph(dbs, objs)


def fresh_graph(spec: FixtureSpec) -> PureGraph:
    """A fresh independent pure state for one execution (determinism; R4F 11.4)."""
    return build_graph(spec)


# ---------------------------------------------------------------------------------------------
# Pure extractor seam (R4F 4.B): payload -> existing canonical model -> existing kernel report.
# ---------------------------------------------------------------------------------------------

def make_pure_extractor(spec: FixtureSpec) -> Callable[[PureGraph], Tuple[Any, Any]]:
    """Return the pure extractor seam over the existing conversion + health path.

    Uses ONLY the established calls (payload_to_scene_model; run_scene_health with the default
    soccer profile) — the same three calls the bridge extractor makes
    (correction_execution_bridge_runtime.py:126-130). No health predicate is reimplemented.
    """
    def pure_extractor(graph: PureGraph) -> Tuple[Any, Any]:
        payload = graph.project_payload(spec.scene["scene_id"], spec.scene["unit_system"],
                                        spec.scene.get("coordinate_frame"))
        scene = payload_to_scene_model(payload)
        report = run_scene_health(scene, soccer_field_profile_default())
        return scene, report
    return pure_extractor


# ---------------------------------------------------------------------------------------------
# Pure mutator mirror (R4F 4.C): faithful mirror of the live enforcement envelope, per operation.
# The mirror NEVER selects; it executes only the executor-provided parameters.
# ---------------------------------------------------------------------------------------------

def _resolve_target(graph: PureGraph, object_id: Any, mesh_id: Any) -> Tuple[PureObject, Datablock]:
    """Mirror of bridge_runtime:148-162: object exists, is MESH, datablock NAME == mesh_id."""
    if type(object_id) is not str or object_id not in graph.objects:
        raise EnvelopeRefusal("RC-TARGET-MISMATCH", f"object {object_id!r} does not exist in the pure state")
    obj = graph.objects[object_id]
    if obj.type != "MESH" or obj.db_key is None:
        raise EnvelopeRefusal("RC-TARGET-MISMATCH", f"object {object_id!r} is not a MESH object")
    db = graph.datablocks[obj.db_key]
    if db.db_name != mesh_id:
        raise EnvelopeRefusal("RC-TARGET-MISMATCH",
                              f"datablock name {db.db_name!r} != executor-provided mesh_id {mesh_id!r}")
    return obj, db


def make_pure_mutator(operation: str) -> Callable[..., None]:
    """Return the pure mirror for one operation. kwargs are exactly the executor's.

    The mirror replicates the LIVE enforcement envelope of correction_execution_bridge_runtime.py
    (baseline 90e4d0a) operation by operation: the same selector-completeness rule, the same
    exact-int/range checks (and the same ABSENCE of checks the live code does not make), the same
    operand comparisons — the executor-provided expected tuple is compared AS GIVEN, never coerced —
    and the same mechanical application. It never selects; it decides no policy (R4F 4.C, 6.2).
    """
    if operation in ("REMOVE_DUPLICATE_FACE", "REMOVE_DEGENERATE_FACE"):
        def face_removal_mutator(engine_state: PureGraph, **kwargs: Any) -> None:
            # Mirror of bridge_runtime _face_removal_mutator (90e4d0a :180-217). The live selector
            # sentinels mean "keyword absent from the call"; kwargs membership is the same test.
            _, db = _resolve_target(engine_state, kwargs.get("object_id"), kwargs.get("mesh_id"))
            duplicate_selector_present = ("selected_face_index" in kwargs
                                          or "expected_face_tuple" in kwargs)
            degenerate_selector_present = ("face_id" in kwargs or "face_tuple" in kwargs)
            if duplicate_selector_present == degenerate_selector_present:
                raise EnvelopeRefusal("RC-SELECTOR",
                                      "face removal requires exactly one complete operation selector")
            if duplicate_selector_present:
                if ("selected_face_index" not in kwargs or "expected_face_tuple" not in kwargs
                        or "face_id" in kwargs or "face_tuple" in kwargs):
                    raise EnvelopeRefusal(
                        "RC-SELECTOR",
                        "duplicate-face mutation requires only its exact index and expected tuple")
                idx = kwargs.get("selected_face_index")
                if type(idx) is not int:
                    raise EnvelopeRefusal("RC-EXACT-INDEX",
                                          "duplicate-face selected_face_index must be an exact int")
                if idx < 0 or idx >= len(db.faces):
                    raise EnvelopeRefusal("RC-INDEX-RANGE",
                                          "duplicate-face selected index is outside the pure mesh")
                # live: faces[selected_face_index] != expected_face_tuple — compare AS GIVEN.
                if tuple(db.faces[idx]) != kwargs.get("expected_face_tuple"):
                    raise EnvelopeRefusal(
                        "RC-TUPLE-MISMATCH",
                        f"faces[{idx}] {tuple(db.faces[idx])!r} != expected {kwargs.get('expected_face_tuple')!r}")
                remove_index = idx
            else:
                if "face_id" not in kwargs or "face_tuple" not in kwargs:
                    raise EnvelopeRefusal("RC-PRESENCE",
                                          "degenerate-face mutation requires face_id and face_tuple")
                if type(kwargs.get("face_id")) is not int:
                    raise EnvelopeRefusal("RC-EXACT-INDEX",
                                          "degenerate-face mutation requires an exact face_id")
                remove_index = kwargs.get("face_id")
            if remove_index < 0 or remove_index >= len(db.faces):
                raise EnvelopeRefusal("RC-INDEX-RANGE",
                                      f"recorded face index {remove_index} is outside the pure mesh")
            db.faces.pop(remove_index)  # in place: every referencing object observes the change
        return face_removal_mutator

    if operation == "REPAIR_FACE_WINDING":
        def winding_mutator(engine_state: PureGraph, **kwargs: Any) -> None:
            # Mirror of bridge_runtime _winding_mutator (90e4d0a :219-235): a range check with NO
            # type check (the live code has none), then the executor-provided tuple coerced exactly
            # as live coerces it (int-coerced tuple), then the reversal.
            _, db = _resolve_target(engine_state, kwargs.get("object_id"), kwargs.get("mesh_id"))
            idx = kwargs.get("face_index")
            if idx < 0 or idx >= len(db.faces):
                raise EnvelopeRefusal("RC-INDEX-RANGE", f"face_index {idx!r} out of range")
            expected = tuple(int(v) for v in kwargs.get("face_tuple"))
            if tuple(db.faces[idx]) != expected:
                raise EnvelopeRefusal("RC-TUPLE-MISMATCH", "faces[face_index] != face_tuple")
            db.faces[idx] = list(reversed(db.faces[idx]))
        return winding_mutator

    if operation == "REPAIR_MERGE_VERTEX":
        def merge_mutator(engine_state: PureGraph, *, object_id: Any, mesh_id: Any,
                          vertices: Any, faces: Any, old_to_new_mapping: Any) -> None:
            # Mirror of bridge_runtime _merge_mutator (90e4d0a :238-241): target resolution then the
            # mechanical application of the predicted tables. Required arguments, EXACTLY as live —
            # an absent table fails as a call-level TypeError (a generic fault), never as a refusal.
            _, db = _resolve_target(engine_state, object_id, mesh_id)
            # Live _same_datablock_rebuild (bridge_runtime:133-146) applies exactly these coercions:
            # vertices -> float (engine storage is float32; the fixture validator guarantees every
            # declared coordinate is float32-exact, so the doubles equal the stored values), faces ->
            # int. Mirroring the coercion (and adding none) keeps the mirror faithful: a value the
            # live rebuild would reject or coerce is treated identically here. Exact-int/range
            # validation of the merge tables belongs to the EXECUTOR's merge preconditions, which
            # both paths share and neither reimplements.
            db.vertices = [[float(c) for c in v] for v in vertices]
            db.faces = [[int(i) for i in f] for f in faces]
            _ = old_to_new_mapping
        return merge_mutator

    raise FixtureError(f"unsupported operation {operation!r}")


# NOTE (R4F 4.C / K1-scope): the mirror intentionally contains NO RC-SLOTS-CHANGED branch.
# The pure transitions update table contents only and preserve the slot table by construction,
# so a pure-side slot refusal is unrepresentable (R4F section 4.C; the live-only check at
# correction_execution_bridge_runtime.py:135, :141-146 remains untouched production behavior).
