"""LIVE Blender driver for the W2 authorization-aware gate family (run INSIDE Blender, never in CI).

Wave 15 — W2 `REPAIR_FACE_WINDING` live boundary closure.
Authoritative design: ``planning/blender/BLENDER_WAVE15_W1_W1B_W2_LIVE_CLOSURE_DESIGN.md``
(§B.2 authority model, §E W2 contract + §E.1 receipt honesty, §F/§F.1 Wave 14 transfer and the
test-only containment rule, §G material-index non-claim, §H.2 gate family 2, §I target selection,
§J.3 adversarial matrix, §M.9 probe record).

Executed by ``tests/test_live_blender_w2_winding_gate.py`` via::

    blender --background --python tests/w2_winding_live_script.py

Per case this driver runs the COMPLETE live path::

    disposable live Blender scene -> bpy_extraction.extract_scene -> payload_to_scene_model
    -> run_scene_health -> plan_scene_report (REAL planner, D1/D2/D3 model)
    -> REAL AuthorizationArtifact (correction_authorization contract, parsed by
       parse_authorization; NOTHING from the plan state alone is treated as authorization)
    -> execute_repair_face_winding (REAL executor: plan integrity -> allowlist -> parameter
       allowlist -> AUTHORIZATION GATE -> source binding -> WC-P6..P17 -> authorization_verified
       -> exactly one bounded mutation -> fresh extraction -> WC-Q1..Q13 -> receipt)
    -> REAL Blender mutation (Wave 14 Pattern B: same datablock rebuild)
    -> raw Wave 14 boundary evidence + a sandboxed save attempt

and prints one JSON evidence block between the markers ``ATLAS_W2_LIVE_START`` /
``ATLAS_W2_LIVE_END``.

AUTHORITY MODEL (verified from the repository, not assumed — recorded as live evidence):
``MESH_WINDING_INCONSISTENT`` is ``HEURISTIC`` / ``FIDELITY_GEOMETRY`` / ``PARTIALLY_REVERSIBLE`` /
``auto_propose=True`` and the emitted proposal carries ``requires_human_review=True``: the correction
is ADVISORY until a human decision artifact is presented. The executor entry point
``execute_repair_face_winding`` takes ``authorization`` as a MANDATORY keyword-only argument, and the
authorization gate runs BEFORE any engine contact (no extraction, no mutation). Plan state alone is
NEVER authorization: this driver always constructs a real artifact, and for the D3 probe it
deliberately constructs none.

``authorization_verified == True`` means "authorization AND the fresh-evidence preconditions
(WC-P6..P17) have passed, immediately before the single bounded mutation". It does NOT mean the
correction succeeded — the no-op-after-accepted-authorization case here proves that live
(result ``POSTCONDITION_FAILED`` / ``WC-Q1`` with ``authorization_verified == True``).

REQUIRED NON-CLAIM (design §G) — repeated here as §G/F.1 mandate::

    Pattern B rebuild resets polygon.material_index. mesh.clear_geometry() followed by
    mesh.from_pydata(...) reconstructs every polygon with material_index == 0; per-face material
    assignment does NOT survive a geometry rebuild. Polygon material assignment is OUTSIDE the frozen
    Atlas representation contract. Wave 15 makes NO claim that per-face material assignment survives,
    and no live gate may assert material_index preservation.

RAW-EVIDENCE CONTAINMENT (design §F.1, red-team F-4): every raw Blender assertion in this driver (raw
slot tables, datablock inventory, orphan detection, unrelated-object material state) is TEST-ONLY
boundary evidence: it lives only in test/gate code, is not imported by production code, is not
promoted into a shared production assertion/validator library, and creates no hidden canonical Atlas
contract. The canonical W2 executor carries no material or datablock clause at all.

BOUNDARY: the mutation primitive lives HERE (live driver) — no production module gains a bpy import,
and ``execute_repair_face_winding`` keeps taking an INJECTED mutator. ADAPTER DISCIPLINE (carried
forward from the W1/W1b red-team refinement): **one mutator invocation = one intended bounded engine
edit**. The canonical contract observes the mutator invocation and the fresh post-state; it does not
and cannot audit arbitrary internal bpy call sequences. No production instrumentation was added to
police that, and the honest boundary is documented (§"documented limitations" in the gate) instead.

SCOPE: W2 only. W1/W1b's implementation and production code are untouched by this task, and this
driver reuses NO face-removal harness: W2 has a distinct entry point, a distinct receipt skeleton, a
distinct parameter set and a mandatory authorization artifact.
"""

import hashlib
import json
import os
import sys
import traceback

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import bpy

from planning.blender.bpy_extraction import extract_scene
from planning.blender.correction_authorization import (
    AUTHORIZATION_VERSION,
    parse_authorization,
)
from planning.blender.correction_contract import CorrectionPlan, CorrectionProposal
from planning.blender.correction_executor import execute_repair_face_winding
from planning.blender.correction_mapping import classify
from planning.blender.correction_planner import _correction_id, plan_scene_report
from planning.blender.correction_values import thaw_jsonable
from planning.blender.extraction_payload import (
    payload_representation_state,
    payload_to_scene_model,
)
from planning.blender.finding_codes import FindingCode, severity_of
from planning.blender.kernel import run_scene_health, soccer_field_profile_default
from planning.blender.scene_report import REPORT_FORMAT_VERSION

# --------------------------------------------------------------------------- constants
W2 = "REPAIR_FACE_WINDING"
WINDING = FindingCode.MESH_WINDING_INCONSISTENT.value
DEG = FindingCode.MESH_DEGENERATE_FACE.value
DV = FindingCode.MESH_DUPLICATE_FACE.value
INVALID_INDEX = FindingCode.MESH_INVALID_INDEX.value

PROFILE = {"name": "soccer-field", "version": "1", "allowed_units": ["METERS", "meters", "m"],
           "name_pattern": r"^[a-z0-9][a-z0-9._-]*$"}
FROZEN_ASSET = os.path.join("tests", "assets", "blender", "atlas_transform_validation.blend")

#: Identity-based target selection (design §I): the decoy "goal" sorts BEFORE the target "pitch", so a
#: positional selector would silently retarget the fixture. Resolution is fail-loud.
TARGET_OBJECT_ID = "pitch"
TARGET_MESH_ID = "pitch"
DECOY_OBJECT_ID = "goal"

TARGET_SLOTS_ASSIGNED = (("DATA", "turf"), ("DATA", "line_markings"))
TARGET_SLOTS_WITH_UNASSIGNED = (("DATA", "turf"), ("DATA", None), ("DATA", "goal_net"))
TARGET_SLOTS_WITH_OBJECT_LINKED = (("DATA", "turf"), ("OBJECT", "line_markings"))
DECOY_SLOTS = (("DATA", "banner"),)

# --------------------------------------------------------------------------- fixtures
#: D2 (§M.9): ONE winding finding (edge [0,1] traversed same-direction by faces 0 and 1). The planner
#: emits candidate_faces [0, 1] with counterpart_faces [1] and NO designation, so the designatable
#: member is face 0 and the recorded counterpart (face 1) must be refused if designated.
D2_VERTS = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)]
D2_FACES = [(0, 1, 2), (0, 1, 3)]

#: D1 (§M.9): TWO findings (edges [0,1] and [0,2]) whose candidate-face intersection is exactly
#: {0}. The planner supplies `designated_face_index: 0` from evidence and `candidate_faces: null`;
#: an artifact supplying a designation for D1 must be refused.
D1_VERTS = D2_VERTS + [(5.0, 5.0, 0.0)]
D1_FACES = [(0, 1, 2), (0, 1, 3), (2, 0, 4)]

#: Degenerate designated-face fixture: face 0 is collinear (kernel-degenerate) AND shares edge [0,1]
#: same-direction with face 1, so the REAL planner emits a D2 proposal whose designatable member is
#: exactly the degenerate face. Presenting a valid artifact that designates it must be refused by
#: WC-P14 (never masked, never substituted).
D2DEG_VERTS = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 5.0, 0.0)]
D2DEG_FACES = [(0, 1, 2), (0, 1, 3)]

#: Duplicate-participating designated face (WC-P14 route ii). NOTE (documented reachability fact):
#: the REAL planner cannot emit a winding proposal for a mesh whose designated face participates in a
#: duplicate pair — duplicate members share their sorted tuple, so they always co-emit conflicting
#: winding identities for the same canonical edge and the aggregator refuses ("refusing to
#: aggregate"), which is D3-style non-emission. The case therefore binds the real planner's D2 plan
#: with the DOCUMENTED designation remap (see `remap_plan`), which is exactly the threat WC-P14
#: defends against: an integrity-valid plan whose designation is no longer a legal winding target.
D2DUP_VERTS = D2_VERTS + [(10.0, 0.0, 0.0), (11.0, 0.0, 0.0), (10.0, 1.0, 0.0)]
D2DUP_FACES = [(0, 1, 2), (0, 1, 3), (4, 5, 6), (4, 5, 6)]

#: Reversal-creates-a-duplicate fixture: face 2 is the EXACT reverse of face 0, so reversing the
#: designated face 0 makes it bit-identical to face 2 (a real duplicate pair appears).
D2Q7_VERTS = D2_VERTS
D2Q7_FACES = [(0, 1, 2), (0, 1, 3), (2, 1, 0)]

#: D3 (planner non-emission): TWO winding findings (edges [0,1] and [4,5]) whose candidate-face
#: intersections are DISJOINT — the planner must emit NO winding proposal and keep the findings
#: review-only. Never executed: no artifact is fabricated for D3.
D3_VERTS = D2_VERTS + [(10.0, 0.0, 0.0), (11.0, 0.0, 0.0), (10.0, 1.0, 0.0), (10.0, -1.0, 0.0)]
D3_FACES = [(0, 1, 2), (0, 1, 3), (4, 5, 6), (4, 5, 7)]

#: decoy mesh faces (a single non-degenerate triangle on its own datablock)
DECOY_FACES = [(0, 1, 2)]


# --------------------------------------------------------------------------- live boundary
class LiveEngine:
    """The one mutable engine handle the executor is given (a thin holder, no extra authority)."""

    def __init__(self, bpy_module):
        self.bpy = bpy_module


class CountingExtractor:
    """The real live extractor, with an invocation counter so the gate can prove WHEN engine contact
    began (authorization refusals must consume ZERO extractions)."""

    def __init__(self):
        self.calls = 0

    def __call__(self, engine_state):
        self.calls += 1
        payload = extract_scene(engine_state.bpy)
        scene = payload_to_scene_model(payload)
        report = run_scene_health(scene, soccer_field_profile_default())
        return scene, report


# --------------------------------------------------------------------------- fixture construction
def reset_scene():
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
    for index, (link, name) in enumerate(spec):
        obj.data.materials.append(slot_material(name))
        if link == "OBJECT":
            obj.material_slots[index].link = "OBJECT"
            obj.material_slots[index].material = slot_material(name)
    return material_slot_table(obj)


def build_scene(*, verts, faces, target_slots=None, decoy_slots=DECOY_SLOTS, decoy_faces=DECOY_FACES):
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
    decoy_mesh.from_pydata([(20.0, 20.0, 20.0), (21.0, 20.0, 20.0), (20.0, 21.0, 20.0),
                            (20.0, 22.0, 20.0), (21.0, 22.0, 20.0)], [],
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
        "object_names_in_extraction_order": [o.name for o in sorted(bpy.data.objects,
                                                                   key=lambda o: o.name)],
        "mesh_datablocks": sorted(m.name for m in bpy.data.meshes),
        "material_datablocks": sorted(m.name for m in bpy.data.materials),
        "filepath": bpy.data.filepath,
        "is_dirty": bool(bpy.data.is_dirty),
    }


def raw_object(snapshot, name):
    return next((o for o in snapshot["objects"] if o["name"] == name), None)


# --------------------------------------------------------------------------- evidence helpers
def histogram(report, mesh_id):
    hist = {}
    for finding in report.findings:
        if finding.mesh_id != mesh_id:
            continue
        entry = hist.setdefault(finding.code.value, {"count": 0, "measured": []})
        entry["count"] += 1
        entry["measured"].append(finding.measured)
    return {code: entry for code, entry in sorted(hist.items())}


def materials_view(payload, scene, object_id):
    entry = next((o for o in payload["objects"] if o["object_id"] == object_id), None)
    mesh = (entry or {}).get("mesh") or {}
    target = next((o for o in scene.objects if o.object_id == object_id and o.mesh is not None), None)
    return {"key_present": "materials" in mesh, "payload_value": mesh.get("materials"),
            "canonical": list(target.mesh.materials) if target is not None else None,
            "representation_state": list(payload_representation_state(payload))}


def content_binding(report, mesh_id):
    """Content-verified pre-flight binding evidence for W2 (design §I).

    The plan must bind to the intended defect by content: finding code, object/mesh id, the EXACT
    measured edge and the exact measured candidate faces.
    """
    finding = next((f for f in report.findings if f.code.value == WINDING and f.mesh_id == mesh_id),
                   None)
    if finding is None:
        return None
    return {"code": finding.code.value, "mesh_id": finding.mesh_id, "measured": finding.measured}


def winding_capability_view(plan):
    """The capability's classification, read from the REAL mapping module (authority evidence)."""
    determinism, correction_type, risk, reversibility, auto_propose = classify(
        FindingCode.MESH_WINDING_INCONSISTENT, None)
    corrections = [c for c in plan.corrections if c.correction_type == W2]
    return {
        "determinism": determinism, "correction_type": correction_type, "risk": risk,
        "reversibility": reversibility, "auto_propose": auto_propose,
        "proposal_count": len(corrections),
        "requires_human_review": None if not corrections else corrections[0].requires_human_review,
        "plan_state": plan.state,
        "plan_correction_types": sorted({c.correction_type for c in plan.corrections}),
    }


# --------------------------------------------------------------------------- plan handling
def report_dict(report):
    payload = report.to_json_compatible()
    payload["digest"] = report.digest()
    payload["report_format_version"] = REPORT_FORMAT_VERSION
    return payload


def real_plan(report):
    """The REAL planner over the REAL kernel report of the live scene."""
    return plan_scene_report(report_dict(report), profile=PROFILE)


def _clone_correction(corr, *, corr_id, object_id=None, mesh_id=None, parameters=None):
    return type(corr)(
        correction_id=corr_id, finding_code=corr.finding_code,
        object_id=(corr.object_id if object_id is None else object_id),
        mesh_id=(corr.mesh_id if mesh_id is None else mesh_id),
        correction_type=corr.correction_type,
        parameters=(thaw_jsonable(corr.parameters) if parameters is None else parameters),
        rationale=corr.rationale, preconditions=thaw_jsonable(corr.preconditions),
        expected_postcondition=thaw_jsonable(corr.expected_postcondition), risk=corr.risk,
        severity=corr.severity, reversibility=corr.reversibility,
        dependencies=tuple(corr.dependencies), determinism=corr.determinism,
        requires_human_review=corr.requires_human_review, out_of_scope=corr.out_of_scope)


def remap_plan(plan, *, designation=None, mesh_id=None, object_id=None,
               recorded_edges=None, counterpart_faces=None, extra_parameter=None):
    """The DOCUMENTED remap used by the adversarial negatives (design §J.3 / GLM m-3 precedent).

    The plan and every correction come from the REAL planner over the REAL live report; only the
    named recorded parameter is re-pointed, the correction id is recomputed with the planner's own
    content-addressed helper and ``plan_id`` is recomputed BY THE CONTRACT from the resulting
    contents. Nothing else is hand-forged, so the resulting plan is integrity-valid — which is
    exactly why these negatives must be refused by the executor's fresh-evidence gates (WC-P*) or by
    the authorization gate rather than by plan integrity.
    """
    corrections = []
    remap = {}
    for corr in plan.corrections:
        if corr.correction_type != W2:
            corrections.append(corr)
            remap[corr.correction_id] = corr.correction_id
            continue
        params = thaw_jsonable(corr.parameters)
        if designation is not None:
            params["designated_face_index"] = designation
            params["candidate_faces"] = None
        if recorded_edges is not None:
            params["recorded_edges"] = [list(edge) for edge in recorded_edges]
        if counterpart_faces is not None:
            params["counterpart_faces"] = list(counterpart_faces)
        if extra_parameter is not None:
            params[extra_parameter] = 1
        new_object_id = corr.object_id if object_id is None else object_id
        new_mesh_id = params.get("mesh_id", corr.mesh_id) if mesh_id is None else mesh_id
        if mesh_id is not None:
            params["mesh_id"] = mesh_id
        new_id = _correction_id(FindingCode(corr.finding_code), new_object_id, new_mesh_id, params)
        remap[corr.correction_id] = new_id
        corrections.append(_clone_correction(corr, corr_id=new_id, object_id=new_object_id,
                                             mesh_id=new_mesh_id, parameters=params))
    return CorrectionPlan(
        plan_id="", source_report_digest=plan.source_report_digest, source_revision_id=None,
        planner_version="1", profile=thaw_jsonable(plan.profile), corrections=tuple(corrections),
        dependencies=tuple((remap.get(f, f), remap.get(t, t)) for f, t in plan.dependencies),
        summary_metrics=thaw_jsonable(plan.summary_metrics), state=plan.state,
        planning_errors=tuple(plan.planning_errors))


def forge_plan_id(plan, value="f" * 64):
    """Forge a plan whose ``plan_id`` no longer matches its contents (the 'stale plan' negative).

    ``CorrectionPlan`` is self-committing at construction, so this is the documented way to model a
    plan that was edited after construction. The executor must refuse it on integrity alone.
    """
    object.__setattr__(plan, "plan_id", value)
    return plan


def synthetic_w2_plan(report, *, parameters, object_id=TARGET_OBJECT_ID, mesh_id=TARGET_MESH_ID):
    """A CONTRACT-LEGAL synthetic W2 plan bound to the REAL live report digest.

    ``plan_id`` is recomputed BY THE CONTRACT from the contents, the correction id comes from the
    planner's own content-addressed helper, and the classification (determinism/risk/reversibility)
    is read from the REAL mapping module. This models the design's documented threat model (§3.1):
    ``plan_id`` proves the plan was not edited after construction; it proves NOTHING about
    provenance. It is used ONLY for the WC-P14-duplicate negative, because the real aggregator
    provably cannot emit such a plan (see the reachability probe) — the executor must refuse it on
    the FRESH evidence regardless of how the plan was produced.
    """
    determinism, correction_type, risk, reversibility, _auto = classify(
        FindingCode.MESH_WINDING_INCONSISTENT, None)
    digest = report.digest()
    correction_id = _correction_id(FindingCode.MESH_WINDING_INCONSISTENT, object_id, mesh_id,
                                  parameters)
    proposal = CorrectionProposal(
        correction_id=correction_id, finding_code=WINDING, object_id=object_id, mesh_id=mesh_id,
        correction_type=correction_type, parameters=parameters,
        rationale="contract-legal synthetic winding correction (WC-P14 duplicate-reachability case)",
        preconditions=({"source_report_digest": digest}, {"finding_code": WINDING},
                       {"affected_entity": {"object_id": object_id, "mesh_id": mesh_id}}),
        expected_postcondition={"finding_cleared": WINDING, "unrelated_topology_unchanged": True},
        risk=risk, severity=severity_of(FindingCode.MESH_WINDING_INCONSISTENT).value,
        reversibility=reversibility, dependencies=(), determinism=determinism,
        requires_human_review=True, out_of_scope=False)
    return CorrectionPlan(
        plan_id="", source_report_digest=digest, source_revision_id=None, planner_version="1",
        profile={"name": "soccer-field", "version": "1"}, corrections=(proposal,), dependencies=(),
        summary_metrics={}, state="REVIEW_REQUIRED", planning_errors=())


# --------------------------------------------------------------------------- authorization
def _base_artifact(plan, correction, *, designation=None, expected_face_tuple=None):
    artifact = {
        "authorization_version": AUTHORIZATION_VERSION,
        "authorization_policy_version": "1",
        "decision": "APPROVED",
        "correction_type": correction.correction_type,
        "correction_id": correction.correction_id,
        "plan_id": plan.plan_id,
        "source_report_digest": plan.source_report_digest,
        "authorized_by": "atlas-operator",
        "authorized_at_utc": "2026-09-19T12:00:00Z",
        "designated_face_index": designation,
    }
    if expected_face_tuple is not None:
        artifact["expected_face_tuple"] = list(expected_face_tuple)
    return artifact


def build_artifact(spec, plan, correction):
    """Build the presented authorization value for a case, plus its audit description.

    ``spec`` is one of:
      ``None``                 -> no artifact is presented at all;
      ``("valid", {...})``     -> a REAL artifact parsed by ``parse_authorization`` (contract entry);
      ``("dict", {...})``      -> a raw mapping passed to the executor (parse or binding must fail);
      ``("raw", value)``       -> a raw non-mapping / non-JSON value (parse must fail closed).
    """
    if spec is None:
        return None, {"kind": "absent"}
    kind, payload = spec
    if kind == "raw":
        if type(payload) is str:
            described = {"kind": "raw_text", "text": payload}
        else:
            described = {"kind": "raw_value", "type": type(payload).__name__,
                         "value": payload if type(payload) in (int, float, bool, list, dict) else None}
        return payload, described
    if kind == "valid":
        raw = _base_artifact(plan, correction, designation=payload.get("designation"),
                            expected_face_tuple=payload.get("expected_face_tuple"))
        artifact = parse_authorization(raw)          # the real contract entry point
        described = {"kind": "valid", "artifact_digest": artifact.digest(),
                     "policy_version": artifact.authorization_policy_version,
                     "designated_face_index": artifact.designated_face_index,
                     "expected_face_tuple": (list(artifact.expected_face_tuple)
                                             if artifact.expected_face_tuple else None)}
        return artifact, described
    if kind == "dict":
        overrides = dict(payload.get("overrides") or {})
        raw = _base_artifact(plan, correction, designation=payload.get("designation"),
                            expected_face_tuple=payload.get("expected_face_tuple"))
        for key in payload.get("remove") or ():
            raw.pop(key, None)
        raw.update(overrides)
        described = {"kind": "raw_dict", "mutations": sorted(list(overrides) +
                                                             list(payload.get("remove") or ()))}
        return raw, described
    raise RuntimeError(f"unknown artifact spec kind {kind!r}")


# --------------------------------------------------------------------------- live mutators
class W2Mutator:
    """W2 live primitive (Wave 14 Pattern B): rebuild the face table IN PLACE on the same datablock,
    replacing ONLY the designated index's tuple by its exact plain reversal.

    ADAPTER DISCIPLINE: one invocation = one intended bounded engine edit. ``engine_edits`` records how
    many rebuild operations this mutator actually performed, so the gate can state the observable
    boundary honestly when a hostile mutator still lands on the canonical post-state.
    """

    primitive = "pattern_b_same_datablock"

    def __init__(self, *, mode="faithful", liar=False):
        self.mode = mode
        self.liar = liar
        self.calls = []
        self.engine_edits = 0

    # -- helpers -------------------------------------------------------------------------------
    def _record(self, kwargs):
        self.calls.append({k: (list(v) if isinstance(v, tuple) else v) for k, v in kwargs.items()})

    def _tables(self, object_id):
        obj = bpy.data.objects.get(object_id)
        if obj is None:
            raise RuntimeError(f"live target object {object_id!r} does not exist")
        return obj, [list(p.vertices) for p in obj.data.polygons], \
            [tuple(float(c) for c in v.co) for v in obj.data.vertices]

    def _rebuild(self, obj, faces, verts=None):
        self.engine_edits += 1
        if verts is None:
            verts = [tuple(float(c) for c in v.co) for v in obj.data.vertices]
        obj.data.clear_geometry()
        obj.data.from_pydata(verts, [], [tuple(int(i) for i in f) for f in faces])
        obj.data.update()

    def _reverse(self, faces, index):
        faces[index] = list(reversed(faces[index]))

    # -- the mutator ---------------------------------------------------------------------------
    def __call__(self, engine_state, *, object_id, mesh_id, face_index, face_tuple):
        self._record({"object_id": object_id, "mesh_id": mesh_id, "face_index": face_index,
                      "face_tuple": face_tuple})
        obj, faces, verts = self._tables(object_id)
        mode = self.mode

        if mode == "noop":
            if self.liar:
                return {"ok": True, "result": "COMPLETED"}
            return None

        if mode == "faithful":
            self._reverse(faces, face_index)
            self._rebuild(obj, faces)
        elif mode == "wrong_face":
            self._reverse(faces, 1 if face_index != 1 else 0)
            self._rebuild(obj, faces)
        elif mode == "two_faces":
            self._reverse(faces, face_index)
            other = 1 if face_index != 1 else 0
            self._reverse(faces, other)
            self._rebuild(obj, faces)
        elif mode == "rotate":
            # a cyclic rotation is NOT the exact plain reversal WC-Q1 requires
            face = faces[face_index]
            faces[face_index] = face[1:] + face[:1]
            self._rebuild(obj, faces)
        elif mode == "vertex_shift":
            self._reverse(faces, face_index)
            moved = list(verts)
            moved[0] = (moved[0][0] + 1.0, moved[0][1], moved[0][2])
            self._rebuild(obj, faces, moved)
        elif mode == "unrelated_mutation":
            self._reverse(faces, face_index)
            self._rebuild(obj, faces)
            decoy = bpy.data.objects.get(DECOY_OBJECT_ID)
            if decoy is not None:
                decoy.data.vertices[0].co = (99.0, 99.0, 99.0)
                decoy.data.update()
        elif mode == "slot_destruction":
            self._reverse(faces, face_index)
            self._rebuild(obj, faces)
            while len(obj.data.materials):
                obj.data.materials.pop()
        elif mode == "datablock_replacement":
            # SUPERSEDED Pattern A, retained as a deliberately lossy diagnostic (Wave 14 §5)
            self._reverse(faces, face_index)
            new_mesh = bpy.data.meshes.new(obj.data.name)
            new_mesh.from_pydata(verts, [], [tuple(int(i) for i in f) for f in faces])
            new_mesh.update()
            self.engine_edits += 1
            obj.data = new_mesh
        elif mode == "orphan_creation":
            self._reverse(faces, face_index)
            self._rebuild(obj, faces)
            bpy.data.meshes.new("w2_orphan_probe")
        elif mode == "two_engine_edits":
            # hostile: THREE engine rebuilds (reverse, reverse back, reverse again) that end on the
            # AUTHORIZED canonical state. The contract observes the invocation count and the fresh
            # post-state, not the internal edit sequence.
            self._reverse(faces, face_index)
            self._rebuild(obj, faces)
            _, reverted, _ = self._tables(object_id)
            self._reverse(reverted, face_index)
            self._rebuild(obj, reverted)
            _, final_faces, _ = self._tables(object_id)
            self._reverse(final_faces, face_index)
            self._rebuild(obj, final_faces)
        else:
            raise RuntimeError(f"unknown W2 mutator mode {mode!r}")

        if self.liar:
            return {"ok": True, "result": "COMPLETED"}
        return None


# --------------------------------------------------------------------------- case runner
def run_case(label, *, verts, faces, target_slots=TARGET_SLOTS_ASSIGNED, decoy_faces=DECOY_FACES,
             decoy_slots=DECOY_SLOTS, artifact_spec=("valid", {}), remap=None, tamper_plan_id=False,
             plan_mode="real", synthetic_parameters=None, mutator_mode="faithful", liar=False,
             engine_mutation=None, expect=None):
    build_scene(verts=verts, faces=faces, target_slots=target_slots, decoy_slots=decoy_slots,
                decoy_faces=decoy_faces)
    engine = LiveEngine(bpy)
    extractor = CountingExtractor()
    payload_before = extract_scene(bpy)
    pre_scene = payload_to_scene_model(payload_before)
    pre_report = run_scene_health(pre_scene, soccer_field_profile_default())

    # --- identity-based target resolution (design §I): fail loud, never positional --------------
    target_obj = next((o for o in pre_scene.objects
                       if o.object_id == TARGET_OBJECT_ID and o.mesh is not None), None)
    if target_obj is None or target_obj.mesh.mesh_id != TARGET_MESH_ID:
        raise RuntimeError(
            f"live fixture target {TARGET_OBJECT_ID!r}/{TARGET_MESH_ID!r} is missing from the "
            "extracted scene; this driver never falls back to another object")
    if not any(o.object_id == DECOY_OBJECT_ID for o in pre_scene.objects):
        raise RuntimeError(f"live fixture decoy {DECOY_OBJECT_ID!r} is missing")

    if plan_mode == "synthetic":
        # CONTRACT-LEGAL synthetic plan (documented threat model): used only where the real
        # aggregator provably cannot emit a plan, so the reachability probe records why.
        assert synthetic_parameters is not None, "synthetic plan mode requires parameters"
        plan = synthetic_w2_plan(pre_report, parameters=dict(synthetic_parameters))
    else:
        plan = real_plan(pre_report)
    capability_before = winding_capability_view(plan)
    if remap is not None:
        plan = remap_plan(plan, **remap)
    if tamper_plan_id:
        plan = forge_plan_id(plan)
    corrections = [c for c in plan.corrections if c.correction_type == W2]
    if not corrections:
        raise RuntimeError(f"{label}: the real planner emitted no W2 proposal for this fixture")
    correction = corrections[0]
    parameters = [thaw_jsonable(c.parameters) for c in corrections]

    if engine_mutation is not None:
        engine_mutation()

    authorization, authorization_view = build_artifact(artifact_spec, plan, correction)
    mutator = W2Mutator(mode=mutator_mode, liar=liar)
    raw_before = raw_snapshot()

    receipt = execute_repair_face_winding(engine_state=engine, plan=plan,
                                         authorization=authorization, mutator=mutator,
                                         extractor=extractor)
    raw_after = raw_snapshot()

    payload_after, post_scene, post_report, post_error = None, None, None, None
    try:
        payload_after = extract_scene(bpy)
        post_scene = payload_to_scene_model(payload_after)
        post_report = run_scene_health(post_scene, soccer_field_profile_default())
    except Exception as exc:  # noqa: BLE001 - a destroyed post-state is itself evidence
        post_error = f"{type(exc).__name__}: {exc}"

    def face_table(scene):
        if scene is None:
            return None
        mesh = next((o.mesh for o in scene.objects if o.object_id == TARGET_OBJECT_ID), None)
        return None if mesh is None else [list(f) for f in mesh.faces]

    return {
        "case": label,
        "capability": W2,
        "expect": expect,
        "fixture": {"vertices": [list(v) for v in verts], "faces": [list(f) for f in faces],
                    "target_slots": [list(s) for s in (target_slots or ())],
                    "decoy_slots": [list(s) for s in (decoy_slots or ())],
                    "decoy_faces": [list(f) for f in decoy_faces]},
        "target": {"object_id": TARGET_OBJECT_ID, "mesh_id": TARGET_MESH_ID,
                   "resolved_by": "identity", "decoy_object_id": DECOY_OBJECT_ID,
                   "decoy_sorts_before_target": DECOY_OBJECT_ID < TARGET_OBJECT_ID},
        "authority": capability_before,
        "binding": {"proposal_count": capability_before["proposal_count"],
                    "correction_ids": [c.correction_id for c in corrections],
                    "parameters": parameters,
                    "expected_finding": content_binding(pre_report, TARGET_MESH_ID),
                    "plan_designation": parameters[0].get("designated_face_index"),
                    "plan_candidate_faces": parameters[0].get("candidate_faces")},
        "plan": {"plan_id": plan.plan_id, "state": plan.state,
                 "source_report_digest": plan.source_report_digest,
                 "all_correction_types": sorted({c.correction_type for c in plan.corrections}),
                 "plan_id_tampered": bool(tamper_plan_id), "plan_mode": plan_mode},
        "plan_integrity_recomputes": plan._compute_plan_id() == plan.plan_id,
        "authorization": authorization_view,
        "mutator": {"primitive": mutator.primitive, "mode": mutator_mode, "liar": liar,
                    "invocations": len(mutator.calls), "engine_edits": mutator.engine_edits,
                    "calls": mutator.calls},
        "extractor_calls": extractor.calls,
        "pre": {
            "digest": pre_report.digest(),
            "vertex_count": len(target_obj.mesh.vertices),
            "faces": [list(f) for f in target_obj.mesh.faces],
            "histogram": histogram(pre_report, TARGET_MESH_ID),
            "decoy_histogram": histogram(pre_report, DECOY_OBJECT_ID),
            "materials": materials_view(payload_before, pre_scene, TARGET_OBJECT_ID),
            "decoy_materials": materials_view(payload_before, pre_scene, DECOY_OBJECT_ID),
        },
        "post": None if post_report is None else {
            "digest": post_report.digest(),
            "faces": face_table(post_scene),
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
            "authorization_verified": receipt["authorization_verified"],
            "authorization_digest": receipt["authorization_digest"],
            "authorization_policy_version": receipt["authorization_policy_version"],
            "correction_id": receipt["correction_id"],
            "plan_id_recomputed": receipt["plan_id_recomputed"],
            "plan_integrity_ok": receipt["plan_id"] == receipt["plan_id_recomputed"],
            "source_report_digest_recomputed": receipt["source_report_digest_recomputed"],
            "executed_correction_ids": receipt["executed_correction_ids"],
            "skipped_correction_ids": receipt["skipped_correction_ids"],
            "target_face": receipt["target_face"],
            "recorded_edges": receipt["recorded_edges"],
            "counterpart_faces": receipt["counterpart_faces"],
            "pre_winding_findings": receipt["pre_winding_findings"],
            "post_winding_findings": receipt["post_winding_findings"],
            "topology_only_orientation_repair": receipt["topology_only_orientation_repair"],
            "normal_agreement_not_verified": receipt["normal_agreement_not_verified"],
            "persisted": receipt["persisted"],
            "rollback_performed": receipt["rollback_performed"],
            "output_report_digest": receipt["output_report_digest"],
            "precondition_results": receipt["precondition_results"],
            "postcondition_results": receipt["postcondition_results"],
        },
        "raw_before": raw_before,
        "raw_after": raw_after,
    }


# --------------------------------------------------------------------------- D3 probe
def d3_planner_non_emission():
    """D3: the candidate-face intersection is empty -> the planner must emit NO winding proposal.

    The planner's refusal is the evidence. NO authorization artifact is fabricated for D3 and no
    execution is attempted (design §E / §J.3: D3 is planner non-emission only).
    """
    build_scene(verts=D3_VERTS, faces=D3_FACES, target_slots=TARGET_SLOTS_ASSIGNED)
    payload = extract_scene(bpy)
    scene = payload_to_scene_model(payload)
    report = run_scene_health(scene, soccer_field_profile_default())
    plan = real_plan(report)
    corrections = [c for c in plan.corrections if c.correction_type == W2]
    winding_findings = [f.measured for f in report.findings
                        if f.code.value == WINDING and f.mesh_id == TARGET_MESH_ID]
    intersections = None
    if len(winding_findings) >= 2:
        sets = [set(f["faces"]) for f in winding_findings]
        common = set(sets[0])
        for other in sets[1:]:
            common &= other
        intersections = sorted(common)
    # live POSITIVE CONTROL in the same run: the D1 fixture (non-empty intersection) DOES emit a
    # winding proposal, so "no proposal for D3" is a discriminating observation, not a dead path.
    build_scene(verts=D1_VERTS, faces=D1_FACES, target_slots=TARGET_SLOTS_ASSIGNED)
    control_payload = extract_scene(bpy)
    control_scene = payload_to_scene_model(control_payload)
    control_report = run_scene_health(control_scene, soccer_field_profile_default())
    control_plan = real_plan(control_report)
    control_proposals = [c for c in control_plan.corrections if c.correction_type == W2]
    return {
        "fixture": {"vertices": [list(v) for v in D3_VERTS], "faces": [list(f) for f in D3_FACES]},
        "winding_findings": winding_findings,
        "candidate_face_intersection": intersections,
        "winding_proposal_count": len(corrections),
        "plan_state": plan.state,
        "plan_correction_types": sorted({c.correction_type for c in plan.corrections
                                        if c.correction_type is not None}),
        "review_only_evidence": f"plan_state={plan.state}",
        "planning_errors": list(plan.planning_errors),
        "d1_control_winding_proposal_count": len(control_proposals),
        "d1_control_designation": (
            None if not control_proposals
            else thaw_jsonable(control_proposals[0].parameters).get("designated_face_index")),
        "artifact_constructed": False,
        "execution_attempted": False,
    }


def unreachable_negative_probes():
    """Reachability evidence for two §J.3 rows that the LIVE boundary provably cannot realise.

    (i)  ``WC-P14`` duplicate clause — a designated/candidate face that participates in a duplicate
         pair. Duplicate members share their entire sorted-tuple edge set, so the aggregator either
         sees a conflicting winding identity on one canonical edge or a candidate-face intersection
         that is not a single face (D3). Both refusals are measured here (no W2 proposal).
    (ii) ``WC-Q7`` / "a reversal creates a new duplicate" — the exact reversal of the designated face
         has the same vertex set, hence shares every edge with a same-vertex-set twin; a pre-existing
         twin makes the winding edge NON-MANIFOLD (incidence 3), so no winding finding and no W2 plan
         can exist for that pre-state. Measured here.

    Neither probe fabricates an authorization artifact, and neither executes anything: they record
    what the frozen planner/kernel do with the candidate fixtures. The corresponding executor
    predicates remain defence in depth and are exercised by the offline deterministic suite; the
    WC-P14 duplicate clause is ALSO executed live through a contract-legal synthetic plan.
    """
    out = {}

    build_scene(verts=D2DUP_VERTS, faces=D2DUP_FACES, target_slots=TARGET_SLOTS_ASSIGNED)
    payload = extract_scene(bpy)
    scene = payload_to_scene_model(payload)
    report = run_scene_health(scene, soccer_field_profile_default())
    plan = real_plan(report)
    findings = [{"code": f.code.value, "measured": f.measured} for f in report.findings]
    winding = [f["measured"] for f in findings if f["code"] == WINDING]
    sets = [set(f["faces"]) for f in winding]
    common = set(sets[0]) if sets else set()
    for other in sets[1:]:
        common &= other
    out["wc_p14_duplicate"] = {
        "fixture": {"vertices": [list(v) for v in D2DUP_VERTS],
                    "faces": [list(f) for f in D2DUP_FACES]},
        "findings": findings,
        "winding_finding_count": len(winding),
        "candidate_face_intersection": sorted(common),
        "winding_proposal_count": len([c for c in plan.corrections if c.correction_type == W2]),
        "plan_correction_types": sorted({c.correction_type for c in plan.corrections
                                        if c.correction_type is not None}),
        "coverage": "NOT_REACHABLE_THROUGH_THE_LIVE_BOUNDARY",
        "reason": "every face that shares a duplicate key with another face also shares its entire "
                  "edge set, so the aggregator's candidate-face intersection can never be the single "
                  "duplicate member (D3-style non-emission)",
    }

    build_scene(verts=D2Q7_VERTS, faces=D2Q7_FACES, target_slots=TARGET_SLOTS_ASSIGNED)
    payload2 = extract_scene(bpy)
    scene2 = payload_to_scene_model(payload2)
    report2 = run_scene_health(scene2, soccer_field_profile_default())
    plan2 = real_plan(report2)
    findings2 = [{"code": f.code.value, "measured": f.measured} for f in report2.findings]
    out["wc_q7_new_duplicate"] = {
        "fixture": {"vertices": [list(v) for v in D2Q7_VERTS],
                    "faces": [list(f) for f in D2Q7_FACES]},
        "findings": findings2,
        "non_manifold_edges": [f["measured"] for f in findings2
                               if f["code"] == "MESH_NON_MANIFOLD_EDGE"],
        "winding_finding_count": len([f for f in findings2 if f["code"] == WINDING]),
        "winding_proposal_count": len([c for c in plan2.corrections if c.correction_type == W2]),
        "coverage": "NOT_REACHABLE_THROUGH_THE_LIVE_BOUNDARY",
        "reason": "the exact reversal of the designated face has the same vertex set, so a twin with "
                  "that vertex set turns the winding edge NON-MANIFOLD (incidence 3); the pre-state "
                  "then has no winding finding and no W2 plan can exist",
    }
    return out


def save_attempt_probe():
    """A real SAVE ATTEMPT that cannot create a file, with sandboxed evidence (design §H.3/§J.1)."""
    import tempfile

    original_cwd = os.getcwd()
    sandbox = tempfile.mkdtemp(prefix="atlas_w2_save_probe_")
    probe = {"filepath_before": bpy.data.filepath, "sandbox": sandbox, "cwd_before": original_cwd}
    os.chdir(sandbox)
    try:
        try:
            bpy.ops.wm.save_mainfile()
            probe.update({"error_type": None, "error_message": None, "refused": False})
        except Exception as exc:  # noqa: BLE001 - the refusal is the evidence
            probe.update({"error_type": type(exc).__name__, "error_message": str(exc),
                          "refused": True})
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


# --------------------------------------------------------------------------- case table
D2 = dict(verts=D2_VERTS, faces=D2_FACES)
D1 = dict(verts=D1_VERTS, faces=D1_FACES)

CASES = [
    # ---- D1 / D2 positives (authorization accepted, exactly one reversal) ---------------------
    ("w2-positive-d2-operator-designation", dict(
        **D2, artifact_spec=("valid", {"designation": 0}),
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1,
                "authorization_verified": True, "extractor_calls": 2})),
    ("w2-positive-d1-evidence-designation", dict(
        **D1, artifact_spec=("valid", {}),
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1,
                "authorization_verified": True, "extractor_calls": 2,
                "note": "D1: the designation comes from EVIDENCE (plan parameter); the artifact must "
                        "not supply one"})),
    ("w2-positive-d2-expected-face-tuple-assertion", dict(
        **D2, artifact_spec=("valid", {"designation": 0, "expected_face_tuple": [0, 1, 2]}),
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1,
                "authorization_verified": True, "extractor_calls": 2,
                "note": "the deferred optional expected_face_tuple assertion is evaluated against "
                        "the fresh authoritative model after source binding"})),
    ("w2-positive-d2-unassigned-slot-raw-only", dict(
        **D2, target_slots=TARGET_SLOTS_WITH_UNASSIGNED,
        artifact_spec=("valid", {"designation": 0}),
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1,
                "authorization_verified": True, "extractor_calls": 2})),
    ("w2-positive-d2-object-linked-slot-raw-only", dict(
        **D2, target_slots=TARGET_SLOTS_WITH_OBJECT_LINKED,
        artifact_spec=("valid", {"designation": 0}),
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1,
                "authorization_verified": True, "extractor_calls": 2})),
    # ---- the §E.1 authorization negative family ----------------------------------------------
    ("w2-negative-authorization-absent-d2", dict(
        **D2, artifact_spec=None,
        expect={"result": "AUTHORIZATION_REQUIRED", "failure_code": "AUTHORIZATION_REQUIRED",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-authorization-absent-d1", dict(
        **D1, artifact_spec=None,
        expect={"result": "AUTHORIZATION_REQUIRED", "failure_code": "AUTHORIZATION_REQUIRED",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-artifact-malformed-json", dict(
        **D2, artifact_spec=("raw", "{not json"),
        expect={"result": "AUTHORIZATION_INVALID", "failure_code": "MALFORMED_JSON",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-artifact-json-not-an-object", dict(
        **D2, artifact_spec=("raw", "[]"),
        expect={"result": "AUTHORIZATION_INVALID", "failure_code": "NOT_A_MAPPING",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-artifact-not-a-mapping", dict(
        **D2, artifact_spec=("raw", 12345),
        expect={"result": "AUTHORIZATION_INVALID", "failure_code": "NOT_A_MAPPING",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-artifact-missing-required-field", dict(
        **D2, artifact_spec=("dict", {"remove": ["decision"]}),
        expect={"result": "AUTHORIZATION_INVALID", "failure_code": "MISSING_FIELD",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-artifact-duplicate-json-key", dict(
        **D2, artifact_spec=("raw", '{"decision":"APPROVED","decision":"APPROVED"}'),
        expect={"result": "AUTHORIZATION_INVALID", "failure_code": "DUPLICATE_JSON_KEY",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-authorization-version-unsupported", dict(
        **D2, artifact_spec=("dict", {"overrides": {"authorization_version": "2"}}),
        expect={"result": "AUTHORIZATION_INVALID", "failure_code": "UNSUPPORTED_AUTHORIZATION_VERSION",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-policy-version-unsupported", dict(
        **D2, artifact_spec=("dict", {"overrides": {"authorization_policy_version": "2"}}),
        expect={"result": "AUTHORIZATION_INVALID", "failure_code": "UNSUPPORTED_POLICY_VERSION",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-decision-not-approved", dict(
        **D2, artifact_spec=("dict", {"overrides": {"decision": "REJECTED"}}),
        expect={"result": "AUTHORIZATION_INVALID", "failure_code": "DECISION_NOT_APPROVED",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-correction-type-not-authorizable", dict(
        **D2, artifact_spec=("dict", {"overrides": {"correction_type": "REMOVE_DUPLICATE_FACE"}}),
        expect={"result": "AUTHORIZATION_INVALID",
                "failure_code": "CORRECTION_TYPE_NOT_AUTHORIZABLE",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-correction-type-mismatch", dict(
        **D2, artifact_spec=("dict", {"overrides": {"correction_type": "REPAIR_MERGE_VERTEX"}}),
        expect={"result": "AUTHORIZATION_SCOPE_MISMATCH", "failure_code": "CORRECTION_TYPE_MISMATCH",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-correction-id-mismatch", dict(
        **D2, artifact_spec=("dict", {"overrides": {"correction_id": "MESH_WINDING_INCONSISTENT-x-0"}}),
        expect={"result": "AUTHORIZATION_SCOPE_MISMATCH", "failure_code": "CORRECTION_ID_MISMATCH",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-plan-id-mismatch", dict(
        **D2, artifact_spec=("dict", {"overrides": {"plan_id": "0" * 64}}),
        expect={"result": "AUTHORIZATION_SCOPE_MISMATCH", "failure_code": "PLAN_ID_MISMATCH",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-source-digest-mismatch", dict(
        **D2, artifact_spec=("dict", {"overrides": {"source_report_digest": "0" * 64}}),
        expect={"result": "AUTHORIZATION_SCOPE_MISMATCH", "failure_code": "SOURCE_DIGEST_MISMATCH",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-artifact-unknown-field", dict(
        **D2, artifact_spec=("dict", {"overrides": {"surprise_field": 1}}),
        expect={"result": "AUTHORIZATION_INVALID", "failure_code": "UNKNOWN_FIELD",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-artifact-digest-format-invalid", dict(
        **D2, artifact_spec=("dict", {"overrides": {"plan_id": "not-a-digest"}}),
        expect={"result": "AUTHORIZATION_INVALID", "failure_code": "DIGEST_FORMAT_INVALID",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-d2-designation-required", dict(
        **D2, artifact_spec=("valid", {}),
        expect={"result": "AUTHORIZATION_REQUIRED", "failure_code": "DESIGNATION_REQUIRED",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-d2-designation-outside-candidate-pair", dict(
        **D2, artifact_spec=("valid", {"designation": 2}),
        expect={"result": "AUTHORIZATION_SCOPE_MISMATCH",
                "failure_code": "DESIGNATION_NOT_IN_CANDIDATE_PAIR",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-d2-designation-is-counterpart", dict(
        **D2, artifact_spec=("valid", {"designation": 1}),
        expect={"result": "PRECONDITION_FAILED", "failure_code": "PRECONDITION_FAILED",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 1,
                "note": "the designation names the recorded COUNTERPART face: the WC-P8 counterpart "
                        "rule refuses it on the fresh evidence (never a silent substitution)"})),
    ("w2-negative-d1-designation-supplied", dict(
        **D1, artifact_spec=("valid", {"designation": 0}),
        expect={"result": "AUTHORIZATION_SCOPE_MISMATCH",
                "failure_code": "DESIGNATION_SUPPLIED_FOR_D1",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    # ---- plan / parameter / source negatives -------------------------------------------------
    ("w2-negative-stale-plan-id", dict(
        **D2, artifact_spec=("valid", {"designation": 0}), tamper_plan_id=True,
        expect={"result": "PLAN_INVALID", "failure_code": "PLAN_ID_MISMATCH",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0})),
    ("w2-negative-malformed-parameters-unexpected-key", dict(
        **D2, artifact_spec=("valid", {"designation": 0}),
        remap={"extra_parameter": "unexpected_key"},
        expect={"result": "PLAN_INVALID", "failure_code": "UNEXPECTED_PARAMETER:unexpected_key",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 0,
                "note": "the parameter allowlist runs BEFORE the authorization gate"})),
    ("w2-negative-wrong-mesh", dict(
        **D2, artifact_spec=("valid", {"designation": 0}), remap={"mesh_id": "no_such_mesh"},
        expect={"result": "PRECONDITION_FAILED", "failure_code": "PRECONDITION_FAILED",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 1,
                "note": "WC-P6: the target mesh is unresolvable on the fresh evidence"})),
    ("w2-negative-missing-target-object", dict(
        **D2, artifact_spec=("valid", {"designation": 0}), remap={"object_id": "no_such_object"},
        expect={"result": "PRECONDITION_FAILED", "failure_code": "PRECONDITION_FAILED",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 1})),
    ("w2-negative-designated-index-out-of-range", dict(
        **D1, artifact_spec=("valid", {}), remap={"designation": 99},
        expect={"result": "PRECONDITION_FAILED", "failure_code": "PRECONDITION_FAILED",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 1,
                "note": "WC-P7: the designation is out of range for the fresh face table"})),
    ("w2-negative-designated-face-degenerate", dict(
        verts=D2DEG_VERTS, faces=D2DEG_FACES, artifact_spec=("valid", {"designation": 0}),
        expect={"result": "PRECONDITION_FAILED", "failure_code": "PRECONDITION_FAILED",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 1,
                "note": "WC-P14: the REAL planner's D2 designatable member IS the degenerate face; a "
                        "valid authorization must still be refused (never masked, never substituted)"})),
    ("w2-negative-designated-face-duplicate", dict(
        verts=D2DUP_VERTS, faces=D2DUP_FACES, artifact_spec=("valid", {}), plan_mode="synthetic",
        synthetic_parameters={"mesh_id": TARGET_MESH_ID, "designated_face_index": 3,
                             "candidate_faces": None, "recorded_edges": [[0, 1]],
                             "counterpart_faces": [1],
                             "orientation": "reverse_designated_face_to_shared_edge_opposite"},
        expect={"result": "PRECONDITION_FAILED", "failure_code": "PRECONDITION_FAILED",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 1,
                "note": "WC-P14 (duplicate clause): designated face 3 shares its duplicate key with "
                        "face 2. The plan is CONTRACT-LEGAL (integrity recomputes, artifact bound to "
                        "it, source digest = the real live digest) but provably NOT planner-emittable "
                        "for this report (see the reachability probe): the executor must refuse it on "
                        "the FRESH evidence, which is exactly what P14 is defence for"})),
    ("w2-negative-recorded-edges-disagree-with-fresh", dict(
        **D2, artifact_spec=("valid", {"designation": 0}),
        remap={"recorded_edges": [[0, 2]], "counterpart_faces": [1]},
        expect={"result": "PRECONDITION_FAILED", "failure_code": "PRECONDITION_FAILED",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 1,
                "note": "WC-P17: the recorded edge set no longer agrees with the fresh recomputation"})),
    ("w2-negative-engine-mutated-after-planning", dict(
        **D2, artifact_spec=("valid", {"designation": 0}),
        engine_mutation=lambda: (lambda o: (setattr(o.data.vertices[2].co, "y", 3.0),
                                            o.data.update()))(
            bpy.data.objects.get(TARGET_OBJECT_ID)),
        expect={"result": "SOURCE_MISMATCH", "failure_code": "SOURCE_DIGEST_MISMATCH",
                "mutations": 0, "authorization_verified": False, "extractor_calls": 1,
                "note": "the artifact verified against the plan's digest; the fresh engine digest "
                        "moved, so source binding refuses before any precondition or mutation"})),
    # ---- mutation-shape / postcondition negatives (§J.3) -------------------------------------
    ("w2-negative-noop-after-accepted-authorization", dict(
        **D2, artifact_spec=("valid", {"designation": 0}), mutator_mode="noop",
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "WC-Q1",
                "mutations": 1, "authorization_verified": True, "extractor_calls": 2,
                "note": "THE F-3 PROOF: authorization_verified is True and the mutator ran, yet the "
                        "result is a failure - it is a pre-mutation claim, not a success flag"})),
    ("w2-negative-liar-mutator", dict(
        **D2, artifact_spec=("valid", {"designation": 0}), mutator_mode="noop", liar=True,
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "WC-Q1",
                "mutations": 1, "authorization_verified": True, "extractor_calls": 2})),
    ("w2-negative-mutator-reverses-wrong-face", dict(
        **D2, artifact_spec=("valid", {"designation": 0}), mutator_mode="wrong_face",
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "WC-Q1",
                "mutations": 1, "authorization_verified": True, "extractor_calls": 2})),
    ("w2-negative-mutator-rotates-designated-face", dict(
        **D2, artifact_spec=("valid", {"designation": 0}), mutator_mode="rotate",
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "WC-Q1",
                "mutations": 1, "authorization_verified": True, "extractor_calls": 2,
                "note": "a cyclic rotation is not the exact plain reversal WC-Q1 requires"})),
    ("w2-negative-mutator-reverses-two-faces", dict(
        **D2, artifact_spec=("valid", {"designation": 0}), mutator_mode="two_faces",
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "WC-Q4",
                "mutations": 1, "authorization_verified": True, "extractor_calls": 2})),
    ("w2-negative-mutator-changes-vertex-table", dict(
        **D2, artifact_spec=("valid", {"designation": 0}), mutator_mode="vertex_shift",
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "WC-Q3",
                "mutations": 1, "authorization_verified": True, "extractor_calls": 2})),
    ("w2-negative-mutator-touches-unrelated-object", dict(
        **D2, artifact_spec=("valid", {"designation": 0}), mutator_mode="unrelated_mutation",
        expect={"result": "POSTCONDITION_FAILED", "failure_code": "WC-Q11",
                "mutations": 1, "authorization_verified": True, "extractor_calls": 2})),
    # ---- Wave 14 fidelity evidence (canonical layer has NO material/datablock clause) --------
    ("w2-evidence-material-slot-destruction", dict(
        **D2, artifact_spec=("valid", {"designation": 0}), mutator_mode="slot_destruction",
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1,
                "authorization_verified": True, "extractor_calls": 2})),
    ("w2-evidence-datablock-replacement", dict(
        **D2, artifact_spec=("valid", {"designation": 0}), mutator_mode="datablock_replacement",
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1,
                "authorization_verified": True, "extractor_calls": 2})),
    ("w2-evidence-orphan-inventory-gain", dict(
        **D2, artifact_spec=("valid", {"designation": 0}), mutator_mode="orphan_creation",
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1,
                "authorization_verified": True, "extractor_calls": 2})),
    ("w2-evidence-two-engine-edits-net-correct", dict(
        **D2, artifact_spec=("valid", {"designation": 0}), mutator_mode="two_engine_edits",
        expect={"result": "COMPLETED", "failure_code": None, "mutations": 1,
                "authorization_verified": True, "extractor_calls": 2,
                "note": "DOCUMENTED BOUNDARY: one mutator invocation performed TWO engine edits and "
                        "still landed on the authorized canonical post-state. The contract observes "
                        "the invocation count plus the fresh post-state, not internal bpy calls"})),
]


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
        "authorization_entry_point_requires_artifact": True,
        "w1_w1b_untouched": True,
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

    for name, probe in (("d3_planner_non_emission", d3_planner_non_emission),
                        ("unreachable_negative_probes", unreachable_negative_probes),):
        try:
            results[name] = probe()
        except Exception:  # noqa: BLE001
            results["errors"].append({"case": name, "traceback": traceback.format_exc()[-3000:]})

    try:
        results["save_attempt"] = save_attempt_probe()
    except Exception:  # noqa: BLE001
        results["errors"].append({"case": "save-attempt-probe",
                                  "traceback": traceback.format_exc()[-3000:]})

    results["session"] = {
        "filepath_at_end": bpy.data.filepath,
        "is_dirty": bool(bpy.data.is_dirty),
        "saved_anything": False,
    }
    print("ATLAS_W2_LIVE_START")
    print(json.dumps(results))
    print("ATLAS_W2_LIVE_END")


if __name__ == "__main__":
    main()
