"""LIVE Blender driver for the REPAIR_MERGE_VERTEX gate (run INSIDE Blender, never in CI).

Executed by ``tests/test_live_blender_merge_vertex_gate.py`` via::

    blender --background --python tests/merge_vertex_live_script.py

It builds DISPOSABLE in-memory scenes (nothing is saved, no .blend is opened, the frozen
validation asset is never touched), runs the complete live path

    live Blender scene -> bpy_extraction.extract_scene -> payload_to_scene_model
    -> run_scene_health -> CorrectionPlan -> authorization artifact -> execute_merge_vertex
    -> REAL Blender mutation -> fresh extraction -> MQ-1..MQ-7 -> receipt

and prints one JSON evidence block between the markers ``ATLAS_MERGE_LIVE_START`` /
``ATLAS_MERGE_LIVE_END``.

Boundary: the mutation primitive is implemented HERE (in the live driver), exactly as the
Wave-2 live gate did — no second planning-layer adapter is invented, and the executor keeps
importing no bpy. No persistence, no save, no rollback, no cleanup, no retry.

WAVE 14 — REPRESENTATION FIDELITY (material slots)
    SUPERSEDED: this driver previously called the datablock-REPLACEMENT pattern
    (``bpy.data.meshes.new(...)`` + ``from_pydata(...)`` + ``obj.data = new_mesh``, "Pattern A") the
    normative primitive. It is no longer normative: it truncates the target object's slot table to
    the new datablock's table, so assigned, unassigned and OBJECT-linked material slots alike are
    destroyed, and it leaves the superseded datablock orphaned. The normative reference pattern is
    now the SAME-DATABLOCK table rebuild ("Pattern B", ``LiveMutator`` below):
        mesh.clear_geometry(); mesh.from_pydata(vertices, [], faces); mesh.update()
    Pattern A survives here ONLY as ``LossyPatternAMutator``, a deliberately lossy diagnostic used by
    the RED case, which must FAIL through raw material-slot evidence and/or the existing MQ-5
    canonical postcondition. Authority, receipt schema and the MQ-1..MQ-7 vocabulary are unchanged.
    See planning/blender/BLENDER_WAVE14_CORRECTION_REPRESENTATION_FIDELITY_DESIGN.md §5.
"""

import hashlib
import json
import os
import sys
import traceback

# Blender's embedded Python does NOT honour the shell PYTHONPATH (Blender 4.4.3), so the repo root
# is put on sys.path explicitly here. This adds an import path ONLY — no contract, no authority.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import bpy

from planning.blender.bpy_extraction import extract_scene
from planning.blender.correction_authorization import (
    AUTHORIZATION_VERSION,
    make_index_mapping,
    mapping_digest,
    parse_authorization,
    require_supported_case,
)
from planning.blender.correction_contract import CorrectionPlan, CorrectionProposal
from planning.blender.correction_executor import ExecutionOutcome, execute_merge_vertex
from planning.blender.correction_planner import (
    _correction_id,
    plan_merge_vertex_correction,
)
from planning.blender.correction_values import thaw_jsonable
from planning.blender.extraction_payload import payload_to_scene_model
from planning.blender.finding_codes import FindingCode, severity_of
from planning.blender.kernel import run_scene_health, soccer_field_profile_default
from planning.blender.mesh_health import check_mesh
from planning.blender.scene_report import REPORT_FORMAT_VERSION

MERGE = "REPAIR_MERGE_VERTEX"
DV = FindingCode.MESH_DUPLICATE_VERTEX.value
PROFILE = {"name": "soccer-field", "version": "1"}
FROZEN_ASSET = os.path.join("tests", "assets", "blender", "atlas_transform_validation.blend")
WINDING = "MESH_WINDING_INCONSISTENT"

#: Every fixture in this driver links the duplicate-bearing target mesh as the object named "pitch"
#: (``build_scene``) and the untouched control mesh as "goal". The target must be selected BY
#: IDENTITY, never by position: ``extract_scene`` emits objects in name-sorted order, so "the first
#: object with a mesh" is now the unrelated "goal" mesh - which silently retargeted every synthetic
#: case onto a mesh with no duplicate-vertex findings (Wave 13 live-gate finding).
TARGET_OBJECT_ID = "pitch"

#: WAVE 14 material-slot fixtures (in-memory only; no material datablock is ever saved). Order is the
#: slot order, names are distinct and non-sortable-by-accident, and each spec pins the producer §4.3
#: branch it exercises: all-DATA-assigned (canonical names), unassigned (key OMITTED), OBJECT-linked
#: (key OMITTED). See BLENDER_WAVE14_CORRECTION_REPRESENTATION_FIDELITY_DESIGN.md §3.1.
MATERIAL_SLOTS_ASSIGNED = (("DATA", "turf"), ("DATA", "line_markings"), ("DATA", "goal_net"))
MATERIAL_SLOTS_UNASSIGNED = (("DATA", "turf"), ("DATA", None), ("DATA", "goal_net"))
MATERIAL_SLOTS_OBJECT_LINKED = (("DATA", "turf"), ("OBJECT", "line_markings"))
MATERIAL_SLOTS_UNRELATED = (("DATA", "banner"),)


def mutator_for(bpy, primitive, **kwargs):
    """Select the live mutation primitive by NAME (never by fallback).

    ``pattern_b`` (default) is the normative same-datablock reference primitive; ``pattern_a`` is the
    SUPERSEDED, deliberately lossy diagnostic used only by the RED case.
    """
    if primitive == "pattern_b":
        return LiveMutator(bpy, **kwargs)
    if primitive == "pattern_a":
        return LossyPatternAMutator(bpy, **kwargs)
    raise RuntimeError(f"unknown live mutation primitive: {primitive!r}")


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


class LiveMutator:
    """The NORMATIVE reference primitive (Wave 14 Pattern B), implemented against real Blender.

    Rebuild the target object's mesh TABLES IN PLACE on the SAME datablock from the DERIVED tables
    and touch nothing else. Because the datablock is never replaced, the object's material-slot
    table (assigned, unassigned and OBJECT-linked slots alike) and the mesh-datablock inventory are
    left untouched, which is what the existing MQ-5/MQ-6 postconditions require. Invocations are
    counted so the receipt-level claim can be checked against the real engine contact.

    WAVE 14 SUPERSESSION: this class previously performed a datablock REPLACEMENT
    (``bpy.data.meshes.new`` + ``from_pydata`` + ``obj.data = new_mesh``). That pattern is retained
    in this driver only as ``LossyPatternAMutator`` (diagnostic RED evidence), never as the
    normative primitive. See BLENDER_WAVE14_CORRECTION_REPRESENTATION_FIDELITY_DESIGN.md §5.
    """

    primitive = "pattern_b_same_datablock"

    def __init__(self, bpy_module, *, drop_last_face=False, shift_coord=False, liar=False):
        self.bpy = bpy_module
        self.calls = []
        self.drop_last_face = drop_last_face
        self.shift_coord = shift_coord
        self.liar = liar

    def __call__(self, engine_state, *, object_id, mesh_id, vertices, faces, old_to_new_mapping):
        self.calls.append({"object_id": object_id, "mesh_id": mesh_id,
                           "vertex_count": len(vertices), "face_count": len(faces)})
        bpy = engine_state.bpy if hasattr(engine_state, "bpy") else engine_state
        obj = bpy.data.objects.get(object_id)
        if obj is None:
            raise RuntimeError(f"live target object {object_id!r} does not exist")
        verts = [tuple(float(c) for c in v) for v in vertices]
        face_tuples = [tuple(int(i) for i in f) for f in faces]
        if self.shift_coord:
            verts[0] = (verts[0][0] + 1.0, verts[0][1], verts[0][2])
        if self.drop_last_face:
            face_tuples = face_tuples[:-1]
        # Pattern B: same datablock, tables rebuilt in place.
        obj.data.clear_geometry()
        obj.data.from_pydata(verts, [], face_tuples)
        obj.data.update()
        if self.liar:
            return {"ok": True, "result": "COMPLETED"}
        return None


class LossyPatternAMutator(LiveMutator):
    """DIAGNOSTIC RED primitive (superseded Pattern A) — deliberately lossy, never normative.

    Builds a NEW mesh datablock and assigns it (``obj.data = new_mesh``). This truncates the
    object's material-slot table to the new datablock's (empty) table and orphans the superseded
    datablock, so a material-bearing target loses every slot at the real Blender boundary. It exists
    only so the live gate can prove it DETECTS material-slot loss (raw slot evidence and/or the
    existing MQ-5 canonical postcondition). It must never be described as the reference primitive.
    """

    primitive = "pattern_a_datablock_replacement"

    def __call__(self, engine_state, *, object_id, mesh_id, vertices, faces, old_to_new_mapping):
        self.calls.append({"object_id": object_id, "mesh_id": mesh_id,
                           "vertex_count": len(vertices), "face_count": len(faces)})
        bpy = engine_state.bpy if hasattr(engine_state, "bpy") else engine_state
        obj = bpy.data.objects.get(object_id)
        if obj is None:
            raise RuntimeError(f"live target object {object_id!r} does not exist")
        verts = [tuple(float(c) for c in v) for v in vertices]
        face_tuples = [tuple(int(i) for i in f) for f in faces]
        if self.shift_coord:
            verts[0] = (verts[0][0] + 1.0, verts[0][1], verts[0][2])
        if self.drop_last_face:
            face_tuples = face_tuples[:-1]
        new_mesh = bpy.data.meshes.new(obj.data.name)
        new_mesh.from_pydata(verts, [], face_tuples)
        new_mesh.update()
        obj.data = new_mesh
        if self.liar:
            return {"ok": True, "result": "COMPLETED"}
        return None


def material_slot_table(obj):
    """The RAW Blender slot table: ordered ``[link, material name or None]`` pairs.

    Wave 14: this is the authoritative raw evidence for the properties the canonical model cannot
    express (unassigned slots, OBJECT-linked slots, slot-order identity). It replaces nothing — the
    canonical comparison keeps its own meaning — and it is never read as canonical state.
    """
    return [[str(getattr(slot, "link", None)),
             (slot.material.name if getattr(slot, "material", None) is not None else None)]
            for slot in obj.material_slots]


def slot_material(bpy, name):
    """Fetch-or-create one material datablock by name (in-memory fixtures only)."""
    if name is None:
        return None
    existing = bpy.data.materials.get(name)
    return existing if existing is not None else bpy.data.materials.new(name)


def apply_material_slots(bpy, obj, spec):
    """Build the object's material-slot table in the given order from a slot spec.

    ``spec`` entries are ``("DATA", name)`` (a data-linked slot), ``("DATA", None)`` (an UNASSIGNED
    data-linked slot) or ``("OBJECT", name)`` (an OBJECT-linked slot). Slot order is the spec order,
    so the fixture's ordering evidence is order-sensitive by construction.
    """
    for index, (link, name) in enumerate(spec):
        obj.data.materials.append(slot_material(bpy, name))
        if link == "OBJECT":
            obj.material_slots[index].link = "OBJECT"
            obj.material_slots[index].material = slot_material(bpy, name)
    return material_slot_table(obj)


def materials_view(payload, scene, object_id):
    """Canonical + payload-level material evidence for one object (Wave 14).

    ``key_present`` / ``payload_value`` show what the FROZEN producer emitted (a key that is omitted
    is different payload state from ``[]``), ``canonical`` is what the canonical model can compare,
    and ``representation_state`` is the payload-level representation fact that the canonical model
    cannot see. Nothing here is read as authority.
    """
    from planning.blender.extraction_payload import payload_representation_state
    entry = next((o for o in payload["objects"] if o["object_id"] == object_id), None)
    mesh = (entry or {}).get("mesh") or {}
    target = next((o for o in scene.objects if o.object_id == object_id and o.mesh is not None), None)
    return {
        "key_present": "materials" in mesh,
        "payload_value": mesh.get("materials"),
        "canonical": list(target.mesh.materials) if target is not None else None,
        "representation_state": list(payload_representation_state(payload)),
    }


def raw_scene_snapshot(bpy):
    """An INDEPENDENT raw-Blender snapshot (outside the extraction model), for pre/post proof."""
    objects = []
    for obj in sorted(bpy.data.objects, key=lambda o: o.name):
        data = getattr(obj, "data", None)
        entry = {
            "name": obj.name,
            "type": obj.type,
            "data_block": getattr(data, "name", None),
            "location": [round(float(a), 9) for a in obj.location],
            "rotation_euler": [round(float(a), 9) for a in obj.rotation_euler],
            "scale": [round(float(a), 9) for a in obj.scale],
            "parent": getattr(obj.parent, "name", None),
            "collections": sorted(c.name for c in obj.users_collection),
            "vertex_count": len(data.vertices) if obj.type == "MESH" and data else None,
            "face_count": len(data.polygons) if obj.type == "MESH" and data else None,
            "vertices": ([round(float(a), 6) for a in v.co] for v in data.vertices)
                        if obj.type == "MESH" and data else None,
            "faces": [list(p.vertices) for p in data.polygons]
                     if obj.type == "MESH" and data else None,
            # WAVE 14: the authoritative raw slot table is link-aware (a data-slot-name list
            # cannot see OBJECT-linked slots and cannot distinguish an unassigned slot).
            "material_slots": material_slot_table(obj)
                              if obj.type == "MESH" and data else None,
            "material_data_slots": [m.name if m else None for m in obj.data.materials]
                              if obj.type == "MESH" and data else None,
            "custom_keys": sorted(dict(obj.items()).keys()),
        }
        if entry["vertices"] is not None:
            entry["vertices"] = [list(v) for v in entry["vertices"]]
        objects.append(entry)
    return {
        "object_count": len(bpy.data.objects),
        "objects": objects,
        "objects_total": len(bpy.data.objects),
        "mesh_datablocks": sorted(m.name for m in bpy.data.meshes),
        "collections": sorted(c.name for c in bpy.data.collections),
        "filepath": bpy.data.filepath,
        "is_dirty": bool(bpy.data.is_dirty),
    }


# --------------------------------------------------------------------------- fixtures
def reset_scene(bpy):
    """Disposable in-memory scene: remove everything, keep the master scene collection."""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    return bpy.context.scene


def build_scene(bpy, *, verts, faces, unrelated=True, goals_collection=True,
                signed_zero_coords=None, target_slots=None, unrelated_slots=None):
    """One target mesh object + (optionally) one unrelated mesh object and one unrelated empty.

    Wave 14: ``target_slots`` / ``unrelated_slots`` build real material-slot tables (see
    ``apply_material_slots``) so the target's canonical material tuple can be NON-EMPTY and the raw
    slot table can be asserted. ``reset_scene`` removes every mesh datablock first, so a fixture can
    never inherit a datablock (or an orphan) from the previous case.
    """
    scene = reset_scene(bpy)
    mesh = bpy.data.meshes.new("pitch")
    mesh.from_pydata([tuple(float(c) for c in v) for v in verts], [], [tuple(int(i) for i in f)
                                                                       for f in faces])
    mesh.update()
    target = bpy.data.objects.new("pitch", mesh)
    scene.collection.objects.link(target)
    if target_slots:
        apply_material_slots(bpy, target, target_slots)

    if unrelated:
        goals = bpy.data.collections.new("Goals")
        scene.collection.children.link(goals)
        gmesh = bpy.data.meshes.new("goal")
        gmesh.from_pydata([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)], [],
                          [(0, 1, 2)])
        gmesh.update()
        goal = bpy.data.objects.new("goal", gmesh)
        if unrelated_slots:
            apply_material_slots(bpy, goal, unrelated_slots)
        goal.location = (5.0, 0.0, 0.0)
        goal.rotation_euler = (0.0, 0.0, 0.0)
        if goals_collection:
            goals.objects.link(goal)
        else:
            scene.collection.objects.link(goal)
        marker = bpy.data.objects.new("marker", None)
        marker.location = (-2.0, 0.0, 0.0)
        scene.collection.objects.link(marker)
    return scene, target


# --------------------------------------------------------------------------- fixtures/cases
B1_VERTS = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (7.0, 0.0, 0.0),
            (3.0, 3.0, 0.0), (3.0, 3.0, 0.0), (4.0, 0.0, 5.0)]
B1_FACES = [(0, 2, 3), (5, 2, 3)]

TAIL_VERTS = [(0.0, 0.0, 0.0), (3.0, 0.0, 0.0), (0.0, 3.0, 0.0), (1.0, 1.0, 0.0),
              (0.0, 0.0, 0.0)]
TAIL_FACES = [(0, 1, 2)]

TRANSITIVE_VERTS = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0),
                    (4.0, 0.0, 0.0), (1.0, 1.0, 0.0), (1.0, -1.0, 0.0)]
TRANSITIVE_FACES = [(0, 3, 4), (0, 3, 5)]

#: genuinely CREATES a winding class -> must refuse BEFORE mutation (topology hazard)
CREATES_VERTS = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (5.0, 0.0, 0.0),
                 (2.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 3.0, 0.0)]
CREATES_FACES = [(1, 3, 4), (0, 3, 5)]

#: bit-different (signed zero) but rounded-key-equal pair: the ONLY sub-grid shape the live
#: extraction can produce, because the adapter rounds coordinates to 6 dp.
SZERO_VERTS = [(0.0, 0.0, 0.0), (-0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (0.0, 5.0, 0.0)]
SZERO_FACES = [(0, 2, 3)]

#: MIDDLE-TABLE duplicate (Wave 13): the removed member (2) is NOT a suffix of the vertex table - PRE
#: vertex 3 survives after it, so the surviving PRE-state subsequence is [0, 1, 3] and
#: set(old_to_new_mapping) == [0, 1, 2] is NOT the kept set. The pre-fix planner indexed the PRE-state
#: table with that post-index range, predicted a post-state that still contained the duplicate, and
#: refused with PARTIAL_GROUP_COVERAGE - which is why no middle-table case could ever reach the real
#: planner. The expected mapping is [0, 1, 0, 2] with group [[0, 2]] and survivor [0].
MIDDLE_VERTS = [(0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 5.0, 0.0)]
MIDDLE_FACES = [(0, 1, 3)]


def derive_merge_parameters(scene, report, mesh_id):
    """Plan parameters derived from the FRESH live evidence (design §4), executor-independent.

    This is the driver's OWN derivation of the same facts, kept as an INDEPENDENT witness: the gate
    asserts the receipt's groups/survivors/mapping against these values, and the hostile cases build a
    contract-valid plan from them that is then mutated (``mutate_params``) — a path that must bypass the
    planner on purpose. Historical note: this synthetic path was also the only way to drive mid-table
    shapes while the retired planner kept set was the POST index range; Wave 13 replaced that with the
    PRE-state survivor subsequence, so every positive case now takes its plan from the real planner.
    """
    mesh = next(o.mesh for o in scene.objects if o.mesh is not None and o.mesh.mesh_id == mesh_id)
    table = mesh.vertices
    n = len(table)
    pairs = set()
    for finding in report.findings:
        if finding.code.value != DV or finding.mesh_id != mesh_id:
            continue
        a, b = finding.measured["vertex_a"], finding.measured["vertex_b"]
        pairs.add((min(a, b), max(a, b)))
    pairs = sorted(pairs)
    comps = []
    for a, b in pairs:
        hit = [c for c in comps if a in c or b in c]
        if not hit:
            comps.append({a, b})
            continue
        merged = {a, b}
        for c in hit:
            merged |= c
            comps.remove(c)
        comps.append(merged)
    groups = tuple(sorted(tuple(sorted(c)) for c in comps if len(c) >= 2))
    survivors = tuple(sorted(min(g) for g in groups))
    sig = {}
    for g in groups:
        for m in g:
            sig[m] = min(g)
    kept = tuple(sorted({sig.get(i, i) for i in range(n)}))
    rho = {s: k for k, s in enumerate(kept)}
    mapping = tuple(rho[sig.get(i, i)] for i in range(n))
    cases = require_supported_case(table, groups) if groups else ()
    return {
        "mesh_id": mesh_id,
        "recorded_pairs": [list(p) for p in pairs],
        "duplicate_groups": [list(g) for g in groups],
        "survivor_indices": list(survivors),
        "old_to_new_mapping": list(mapping),
        "mapping_digest": mapping_digest(mesh_id, n, mapping),
        "all_groups_exact": bool(cases) and all(c == "EXACT" for c in cases),
        "predicted_topology_unchanged": True,
    }, {"groups": [list(g) for g in groups], "kept": list(kept),
        "survivors": list(survivors), "mapping": list(mapping),
        "cases": list(cases), "n": n}


def report_dict(report):
    payload = report.to_json_compatible()
    payload["digest"] = report.digest()
    payload["report_format_version"] = REPORT_FORMAT_VERSION
    return payload


def scene_input_dict(scene):
    """The SCENE-INPUT grammar for the real planner (no extraction-only schema_version field)."""
    payload = extract_scene(bpy)
    payload.pop("schema_version", None)
    return payload


def synthetic_plan(scene, parameters, *, object_id="pitch", mesh_id="pitch"):
    digest = run_scene_health(scene, soccer_field_profile_default()).digest()
    proposal = CorrectionProposal(
        correction_id=_correction_id(FindingCode.MESH_DUPLICATE_VERTEX, object_id, mesh_id,
                                     parameters),
        finding_code=DV, object_id=object_id, mesh_id=mesh_id, correction_type=MERGE,
        parameters=parameters, rationale="live merge authorization (contract-built plan)",
        preconditions=({"source_report_digest": digest}, {"finding_code": DV},
                       {"affected_entity": {"object_id": object_id, "mesh_id": mesh_id}}),
        expected_postcondition={"finding_cleared": DV, "unrelated_topology_unchanged": True},
        risk="FIDELITY_GEOMETRY", severity=severity_of(FindingCode.MESH_DUPLICATE_VERTEX).value,
        reversibility="partially_reversible", dependencies=(), determinism="DETERMINISTIC",
        requires_human_review=True, out_of_scope=False)
    plan = CorrectionPlan(plan_id="", source_report_digest=digest, source_revision_id=None,
                          planner_version="1", profile={"name": "soccer-field", "version": "1"},
                          corrections=(proposal,), dependencies=(), summary_metrics={},
                          state="REVIEW_REQUIRED", planning_errors=())
    return plan, proposal


def artifact(plan, correction, **overrides):
    art = {
        "authorization_version": AUTHORIZATION_VERSION,
        "authorization_policy_version": "1",
        "decision": "APPROVED",
        "correction_type": correction.correction_type,
        "correction_id": correction.correction_id,
        "plan_id": plan.plan_id,
        "source_report_digest": plan.source_report_digest,
        "authorized_by": "operator",
        "authorized_at_utc": "2026-09-13T12:00:00Z",
    }
    art.update(overrides)
    return art


def measured_payloads(report, mesh_id, code):
    return [f.measured for f in report.findings
            if f.code.value == code and f.mesh_id == mesh_id]


def receipt_view(receipt):
    return {
        "result": receipt["result"],
        "failure_code": receipt["failure_code"],
        "field_count": len(receipt),
        "precondition_results": receipt["precondition_results"],
        "postcondition_results": receipt["postcondition_results"],
        "duplicate_groups": receipt["duplicate_groups"],
        "survivor_indices": receipt["survivor_indices"],
        "removed_vertex_indices": receipt["removed_vertex_indices"],
        "old_to_new_mapping": receipt["old_to_new_mapping"],
        "old_to_new_mapping_digest": receipt["old_to_new_mapping_digest"],
        "changed_face_indices": receipt["changed_face_indices"],
        "pre_vertex_count": receipt["pre_vertex_count"],
        "post_vertex_count": receipt["post_vertex_count"],
        "executed_correction_ids": receipt["executed_correction_ids"],
        "authorization_verified": receipt["authorization_verified"],
        "authorization_digest": receipt["authorization_digest"],
        "source_report_digest_recomputed": receipt["source_report_digest_recomputed"],
        "output_report_digest": receipt["output_report_digest"],
        "plan_id": receipt["plan_id"],
        "plan_id_recomputed": receipt["plan_id_recomputed"],
        "vertex_merge_only": receipt["vertex_merge_only"],
        "index_renumbering_only": receipt["index_renumbering_only"],
        "geometry_unverifiable": receipt["geometry_unverifiable"],
        "normal_agreement_not_verified": receipt["normal_agreement_not_verified"],
        "persisted": receipt["persisted"],
        "rollback_performed": receipt["rollback_performed"],
        "pre_winding_findings": receipt["pre_winding_findings"],
        "post_winding_findings": receipt["post_winding_findings"],
        "pre_duplicate_vertex_findings": receipt["pre_duplicate_vertex_findings"],
        "post_duplicate_vertex_findings": receipt["post_duplicate_vertex_findings"],
        "target_object_mesh": receipt["target_object_mesh"],
    }


def run_case(label, verts, faces, *, mode="synthetic", authorization=None,
             mutate_params=None, mutator_kwargs=None, unrelated=True, goals_collection=True,
             planner=True, primitive="pattern_b", target_slots=None, unrelated_slots=None):
    """Build the disposable scene, run the whole live path, capture raw + receipt evidence."""
    build_scene(bpy, verts=verts, faces=faces, unrelated=unrelated,
                goals_collection=goals_collection, target_slots=target_slots,
                unrelated_slots=unrelated_slots)
    engine = LiveEngine(bpy)
    pre_payload = extract_scene(bpy)
    pre_scene, pre_report = live_extractor(engine)
    target_object = next((o for o in pre_scene.objects
                          if o.object_id == TARGET_OBJECT_ID and o.mesh is not None), None)
    if target_object is None:
        raise RuntimeError(
            f"live fixture target object {TARGET_OBJECT_ID!r} is missing from the extracted scene; "
            "this driver never falls back to another object")
    target = target_object.mesh
    params, derived = derive_merge_parameters(pre_scene, pre_report, target.mesh_id)

    planner_out = None
    if mode == "real_planner":
        out = plan_merge_vertex_correction(report_dict(pre_report), scene_input_dict(pre_scene),
                                          profile=PROFILE)
        corrections = [c for c in out.plan.corrections if c.correction_type == MERGE]
        planner_out = {"state": out.plan.state, "merge_corrections": len(corrections),
                       "correction_ids": [c.correction_id for c in corrections],
                       # the REAL planner's own emitted parameters: the Wave 13 middle-table case must
                       # prove the planner's predicted kept-set, not only the executor's re-derivation.
                       "parameters": [dict(c.parameters) for c in corrections]}
        if not corrections:
            raise RuntimeError("real planner emitted no merge correction for a positive case")
        plan, correction = out.plan, corrections[0]
    else:
        plan, correction = synthetic_plan(pre_scene, params)

    if mutate_params is not None:
        mutate_params(params, plan)
        if mode != "real_planner":
            plan, correction = synthetic_plan(pre_scene, params)

    mutator = mutator_for(bpy, primitive, **(mutator_kwargs or {}))
    raw_before = raw_scene_snapshot(bpy)
    auth = authorization
    if auth == "AUTO":
        auth = artifact(plan, correction)
    receipt = execute_merge_vertex(engine_state=engine, plan=plan, authorization=auth,
                                   mutator=mutator, extractor=live_extractor)
    raw_after = raw_scene_snapshot(bpy)
    post_payload = None
    try:
        post_payload = extract_scene(bpy)
        post_scene, post_report = live_extractor(engine)
        post_error = None
    except Exception as exc:  # noqa: BLE001 - a destroyed post-state is itself evidence
        post_scene, post_report, post_error = None, None, f"{type(exc).__name__}: {exc}"

    target_after = None
    if post_scene is not None:
        for obj in post_scene.objects:
            if obj.mesh is not None and obj.object_id == target_object.object_id:
                target_after = obj.mesh
    return {
        "case": label,
        "mode": mode,
        "primitive": mutator.primitive,
        "planner": planner_out,
        "fixture": {"vertices": [list(v) for v in verts], "faces": [list(f) for f in faces]},
        "derived": derived,
        "parameters": params,
        "target": {"object_id": target_object.object_id, "mesh_id": target.mesh_id},
        "pre": {
            "digest": pre_report.digest(),
            "vertex_count": len(target.vertices),
            "faces": [list(f) for f in target.faces],
            "duplicate_vertex": measured_payloads(pre_report, target.mesh_id, DV),
            "winding": measured_payloads(pre_report, target.mesh_id, WINDING),
            "non_manifold": measured_payloads(pre_report, target.mesh_id,
                                              "MESH_NON_MANIFOLD_EDGE"),
            "duplicate_face": measured_payloads(pre_report, target.mesh_id,
                                                "MESH_DUPLICATE_FACE"),
            "degenerate_face": measured_payloads(pre_report, target.mesh_id,
                                                 "MESH_DEGENERATE_FACE"),
            # WAVE 14 representation evidence: what the frozen producer emitted, what the canonical
            # model can compare, and the payload-level representation fact it cannot see.
            "materials": materials_view(pre_payload, pre_scene, target_object.object_id),
            "unrelated_materials": materials_view(pre_payload, pre_scene, "goal"),
        },
        "post": None if target_after is None else {
            "digest": post_report.digest(),
            "vertex_count": len(target_after.vertices),
            "vertices": [list(v) for v in target_after.vertices],
            "faces": [list(f) for f in target_after.faces],
            "duplicate_vertex": measured_payloads(post_report, target.mesh_id, DV),
            "winding": measured_payloads(post_report, target.mesh_id, WINDING),
            "non_manifold": measured_payloads(post_report, target.mesh_id,
                                              "MESH_NON_MANIFOLD_EDGE"),
            "duplicate_face": measured_payloads(post_report, target.mesh_id,
                                                "MESH_DUPLICATE_FACE"),
            "degenerate_face": measured_payloads(post_report, target.mesh_id,
                                                 "MESH_DEGENERATE_FACE"),
            "materials": (None if post_payload is None or post_scene is None
                          else materials_view(post_payload, post_scene, target_object.object_id)),
            "unrelated_materials": (None if post_payload is None or post_scene is None
                                    else materials_view(post_payload, post_scene, "goal")),
        },
        "post_extraction_error": post_error,
        "mutator_invocations": len(mutator.calls),
        "mutator_calls": mutator.calls,
        "receipt": receipt_view(receipt),
        "raw_before": raw_before,
        "raw_after": raw_after,
    }


def main():
    results = {"environment": {
        "blender_version": bpy.app.version_string,
        "build_hash": bpy.app.build_hash.decode() if isinstance(bpy.app.build_hash, bytes)
                      else str(bpy.app.build_hash),
        "build_date": bpy.app.build_commit_date.decode()
                      if isinstance(bpy.app.build_commit_date, bytes)
                      else str(bpy.app.build_commit_date),
        "build_time": bpy.app.build_time.decode() if isinstance(bpy.app.build_time, bytes)
                      else str(bpy.app.build_time),
        "filepath_at_start": bpy.data.filepath,
    }, "cases": [], "errors": []}

    asset = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         FROZEN_ASSET)
    if os.path.isfile(asset):
        with open(asset, "rb") as handle:
            results["environment"]["frozen_asset_sha256"] = hashlib.sha256(
                handle.read()).hexdigest()

    cases = [
        ("positive-B1-live", B1_VERTS, B1_FACES, {"mode": "real_planner"}),
        ("positive-tail-real-planner", TAIL_VERTS, TAIL_FACES, {"mode": "real_planner"}),
        ("positive-middle-table-real-planner", MIDDLE_VERTS, MIDDLE_FACES,
         {"mode": "real_planner"}),
        ("positive-transitive-3", TRANSITIVE_VERTS, TRANSITIVE_FACES, {"mode": "real_planner"}),
        # ---- WAVE 14: material-slot representation fidelity (real planner, normative Pattern B) ----
        ("positive-material-slots-real-planner", TAIL_VERTS, TAIL_FACES,
         {"mode": "real_planner", "target_slots": MATERIAL_SLOTS_ASSIGNED,
          "unrelated_slots": MATERIAL_SLOTS_UNRELATED}),
        ("positive-material-slots-with-unassigned", TAIL_VERTS, TAIL_FACES,
         {"mode": "real_planner", "target_slots": MATERIAL_SLOTS_UNASSIGNED}),
        ("positive-object-linked-slot", TAIL_VERTS, TAIL_FACES,
         {"mode": "real_planner", "target_slots": MATERIAL_SLOTS_OBJECT_LINKED}),
        ("diagnostic-lossy-pattern-a-drops-material-slots", TAIL_VERTS, TAIL_FACES,
         {"mode": "real_planner", "target_slots": MATERIAL_SLOTS_ASSIGNED,
          "primitive": "pattern_a"}),
        ("negative-missing-authorization", B1_VERTS, B1_FACES, {"authorization": None}),
        ("negative-no-artifact-string", B1_VERTS, B1_FACES,
         {"authorization": "REPAIR_MERGE_VERTEX"}),
        ("negative-wrong-target-mesh", B1_VERTS, B1_FACES,
         {"mutate_params": lambda p, pl: p.update(mesh_id="nonexistent")}),
        ("negative-cross-plan-artifact", B1_VERTS, B1_FACES, {"authorization": "OTHER_PLAN"}),
        ("negative-mapping-digest-mismatch", B1_VERTS, B1_FACES,
         {"mutate_params": lambda p, pl: p.update(mapping_digest="0" * 64)}),
        ("negative-subgrid-declared", SZERO_VERTS, SZERO_FACES,
         {"mutate_params": lambda p, pl: p.update(all_groups_exact=False)}),
        ("positive-signed-zero-numeric-exact", SZERO_VERTS, SZERO_FACES, {}),
        ("negative-topology-hazard", CREATES_VERTS, CREATES_FACES, {}),
        ("negative-corrupt-mutator-drops-face", B1_VERTS, B1_FACES,
         {"mutator_kwargs": {"drop_last_face": True}}),
        ("negative-corrupt-mutator-shifts-coord", B1_VERTS, B1_FACES,
         {"mutator_kwargs": {"shift_coord": True}}),
        ("negative-liar-mutator", B1_VERTS, B1_FACES, {"mutator_kwargs": {"liar": True}}),
    ]

    other_plan = None
    for label, verts, faces, kwargs in cases:
        try:
            kwargs = dict(kwargs)
            if "authorization" not in kwargs:
                kwargs["authorization"] = "AUTO"
            if kwargs.get("authorization") == "OTHER_PLAN":
                build_scene(bpy, verts=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
                            faces=[(0, 1, 2)], unrelated=False)
                engine = LiveEngine(bpy)
                scene, report = live_extractor(engine)
                other_params, _ = derive_merge_parameters(scene, report, "pitch")
                other_plan, other_corr = synthetic_plan(scene, other_params)
                kwargs = dict(kwargs, authorization=artifact(other_plan, other_corr))
                label = label
            elif kwargs.get("authorization") == "AUTO":
                kwargs = dict(kwargs)
            result = run_case(label, verts, faces, **kwargs)
            results["cases"].append(result)
        except Exception:  # noqa: BLE001 - record, never abort the whole run
            results["errors"].append({"case": label, "traceback": traceback.format_exc()[-3000:]})

    # the disposable Blender process is discarded; nothing was written
    results["session"] = {
        "filepath_at_end": bpy.data.filepath,
        "is_dirty": bool(bpy.data.is_dirty),
        "saved_anything": False,
    }
    print("ATLAS_MERGE_LIVE_START")
    print(json.dumps(results))
    print("ATLAS_MERGE_LIVE_END")


if __name__ == "__main__":
    main()
