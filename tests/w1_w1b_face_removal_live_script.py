"""LIVE Blender driver for the W1/W1b face-removal gate family (run INSIDE Blender, never in CI).

Wave 15 — W1 `REMOVE_DUPLICATE_FACE` and W1b `REMOVE_DEGENERATE_FACE` live boundary closure.
Authoritative design: ``planning/blender/BLENDER_WAVE15_W1_W1B_W2_LIVE_CLOSURE_DESIGN.md``
(§B.1 authority classification, §C/§C.1 W1 contract + red-team F-1 evidence, §D/§D.A–D.D W1b
contract + sub-cases + red-team F-2 revalidation, §F/§F.1 Wave 14 fidelity transfer and the
test-only containment rule, §G material-index non-claim, §I target selection, §J.1/§J.2 matrices).

Executed by ``tests/test_live_blender_w1_w1b_face_removal_gate.py`` via::

    blender --background --python tests/w1_w1b_face_removal_live_script.py

It builds DISPOSABLE in-memory scenes (nothing is saved, no ``.blend`` is opened, the frozen
validation asset is never touched), runs the complete live path per case

    live Blender scene -> bpy_extraction.extract_scene -> payload_to_scene_model
    -> run_scene_health -> plan_scene_report (REAL planner) -> execute_remove_duplicate_face /
    execute_remove_degenerate_face (REAL executor, NO authorization artifact)
    -> REAL Blender mutation (Pattern B: same datablock) -> fresh extraction -> postconditions
    -> receipt + raw boundary evidence

and prints one JSON evidence block between the markers ``ATLAS_W1_W1B_LIVE_START`` /
``ATLAS_W1_W1B_LIVE_END``.

REQUIRED NON-CLAIM (design §G) — repeated here as design §G/F.1 mandate::

    Pattern B rebuild resets polygon.material_index. mesh.clear_geometry() followed by
    mesh.from_pydata(...) reconstructs every polygon with material_index == 0; per-face material
    assignment does NOT survive a geometry rebuild. Polygon material assignment is OUTSIDE the
    frozen Atlas representation contract. Wave 15 makes NO claim that per-face material assignment
    survives, and no live gate may assert material_index preservation.

RAW-EVIDENCE CONTAINMENT (design §F.1, red-team F-4) — all raw Blender fidelity assertions in this
driver (raw slot tables, datablock inventory, orphan detection, unrelated-object material state)
are TEST-ONLY boundary evidence: they live only in test/gate code, are not imported by production
code, are not promoted into a shared production assertion/validator library, and do not create a
hidden canonical Atlas contract. They record what a specific engine run did; they do not extend the
canonical model, and the canonical executors used here carry no material or datablock clause at all.

BOUNDARY: the mutation primitive is implemented HERE (live driver), exactly as the Wave 13/14 and
W6/W7 live gates do — no production module gains a bpy import, and the executors keep taking an
INJECTED mutator. No persistence, no save, no rollback, no cleanup, no retry, no second mutation.
"""

import hashlib
import json
import os
import sys
import traceback

# Blender's embedded Python does NOT honour the shell PYTHONPATH (Blender 4.4.3), so the repo root
# is put on sys.path explicitly. This adds an import path ONLY — no contract, no authority.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import bpy

from planning.blender.bpy_extraction import extract_scene
from planning.blender.correction_contract import CorrectionPlan
from planning.blender.correction_executor import (
    execute_remove_degenerate_face,
    execute_remove_duplicate_face,
)
from planning.blender.correction_planner import _correction_id, plan_scene_report
from planning.blender.correction_values import thaw_jsonable
from planning.blender.extraction_payload import (
    payload_representation_state,
    payload_to_scene_model,
)
from planning.blender.finding_codes import FindingCode
from planning.blender.kernel import run_scene_health, soccer_field_profile_default
from planning.blender.scene_report import REPORT_FORMAT_VERSION

# --------------------------------------------------------------------------- capability constants
W1 = "REMOVE_DUPLICATE_FACE"
W1B = "REMOVE_DEGENERATE_FACE"
DV = FindingCode.MESH_DUPLICATE_FACE.value
DEG = FindingCode.MESH_DEGENERATE_FACE.value
WINDING = FindingCode.MESH_WINDING_INCONSISTENT.value
NON_MANIFOLD = FindingCode.MESH_NON_MANIFOLD_EDGE.value
INVALID_INDEX = FindingCode.MESH_INVALID_INDEX.value

PROFILE = {"name": "soccer-field", "version": "1", "allowed_units": ["METERS", "meters", "m"],
           "name_pattern": r"^[a-z0-9][a-z0-9._-]*$"}
FROZEN_ASSET = os.path.join("tests", "assets", "blender", "atlas_transform_validation.blend")

# --------------------------------------------------------------------------- identity selection
#: Identity-based target selection (design §I). The decoy is named so that it sorts BEFORE the
#: target ("goal" < "pitch"): ``extract_scene`` emits objects in name-sorted order, so any
#: positional selector ("the first mesh object") would silently retarget the fixture. Resolution is
#: fail-loud and never falls back to another object.
TARGET_OBJECT_ID = "pitch"
TARGET_MESH_ID = "pitch"
DECOY_OBJECT_ID = "goal"

#: Wave 14 fidelity fixtures (in-memory only; no material datablock is ever saved).
TARGET_SLOTS_ASSIGNED = (("DATA", "turf"), ("DATA", "line_markings"))
TARGET_SLOTS_WITH_UNASSIGNED = (("DATA", "turf"), ("DATA", None), ("DATA", "goal_net"))
TARGET_SLOTS_WITH_OBJECT_LINKED = (("DATA", "turf"), ("OBJECT", "line_markings"))
DECOY_SLOTS = (("DATA", "banner"),)

#: W1 F-1 fixture (§C.1 / §M.7): the duplicate pair is the FINAL two face indices, so removing the
#: second member renumbers nothing (identity map), and faces 0/1 form an UNRELATED same-direction
#: winding pair whose finding must survive the repair bit-identically.
W1_VERTS = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, -1.0, 0.0),
            (10.0, 0.0, 0.0), (11.0, 0.0, 0.0), (10.0, 1.0, 0.0)]
W1_FACES = [(0, 1, 2), (0, 1, 3), (4, 5, 6), (4, 5, 6)]

#: Same duplicate pair but in the MIDDLE of the table (a distinguished follower face remains at
#: index 4), which is what makes a non-identity renumbering map observable at all (a duplicate pair
#: whose members are identical makes swapping WHICH member is removed invisible; a follower does not).
W1_MID_VERTS = W1_VERTS + [(20.0, 0.0, 0.0), (21.0, 0.0, 0.0), (20.0, 1.0, 0.0)]
W1_MID_FACES = [(0, 1, 2), (0, 1, 3), (4, 5, 6), (4, 5, 6), (7, 8, 9)]

#: W1b fixtures (§D.A–§D.C).
W1B_ZERO_AREA_VERTS = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (5.0, 5.0, 0.0)]
W1B_ZERO_AREA_FACES = [(0, 1, 2), (0, 1, 3)]            # face 0 collinear, face 1 non-degenerate
W1B_TWO_VERTEX_VERTS = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
W1B_TWO_VERTEX_FACES = [(0, 1)]                        # built as from_pydata(v, [], [(0, 1)])
W1B_ONLY_FACE_VERTS = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
W1B_ONLY_FACE_FACES = [(0, 1, 2)]                      # the single (degenerate) face -> zero-face post
W1B_TWO_DEGENERATE_VERTS = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0),
                            (10.0, 0.0, 0.0), (11.0, 0.0, 0.0), (12.0, 0.0, 0.0)]
W1B_TWO_DEGENERATE_FACES = [(0, 1, 2), (3, 4, 5)]      # two degenerate faces -> ambiguous plan
#: decoy faces used by most cases (a single non-degenerate triangle)
W1B_DECOY_FACES = [(0, 1, 2)]
#: decoy faces that ALSO carry a collinear (degenerate) face: vertices (20,20,20), (20,21,20),
#: (20,22,20) are collinear, so face (0,2,3) is degenerate -> used by the untargeted-degeneracy case
W1B_DECOY_FACES_WITH_DEGENERATE = [(0, 1, 2), (0, 2, 3)]


# --------------------------------------------------------------------------- live boundary
class LiveEngine:
    """The one mutable engine handle the executor is given (a thin holder, no extra authority)."""

    def __init__(self, bpy_module):
        self.bpy = bpy_module


def live_extractor(engine_state):
    """The EXISTING thin adapter: live bpy -> canonical payload -> SceneModel + kernel report."""
    payload = extract_scene(engine_state.bpy)
    scene = payload_to_scene_model(payload)
    report = run_scene_health(scene, soccer_field_profile_default())
    return scene, report


# --------------------------------------------------------------------------- fixture construction
def reset_scene():
    """Disposable in-memory scene: remove everything, keep the master scene collection."""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)


def material_slot_table(obj):
    """RAW Blender slot table: ordered ``[link, material name or None]`` pairs (TEST-ONLY, §F.1)."""
    return [[str(getattr(slot, "link", None)),
             (slot.material.name if getattr(slot, "material", None) is not None else None)]
            for slot in obj.material_slots]


def slot_material(name):
    if name is None:
        return None
    existing = bpy.data.materials.get(name)
    return existing if existing is not None else bpy.data.materials.new(name)


def apply_material_slots(obj, spec):
    """Build a slot table in the given order (``DATA`` assigned/unassigned, ``OBJECT`` linked)."""
    for index, (link, name) in enumerate(spec):
        obj.data.materials.append(slot_material(name))
        if link == "OBJECT":
            obj.material_slots[index].link = "OBJECT"
            obj.material_slots[index].material = slot_material(name)
    return material_slot_table(obj)


def build_scene(*, verts, faces, target_slots=None, decoy_slots=None,
                decoy_faces=W1B_DECOY_FACES):
    """One target mesh object ("pitch") + one decoy mesh object ("goal") in a child collection.

    The decoy is always present and always sorts before the target, so a positional selector would
    retarget the fixture and fail loudly (design §I).
    """
    reset_scene()
    mesh = bpy.data.meshes.new(TARGET_OBJECT_ID)
    mesh.from_pydata([tuple(float(c) for c in v) for v in verts], [],
                     [tuple(int(i) for i in f) for f in faces])
    mesh.update()
    target = bpy.data.objects.new(TARGET_OBJECT_ID, mesh)
    bpy.context.scene.collection.objects.link(target)
    if target_slots:
        apply_material_slots(target, target_slots)

    goals = bpy.data.collections.new("Goals")
    bpy.context.scene.collection.children.link(goals)
    decoy_mesh = bpy.data.meshes.new(DECOY_OBJECT_ID)
    decoy_mesh.from_pydata([tuple(float(c) for c in v) for v in
                            [(20.0, 20.0, 20.0), (21.0, 20.0, 20.0), (20.0, 21.0, 20.0),
                             (20.0, 22.0, 20.0), (21.0, 22.0, 20.0)]], [],
                           [tuple(int(i) for i in f) for f in decoy_faces])
    decoy_mesh.update()
    decoy = bpy.data.objects.new(DECOY_OBJECT_ID, decoy_mesh)
    goals.objects.link(decoy)
    if decoy_slots:
        apply_material_slots(decoy, decoy_slots)
    return target, decoy


def raw_snapshot():
    """INDEPENDENT raw-Blender snapshot (outside the extraction model) — TEST-ONLY evidence (§F.1)."""
    objects = []
    for obj in sorted(bpy.data.objects, key=lambda o: o.name):
        data = getattr(obj, "data", None)
        is_mesh = obj.type == "MESH" and data is not None
        objects.append({
            "name": obj.name,
            "type": obj.type,
            "data_block": getattr(data, "name", None),
            "vertex_count": len(data.vertices) if is_mesh else None,
            "edge_count": len(data.edges) if is_mesh else None,
            "polygon_count": len(data.polygons) if is_mesh else None,
            "loops": len(data.loops) if is_mesh else None,
            "polygon_sizes": [len(p.vertices) for p in data.polygons] if is_mesh else None,
            "vertices": [[round(float(c), 9) for c in v.co] for v in data.vertices] if is_mesh else None,
            "faces": [list(p.vertices) for p in data.polygons] if is_mesh else None,
            "material_slots": material_slot_table(obj) if is_mesh else None,
            "collections": sorted(c.name for c in obj.users_collection),
        })
    return {
        "objects": objects,
        "object_names_in_extraction_order": sorted(bpy.data.objects, key=lambda o: o.name) and
        [o.name for o in sorted(bpy.data.objects, key=lambda o: o.name)],
        "mesh_datablocks": sorted(m.name for m in bpy.data.meshes),
        "material_datablocks": sorted(m.name for m in bpy.data.materials),
        "filepath": bpy.data.filepath,
        "is_dirty": bool(bpy.data.is_dirty),
    }


def raw_object(snapshot, name):
    for entry in snapshot["objects"]:
        if entry["name"] == name:
            return entry
    return None


# --------------------------------------------------------------------------- evidence helpers
def histogram(report, mesh_id):
    """Per-mesh finding-class histogram: ``{code: {"count": n, "measured": [...]}}`` (design §C.1.1)."""
    hist = {}
    for finding in report.findings:
        if finding.mesh_id != mesh_id:
            continue
        entry = hist.setdefault(finding.code.value, {"count": 0, "measured": []})
        entry["count"] += 1
        entry["measured"].append(finding.measured)
    return {code: entry for code, entry in sorted(hist.items())}


def materials_view(payload, scene, object_id):
    """Canonical + payload-level material evidence for one object (§F)."""
    entry = next((o for o in payload["objects"] if o["object_id"] == object_id), None)
    mesh = (entry or {}).get("mesh") or {}
    target = next((o for o in scene.objects if o.object_id == object_id and o.mesh is not None), None)
    return {
        "key_present": "materials" in mesh,
        "payload_value": mesh.get("materials"),
        "canonical": list(target.mesh.materials) if target is not None else None,
        "representation_state": list(payload_representation_state(payload)),
    }


def renumbering_map(pre_faces, post_faces):
    """Map each surviving post face back to its pre-state index (first unused content match)."""
    used = set()
    mapping = []
    for face in post_faces:
        for index, pre in enumerate(pre_faces):
            if index not in used and list(pre) == list(face):
                used.add(index)
                mapping.append([index, len(mapping)])
                break
    return mapping


def content_binding(report, capability, mesh_id):
    """Content-verified pre-flight binding evidence (design §I): the finding the plan must target."""
    finding = next((f for f in report.findings if f.mesh_id == mesh_id
                    and f.code.value == (DV if capability == W1 else DEG)), None)
    if finding is None:
        return None
    return {"code": finding.code.value, "mesh_id": finding.mesh_id, "measured": finding.measured}


# --------------------------------------------------------------------------- plan handling
def report_dict(report):
    payload = report.to_json_compatible()
    payload["digest"] = report.digest()
    payload["report_format_version"] = REPORT_FORMAT_VERSION
    return payload


def real_plan(report):
    """The REAL planner, over the REAL kernel report of the live scene."""
    return plan_scene_report(report_dict(report), profile=PROFILE)


def remap_plan(plan, *, capability, face_ids=None, face_id=None, mesh_id=None, object_id=None,
               extra_parameter=None, source_digest=None, keep_only_target=False):
    """The DOCUMENTED remap used by the negative cases (design §D.D / §J, GLM finding m-3).

    The plan and every correction are taken from the REAL planner output; only the recorded
    parameter (or the plan's source digest) is re-pointed, the correction id is recomputed with the
    planner's own content-addressed helper, dependency edges are translated through that id map, and
    ``plan_id`` is recomputed BY THE CONTRACT from the resulting contents. No arbitrary plan field is
    hand-forged; the resulting plan is integrity-valid, which is exactly why the negative must be
    refused by the executor's fresh-evidence gates rather than by plan integrity.
    """
    corrections = []
    remap = {}
    if keep_only_target:
        # DOCUMENTED REMAP (documented in the driver header and asserted by the gate): the plan is
        # the REAL planner's output for the real report, reduced to the single correction that
        # targets TARGET_MESH_ID, so that a scene containing an ADDITIONAL (untargeted) degenerate
        # face on another object can be executed at all. Without this the planner's two degenerate
        # proposals hit the executor's one-correction-per-run rule (covered separately by
        # w1b-negative-ambiguous-multiple-degenerate-faces).
        plan = CorrectionPlan(
            plan_id="", source_report_digest=plan.source_report_digest, source_revision_id=None,
            planner_version="1", profile=thaw_jsonable(plan.profile),
            corrections=tuple(c for c in plan.corrections
                              if c.correction_type == capability and c.mesh_id == TARGET_MESH_ID),
            dependencies=(), summary_metrics=thaw_jsonable(plan.summary_metrics),
            state=plan.state, planning_errors=tuple(plan.planning_errors))
    for corr in plan.corrections:
        params = thaw_jsonable(corr.parameters)
        touched = False
        if corr.correction_type == capability:
            if face_ids is not None:
                params["face_ids"] = list(face_ids)
                touched = True
            if face_id is not None:
                params["face_id"] = face_id
                touched = True
            if mesh_id is not None:
                params["mesh_id"] = mesh_id
                touched = True
            if extra_parameter is not None:
                params[extra_parameter] = 1
                touched = True
        new_object_id = (object_id if object_id is not None
                         else corr.object_id) if corr.correction_type == capability else corr.object_id
        if object_id is not None and corr.correction_type == capability:
            touched = True
        new_mesh_id = params.get("mesh_id", corr.mesh_id) if corr.correction_type == capability \
            else corr.mesh_id
        new_id = _correction_id(FindingCode(corr.finding_code), new_object_id, new_mesh_id, params)
        remap[corr.correction_id] = new_id
        corrections.append(type(corr)(
            correction_id=new_id, finding_code=corr.finding_code, object_id=new_object_id,
            mesh_id=new_mesh_id, correction_type=corr.correction_type, parameters=params,
            rationale=corr.rationale, preconditions=thaw_jsonable(corr.preconditions),
            expected_postcondition=thaw_jsonable(corr.expected_postcondition), risk=corr.risk,
            severity=corr.severity, reversibility=corr.reversibility,
            dependencies=tuple(corr.dependencies), determinism=corr.determinism,
            requires_human_review=corr.requires_human_review, out_of_scope=corr.out_of_scope))
    return CorrectionPlan(
        plan_id="", source_report_digest=(source_digest or plan.source_report_digest),
        source_revision_id=None, planner_version="1", profile=thaw_jsonable(plan.profile),
        corrections=tuple(corrections),
        dependencies=tuple((remap.get(f, f), remap.get(t, t)) for f, t in plan.dependencies),
        summary_metrics=thaw_jsonable(plan.summary_metrics), state=plan.state,
        planning_errors=tuple(plan.planning_errors))


# --------------------------------------------------------------------------- live mutators
class _BaseMutator:
    """Pattern B (Wave 14 normative): rebuild the authorized tables IN PLACE on the SAME datablock."""

    primitive = "pattern_b_same_datablock"

    def __init__(self, *, mode="faithful", liar=False):
        self.mode = mode
        self.liar = liar
        self.calls = []
        self.engine_edits = 1

    def _record(self, kwargs):
        self.calls.append({k: (list(v) if isinstance(v, tuple) else v) for k, v in kwargs.items()})

    def _target(self, kwargs):
        obj = bpy.data.objects.get(kwargs["object_id"])
        if obj is None:
            raise RuntimeError(f"live target object {kwargs['object_id']!r} does not exist")
        return obj

    def _rebuild(self, obj, keep_faces):
        verts = [tuple(float(c) for c in v.co) for v in obj.data.vertices]
        obj.data.clear_geometry()
        obj.data.from_pydata(verts, [], [tuple(int(i) for i in f) for f in keep_faces])
        obj.data.update()

    def __call__(self, engine_state, **kwargs):
        raise NotImplementedError


class W1Mutator(_BaseMutator):
    """W1 live primitive: delete EXACTLY ONE face of the recorded duplicate pair (design §C)."""

    def __call__(self, engine_state, *, object_id, mesh_id, face_ids, dup_tuple, **kwargs):
        self._record({"object_id": object_id, "mesh_id": mesh_id, "face_ids": face_ids,
                      "dup_tuple": dup_tuple})
        pair = [int(i) for i in face_ids]
        if self.mode == "faithful":
            drop = {pair[-1]}                      # the FINAL recorded member (fixture policy)
        elif self.mode == "first_member":
            drop = {pair[0]}
        elif self.mode == "both_members":
            drop = set(pair)
        elif self.mode == "wrong_face":
            drop = {0}                             # a face that is not part of the pair
        elif self.mode == "noop":
            drop = set()
        elif self.mode in ("vertex_shift", "unrelated_mutation", "survivor_pair_altered",
                           "slot_destruction", "datablock_replacement", "orphan_creation",
                           "net_multiset_equivalent"):
            # hostile / evidence modes all START from the authorized single-face deletion and then
            # add their collateral damage
            drop = {pair[-1]}
        else:
            raise RuntimeError(f"unknown W1 mutator mode {self.mode!r}")
        if self.mode == "noop" or self.liar:
            if self.liar:
                return {"ok": True, "result": "COMPLETED"}
            return None
        obj = self._target({"object_id": object_id})
        faces = [list(p.vertices) for p in obj.data.polygons]
        keep = [f for index, f in enumerate(faces) if index not in drop]
        if self.mode == "survivor_pair_altered":
            # hostile: also reverse the UNRELATED winding pair (faces 0 and 1) while deleting the
            # authorized duplicate. The canonical one-face delta still holds, so only the gate's
            # histogram / survivor assertions can catch the collateral damage.
            keep = [list(reversed(keep[1])) if index == 1 else face
                    for index, face in enumerate(keep)]
        if self.mode == "vertex_shift":
            verts = [tuple(float(c) for c in v.co) for v in obj.data.vertices]
            obj.data.clear_geometry()
            obj.data.from_pydata([(verts[0][0] + 1.0, verts[0][1], verts[0][2])] + verts[1:], [],
                                 [tuple(int(i) for i in f) for f in keep])
            obj.data.update()
        elif self.mode == "unrelated_mutation":
            self._rebuild(obj, keep)
            decoy = bpy.data.objects.get(DECOY_OBJECT_ID)
            if decoy is not None:
                decoy.data.vertices[0].co = (99.0, 99.0, 99.0)
                decoy.data.update()
        elif self.mode == "slot_destruction":
            self._rebuild(obj, keep)
            while len(obj.data.materials):
                obj.data.materials.pop()
        elif self.mode == "datablock_replacement":
            # SUPERSEDED Pattern A, retained as a deliberately lossy diagnostic (Wave 14 §5)
            verts = [tuple(float(c) for c in v.co) for v in obj.data.vertices]
            new_mesh = bpy.data.meshes.new(obj.data.name)
            new_mesh.from_pydata(verts, [], [tuple(int(i) for i in f) for f in keep])
            new_mesh.update()
            obj.data = new_mesh
        elif self.mode == "net_multiset_equivalent":
            # hostile: TWO engine rebuilds in one mutator invocation -- delete both duplicate
            # members, then add one copy back -- so the surviving face MULTISET equals the
            # authorized one-face delta while the engine was edited twice.
            self.engine_edits = 2
            self._rebuild(obj, [f for index, f in enumerate(faces) if index not in set(pair)])
            self._rebuild(obj, [f for index, f in enumerate(faces) if index not in set(pair)]
                          + [list(dup_tuple)])
            return None
        elif self.mode == "orphan_creation":
            self._rebuild(obj, keep)
            bpy.data.meshes.new("w1_w1b_orphan_probe")
        else:
            self._rebuild(obj, keep)
        if self.liar:
            return {"ok": True, "result": "COMPLETED"}
        return None


class W1BMutator(_BaseMutator):
    """W1b live primitive: delete EXACTLY the recorded degenerate face (design §D)."""

    def __call__(self, engine_state, *, object_id, mesh_id, face_id, face_tuple, **kwargs):
        self._record({"object_id": object_id, "mesh_id": mesh_id, "face_id": face_id,
                      "face_tuple": face_tuple})
        if self.mode == "faithful":
            drop = {int(face_id)}
        elif self.mode == "wrong_face":
            drop = {0} if int(face_id) != 0 else {1}
        elif self.mode == "noop":
            drop = set()
        elif self.mode in ("vertex_shift", "unrelated_mutation", "slot_destruction"):
            # hostile / evidence modes start from the authorized single-face deletion
            drop = {int(face_id)}
        else:
            raise RuntimeError(f"unknown W1b mutator mode {self.mode!r}")
        if self.mode == "noop" or self.liar:
            if self.liar:
                return {"ok": True, "result": "COMPLETED"}
            return None
        obj = self._target({"object_id": object_id})
        faces = [list(p.vertices) for p in obj.data.polygons]
        keep = [f for index, f in enumerate(faces) if index not in drop]
        if self.mode == "vertex_shift":
            verts = [tuple(float(c) for c in v.co) for v in obj.data.vertices]
            obj.data.clear_geometry()
            obj.data.from_pydata([(verts[0][0] + 1.0, verts[0][1], verts[0][2])] + verts[1:], [],
                                 [tuple(int(i) for i in f) for f in keep])
            obj.data.update()
        elif self.mode == "unrelated_mutation":
            self._rebuild(obj, keep)
            decoy = bpy.data.objects.get(DECOY_OBJECT_ID)
            if decoy is not None:
                decoy.data.vertices[0].co = (99.0, 99.0, 99.0)
                decoy.data.update()
        elif self.mode == "slot_destruction":
            self._rebuild(obj, keep)
            while len(obj.data.materials):
                obj.data.materials.pop()
        else:
            self._rebuild(obj, keep)
        if self.liar:
            return {"ok": True, "result": "COMPLETED"}
        return None


# --------------------------------------------------------------------------- case runner
def run_case(label, *, capability, verts, faces, target_slots=TARGET_SLOTS_ASSIGNED,
             decoy_slots=DECOY_SLOTS, decoy_faces=W1B_DECOY_FACES, mutator_mode="faithful",
             liar=False, remap=None, engine_mutation=None, expect=None):
    """Build the disposable scene, run the whole live path, capture canonical + raw evidence."""
    build_scene(verts=verts, faces=faces, target_slots=target_slots, decoy_slots=decoy_slots,
                decoy_faces=decoy_faces)
    engine = LiveEngine(bpy)
    payload_before = extract_scene(bpy)
    pre_scene, pre_report = live_extractor(engine)

    # --- identity-based target resolution (design §I): never positional, never a fallback --------
    target_obj = next((o for o in pre_scene.objects
                       if o.object_id == TARGET_OBJECT_ID and o.mesh is not None), None)
    if target_obj is None or target_obj.mesh.mesh_id != TARGET_MESH_ID:
        raise RuntimeError(
            f"live fixture target {TARGET_OBJECT_ID!r}/{TARGET_MESH_ID!r} is missing from the "
            "extracted scene; this driver never falls back to another object")
    decoy_names = [o.object_id for o in pre_scene.objects if o.object_id == DECOY_OBJECT_ID]
    if not decoy_names:
        raise RuntimeError(f"live fixture decoy {DECOY_OBJECT_ID!r} is missing")

    plan = real_plan(pre_report)
    if remap is not None:
        plan = remap_plan(plan, capability=capability, **remap)
    corrections = [c for c in plan.corrections if c.correction_type == capability]
    parameters = [thaw_jsonable(c.parameters) for c in corrections]

    if engine_mutation is not None:
        engine_mutation()

    mutator = (W1Mutator(mode=mutator_mode, liar=liar) if capability == W1
               else W1BMutator(mode=mutator_mode, liar=liar))
    raw_before = raw_snapshot()
    if capability == W1:
        receipt = execute_remove_duplicate_face(engine_state=engine, plan=plan, mutator=mutator,
                                                extractor=live_extractor)
    else:
        receipt = execute_remove_degenerate_face(engine_state=engine, plan=plan, mutator=mutator,
                                                 extractor=live_extractor)
    raw_after = raw_snapshot()

    payload_after = None
    try:
        payload_after = extract_scene(bpy)
        post_scene, post_report = live_extractor(engine)
        post_error = None
    except Exception as exc:  # noqa: BLE001 - a destroyed post-state is itself evidence
        post_scene, post_report, post_error = None, None, f"{type(exc).__name__}: {exc}"

    pre_faces = raw_object(raw_before, TARGET_OBJECT_ID)["faces"]
    post_faces = raw_object(raw_after, TARGET_OBJECT_ID)["faces"]
    mapping = renumbering_map(pre_faces, post_faces)
    return {
        "case": label,
        "capability": capability,
        "expect": expect,
        "fixture": {"vertices": [list(v) for v in verts], "faces": [list(f) for f in faces],
                    "target_slots": [list(s) for s in (target_slots or ())],
                    "decoy_slots": [list(s) for s in (decoy_slots or ())],
                    "decoy_faces": [list(f) for f in decoy_faces]},
        "target": {"object_id": TARGET_OBJECT_ID, "mesh_id": TARGET_MESH_ID,
                   "resolved_by": "identity", "decoy_object_id": DECOY_OBJECT_ID,
                   "decoy_sorts_before_target": DECOY_OBJECT_ID < TARGET_OBJECT_ID},
        "binding": {"proposal_count": len(corrections),
                    "correction_ids": [c.correction_id for c in corrections],
                    "parameters": parameters,
                    "expected_finding": content_binding(pre_report, capability, TARGET_MESH_ID),
                    "correction_contract": None if not corrections else {
                        "finding_code": str(corrections[0].finding_code),
                        "rationale": corrections[0].rationale,
                        "preconditions": thaw_jsonable(corrections[0].preconditions),
                        "expected_postcondition": thaw_jsonable(corrections[0].expected_postcondition),
                        "risk": corrections[0].risk,
                        "severity": corrections[0].severity,
                        "reversibility": corrections[0].reversibility,
                        "determinism": corrections[0].determinism,
                        "requires_human_review": corrections[0].requires_human_review,
                    }},
        "plan": {"plan_id": plan.plan_id, "state": plan.state,
                 "source_report_digest": plan.source_report_digest,
                 "all_correction_types": [c.correction_type for c in plan.corrections]},
        "mutator": {"primitive": mutator.primitive, "mode": mutator_mode, "liar": liar,
                    "invocations": len(mutator.calls), "engine_edits": mutator.engine_edits,
                    "calls": mutator.calls},
        "pre": {
            "digest": pre_report.digest(),
            "vertex_count": len(target_obj.mesh.vertices),
            "faces": [list(f) for f in target_obj.mesh.faces],
            "histogram": histogram(pre_report, TARGET_MESH_ID),
            "decoy_histogram": histogram(pre_report, DECOY_OBJECT_ID),
            "materials": materials_view(payload_before, pre_scene, TARGET_OBJECT_ID),
            "decoy_materials": materials_view(payload_before, pre_scene, DECOY_OBJECT_ID),
        },
        "post": None if (post_report is None or payload_after is None) else {
            "digest": post_report.digest(),
            "vertex_count": len(next(o.mesh.vertices for o in post_scene.objects
                                     if o.object_id == TARGET_OBJECT_ID)),
            "faces": [list(f) for f in next(o.mesh.faces for o in post_scene.objects
                                            if o.object_id == TARGET_OBJECT_ID)],
            "histogram": histogram(post_report, TARGET_MESH_ID),
            "decoy_histogram": histogram(post_report, DECOY_OBJECT_ID),
            "materials": materials_view(payload_after, post_scene, TARGET_OBJECT_ID),
            "decoy_materials": materials_view(payload_after, post_scene, DECOY_OBJECT_ID),
        },
        "post_extraction_error": post_error,
        "receipt": {
            "result": receipt["result"],
            "failure_code": receipt["failure_code"],
            "field_count": len(receipt),
            "has_authorization_verified_field": "authorization_verified" in receipt,
            "plan_id": receipt["plan_id"],
            "plan_id_recomputed": receipt["plan_id_recomputed"],
            "plan_integrity_ok": receipt["plan_id"] == receipt["plan_id_recomputed"],
            "source_report_digest_recomputed": receipt["source_report_digest_recomputed"],
            "precondition_results": receipt["precondition_results"],
            "postcondition_results": receipt["postcondition_results"],
            "executed_correction_ids": receipt["executed_correction_ids"],
            "skipped_correction_ids": receipt["skipped_correction_ids"],
            "persisted": receipt["persisted"],
            "rollback_performed": receipt["rollback_performed"],
            "output_report_digest": receipt["output_report_digest"],
        },
        "renumbering_map": mapping,
        "identity_renumbering": all(old == new for old, new in mapping) if mapping else None,
        "raw_before": raw_before,
        "raw_after": raw_after,
    }


# --------------------------------------------------------------------------- extraction limitation
def repeated_index_limitation():
    """Documented parser limitation (design §D.C): a repeated-index polygon is NOT live-positive.

    The observation is deliberately an EXTRACTION observation: the mesh is built, extraction is
    attempted through the frozen path, and the canonical parse refusal is recorded verbatim. No
    production file is modified to change this.
    """
    build_scene(verts=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)], faces=[(0, 0, 1)],
                target_slots=TARGET_SLOTS_ASSIGNED, decoy_slots=DECOY_SLOTS)
    raw = raw_snapshot()
    observation = {"raw_before_parse": raw_object(raw, TARGET_OBJECT_ID)}
    try:
        payload = extract_scene(bpy)
        entry = next(o for o in payload["objects"] if o["object_id"] == TARGET_OBJECT_ID)
        observation["payload_faces"] = entry["mesh"]["faces"]
        payload_to_scene_model(payload)
        observation["parse_ok"] = True
        observation["failure_site"] = None
    except Exception as exc:  # noqa: BLE001 - the refusal is the evidence
        frames = traceback.extract_tb(sys.exc_info()[2])
        observation["parse_ok"] = False
        observation["failure_type"] = type(exc).__name__
        observation["failure_message"] = str(exc)
        observation["failure_site"] = (f"{os.path.basename(frames[-1].filename)}:"
                                       f"{frames[-1].lineno} in {frames[-1].name}")
    observation["live_positive_coverage"] = "NOT_APPLICABLE"
    return observation


# --------------------------------------------------------------------------- case table
#: Capability-specific expectations are declared EXPLICITLY per case (no generic
#: findings-preservation abstraction hides them): each W1/W1b case names its mutator mode, any
#: documented plan remap, and the expected executor outcome.
CASES = [
    # ---- W1: the F-1 fixture (§C.1 / §M.7) ----------------------------------------------------
    ("w1-positive-duplicate-final-index", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES,
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1})),
    ("w1-positive-unassigned-slot-raw-only", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES,
        target_slots=TARGET_SLOTS_WITH_UNASSIGNED,
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1})),
    ("w1-positive-object-linked-slot-raw-only", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES,
        target_slots=TARGET_SLOTS_WITH_OBJECT_LINKED,
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1})),
    ("w1-evidence-middle-duplicate-renumbering", dict(
        capability=W1, verts=W1_MID_VERTS, faces=W1_MID_FACES,
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1,
                "note": "fixture-policy violation: the removed duplicate is NOT final, so the "
                        "renumbering map is not the identity; the executor still accepts the "
                        "one-face delta. This case exists so the gate's identity-policy assertion "
                        "is demonstrably discriminating."})),
    # ---- W1 negatives (§J.1) ------------------------------------------------------------------
    ("w1-negative-both-members-removed", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES, mutator_mode="both_members",
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "POSTCONDITION_FAILED",
                "mutations": 1})),
    ("w1-negative-wrong-face-removed", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES, mutator_mode="wrong_face",
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "POSTCONDITION_FAILED",
                "mutations": 1})),
    ("w1-negative-noop-mutator", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES, mutator_mode="noop",
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "POSTCONDITION_FAILED",
                "mutations": 1})),
    ("w1-negative-liar-mutator", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES, mutator_mode="noop", liar=True,
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "POSTCONDITION_FAILED",
                "mutations": 1})),
    ("w1-negative-vertex-mutation", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES, mutator_mode="vertex_shift",
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "POSTCONDITION_FAILED",
                "mutations": 1})),
    ("w1-negative-unrelated-object-mutation", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES, mutator_mode="unrelated_mutation",
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "POSTCONDITION_FAILED",
                "mutations": 1})),
    ("w1-negative-recorded-pair-not-duplicate", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES,
        remap={"face_ids": [0, 1]},
        expect={"result": "PRECONDITION_FAILED", "failure_code": "PRECONDITION_FAILED",
                "mutations": 0})),
    ("w1-negative-digest-first-engine-mutated", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES,
        engine_mutation=lambda: (lambda o: (setattr(o.data.vertices[4].co, "x", 42.0),
                                            o.data.update()))(
            bpy.data.objects.get(TARGET_OBJECT_ID)),
        expect={"result": "SOURCE_MISMATCH", "failure_code": "SOURCE_DIGEST_MISMATCH",
                "mutations": 0})),
    ("w1-negative-wrong-mesh", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES, remap={"mesh_id": "no_such_mesh"},
        expect={"result": "PRECONDITION_FAILED", "failure_code": "PRECONDITION_FAILED",
                "mutations": 0})),
    ("w1-negative-missing-target-object", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES, remap={"object_id": "no_such_object"},
        expect={"result": "PRECONDITION_FAILED", "failure_code": "PRECONDITION_FAILED",
                "mutations": 0})),
    ("w1-negative-malformed-parameters", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES, remap={"extra_parameter": "unexpected_key"},
        expect={"result": "PLAN_INVALID", "failure_code": "UNEXPECTED_PARAMETER:unexpected_key",
                "mutations": 0})),
    ("w1-negative-stale-source-digest", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES, remap={"source_digest": "0" * 64},
        expect={"result": "SOURCE_MISMATCH", "failure_code": "SOURCE_DIGEST_MISMATCH",
                "mutations": 0})),
    ("w1-negative-survivor-pair-altered", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES, mutator_mode="survivor_pair_altered",
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "POSTCONDITION_FAILED",
                "mutations": 1,
                "note": "hostile: the authorized face is removed AND the unrelated winding pair is "
                        "reversed. Reversing a face changes its tuple, so the canonical MULTISET "
                        "delta refuses this class (measured here). The gate's survivor-payload / "
                        "histogram assertions are the redundant defence for it and are "
                        "self-tested in the gate module."})),
    ("w1-evidence-net-multiset-equivalent-mutation", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES, mutator_mode="net_multiset_equivalent",
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1,
                "note": "DOCUMENTED LIMITATION: the canonical postcondition is a MULTISET delta, so "
                        "a mutator that removes BOTH identical members and adds one copy back is "
                        "indistinguishable from the authorized single removal (and the raw face "
                        "table is identical too). The harness counts invocations and compares "
                        "states; it cannot audit mutation internals."})),
    ("w1-evidence-material-slot-destruction", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES, mutator_mode="slot_destruction",
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1,
                "note": "the W1 canonical postcondition has NO material clause, so this completes; "
                        "only gate-side canonical + raw material evidence detects the loss."})),
    ("w1-evidence-datablock-replacement", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES, mutator_mode="datablock_replacement",
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1,
                "note": "SUPERSEDED Pattern A diagnostic: slots are destroyed and the superseded "
                        "datablock is orphaned; caught by raw evidence only."})),
    ("w1-evidence-orphan-inventory-gain", dict(
        capability=W1, verts=W1_VERTS, faces=W1_FACES, mutator_mode="orphan_creation",
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1,
                "note": "raw datablock-inventory gain; the canonical layer has no datablock clause."})),
    # ---- W1b positives (§D.A–§D.B, zero-face, untargeted degeneracy) ---------------------------
    ("w1b-positive-zero-area-collinear", dict(
        capability=W1B, verts=W1B_ZERO_AREA_VERTS, faces=W1B_ZERO_AREA_FACES,
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1})),
    ("w1b-positive-two-vertex-face", dict(
        capability=W1B, verts=W1B_TWO_VERTEX_VERTS, faces=W1B_TWO_VERTEX_FACES,
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1})),
    ("w1b-positive-only-face-zero-face-post-state", dict(
        capability=W1B, verts=W1B_ONLY_FACE_VERTS, faces=W1B_ONLY_FACE_FACES,
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1,
                "note": "Wave 11 touch-point: removing the only face yields the canonical zero-face "
                        "state MeshModel(vertices=..., faces=())"} )),
    ("w1b-evidence-untargeted-degeneracy-remains", dict(
        capability=W1B, verts=W1B_ZERO_AREA_VERTS, faces=W1B_ZERO_AREA_FACES,
        decoy_faces=W1B_DECOY_FACES_WITH_DEGENERATE,
        remap={"keep_only_target": True},
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1,
                "note": "the decoy object keeps its own degenerate finding after the target's is "
                        "cleared: no global degeneracy-clear requirement exists. The plan was "
                        "reduced to the single target correction by the DOCUMENTED remap, because "
                        "the planner's two degenerate proposals would otherwise hit the executor's "
                        "one-correction-per-run rule (covered by the ambiguity case)."})),
    # ---- W1b negatives (§D.D, §J.2) -----------------------------------------------------------
    ("w1b-negative-recorded-face-not-degenerate", dict(
        capability=W1B, verts=W1B_ZERO_AREA_VERTS, faces=W1B_ZERO_AREA_FACES, remap={"face_id": 1},
        expect={"result": "PRECONDITION_FAILED", "failure_code": "PRECONDITION_FAILED",
                "mutations": 0,
                "note": "F-2 same-digest revalidation discriminator: the recorded face EXISTS but "
                        "is no longer degenerate; the plan is the real planner's, only the recorded "
                        "index is remapped."})),
    ("w1b-negative-digest-first-engine-mutated", dict(
        capability=W1B, verts=W1B_ZERO_AREA_VERTS, faces=W1B_ZERO_AREA_FACES,
        engine_mutation=lambda: (lambda o: (setattr(o.data.vertices[2].co, "y", 3.0),
                                            o.data.update()))(
            bpy.data.objects.get(TARGET_OBJECT_ID)),
        expect={"result": "SOURCE_MISMATCH", "failure_code": "SOURCE_DIGEST_MISMATCH",
                "mutations": 0})),
    ("w1b-negative-wrong-face-removed", dict(
        capability=W1B, verts=W1B_ZERO_AREA_VERTS, faces=W1B_ZERO_AREA_FACES,
        mutator_mode="wrong_face",
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "POSTCONDITION_FAILED",
                "mutations": 1})),
    ("w1b-negative-noop-mutator", dict(
        capability=W1B, verts=W1B_ZERO_AREA_VERTS, faces=W1B_ZERO_AREA_FACES, mutator_mode="noop",
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "POSTCONDITION_FAILED",
                "mutations": 1})),
    ("w1b-negative-liar-mutator", dict(
        capability=W1B, verts=W1B_ZERO_AREA_VERTS, faces=W1B_ZERO_AREA_FACES, mutator_mode="noop",
        liar=True,
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "POSTCONDITION_FAILED",
                "mutations": 1})),
    ("w1b-negative-vertex-mutation", dict(
        capability=W1B, verts=W1B_ZERO_AREA_VERTS, faces=W1B_ZERO_AREA_FACES,
        mutator_mode="vertex_shift",
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "POSTCONDITION_FAILED",
                "mutations": 1})),
    ("w1b-negative-unrelated-object-mutation", dict(
        capability=W1B, verts=W1B_ZERO_AREA_VERTS, faces=W1B_ZERO_AREA_FACES,
        mutator_mode="unrelated_mutation",
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "POSTCONDITION_FAILED",
                "mutations": 1})),
    ("w1b-negative-ambiguous-multiple-degenerate-faces", dict(
        capability=W1B, verts=W1B_TWO_DEGENERATE_VERTS, faces=W1B_TWO_DEGENERATE_FACES,
        expect={"result": "PLAN_INVALID",
                "failure_code": "AMBIGUOUS_MULTIPLE_EXECUTABLE_CORRECTIONS", "mutations": 0,
                "note": "one correction per execution: two executable W1b corrections are refused "
                        "before any engine contact"})),
    ("w1b-negative-wrong-mesh", dict(
        capability=W1B, verts=W1B_ZERO_AREA_VERTS, faces=W1B_ZERO_AREA_FACES,
        remap={"mesh_id": "no_such_mesh"},
        expect={"result": "PRECONDITION_FAILED", "failure_code": "PRECONDITION_FAILED",
                "mutations": 0})),
    ("w1b-negative-malformed-parameters", dict(
        capability=W1B, verts=W1B_ZERO_AREA_VERTS, faces=W1B_ZERO_AREA_FACES,
        remap={"extra_parameter": "unexpected_key"},
        expect={"result": "PLAN_INVALID", "failure_code": "UNEXPECTED_PARAMETER:unexpected_key",
                "mutations": 0})),
    ("w1b-negative-stale-source-digest", dict(
        capability=W1B, verts=W1B_ZERO_AREA_VERTS, faces=W1B_ZERO_AREA_FACES,
        remap={"source_digest": "0" * 64},
        expect={"result": "SOURCE_MISMATCH", "failure_code": "SOURCE_DIGEST_MISMATCH",
                "mutations": 0})),
    ("w1b-evidence-material-slot-destruction", dict(
        capability=W1B, verts=W1B_ZERO_AREA_VERTS, faces=W1B_ZERO_AREA_FACES,
        mutator_mode="slot_destruction",
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1,
                "note": "no material clause exists on this path; only gate-side canonical + raw "
                        "material evidence detects the loss"})),
]


def save_attempt_probe():
    """A real SAVE ATTEMPT that cannot create a file, with sandboxed evidence (design §H.1/§J).

    ``bpy.data.filepath`` is empty for every disposable scene, so Blender has no path to write and
    refuses the save. The attempt is additionally made from a fresh TEMP directory, so even a
    pathological write could not touch the repository; the directory is inspected afterwards and must
    be empty. Nothing is claimed beyond what is measured here.
    """
    import tempfile

    original_cwd = os.getcwd()
    sandbox = tempfile.mkdtemp(prefix="atlas_w1_w1b_save_probe_")
    probe = {"filepath_before": bpy.data.filepath, "sandbox": sandbox,
             "cwd_before": original_cwd}
    os.chdir(sandbox)
    try:
        try:
            bpy.ops.wm.save_mainfile()
            probe["error_type"] = None
            probe["error_message"] = None
            probe["refused"] = False
        except Exception as exc:  # noqa: BLE001 - the refusal is the evidence
            probe["error_type"] = type(exc).__name__
            probe["error_message"] = str(exc)
            probe["refused"] = True
        probe["files_created_in_sandbox"] = sorted(os.listdir(sandbox))
        probe["filepath_after"] = bpy.data.filepath
    finally:
        os.chdir(original_cwd)
        try:
            os.rmdir(sandbox)
            probe["sandbox_removed"] = True
        except OSError:
            probe["sandbox_removed"] = False
    return probe


def main():
    results = {"environment": {
        "blender_version": bpy.app.version_string,
        "build_hash": bpy.app.build_hash.decode() if isinstance(bpy.app.build_hash, bytes)
        else str(bpy.app.build_hash),
        "build_date": bpy.app.build_commit_date.decode()
        if isinstance(bpy.app.build_commit_date, bytes) else str(bpy.app.build_commit_date),
        "filepath_at_start": bpy.data.filepath,
        "target_contract": {"target_object_id": TARGET_OBJECT_ID,
                            "target_mesh_id": TARGET_MESH_ID,
                            "decoy_object_id": DECOY_OBJECT_ID,
                            "decoy_sorts_before_target": DECOY_OBJECT_ID < TARGET_OBJECT_ID},
        "w2_not_implemented": True,
    }, "cases": [], "errors": []}

    asset = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), FROZEN_ASSET)
    if os.path.isfile(asset):
        with open(asset, "rb") as handle:
            results["environment"]["frozen_asset_sha256"] = hashlib.sha256(handle.read()).hexdigest()

    for label, kwargs in CASES:
        try:
            results["cases"].append(run_case(label, **dict(kwargs)))
        except Exception:  # noqa: BLE001 - record, never abort the whole run
            results["errors"].append({"case": label, "traceback": traceback.format_exc()[-3000:]})

    try:
        results["repeated_index_limitation"] = repeated_index_limitation()
    except Exception:  # noqa: BLE001
        results["errors"].append({"case": "repeated-index-limitation",
                                  "traceback": traceback.format_exc()[-3000:]})

    try:
        results["save_attempt"] = save_attempt_probe()
    except Exception:  # noqa: BLE001
        results["errors"].append({"case": "save-attempt-probe",
                                  "traceback": traceback.format_exc()[-3000:]})

    # the disposable Blender process is discarded; nothing was written
    results["session"] = {
        "filepath_at_end": bpy.data.filepath,
        "is_dirty": bool(bpy.data.is_dirty),
        "saved_anything": False,
    }
    print("ATLAS_W1_W1B_LIVE_START")
    print(json.dumps(results))
    print("ATLAS_W1_W1B_LIVE_END")


if __name__ == "__main__":
    main()
