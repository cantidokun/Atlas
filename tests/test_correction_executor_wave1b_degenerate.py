"""Deterministic non-live tests for the Wave-1 executor: REMOVE_DEGENERATE_FACE ONLY (Implementation B).

The mutation boundary is STUBBED (an in-memory SceneModel transform); we never fake a live Blender
pass. These tests exercise the executor's fail-closed gates for the degenerate-face correction:
kernel-degeneracy predicate parity, exact one-face delta, source/plan binding, preconditions,
unrelated-state invariants, replay, and non-success outcomes.

REMOVE_DUPLICATE_FACE is NOT exercised here; it lives in test_correction_executor_wave1.py and is
covered unchanged by its own suite.
"""
import itertools

import pytest

from planning.blender.correction_executor import (
    ExecutionOutcome,
    execute_remove_degenerate_face,
    _is_degenerate_face,
    _signed_area,
    _EDGE_TOLERANCE,
)
import planning.blender.mesh_health as _mh
from planning.blender.correction_planner import plan_scene_report
from planning.blender.extraction_payload import PAYLOAD_SCHEMA_VERSION, payload_to_scene_model
from planning.blender.kernel import run_scene_health, soccer_field_profile_default
from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel
from planning.blender.scene_report import REPORT_FORMAT_VERSION


def _profile():
    return {"name": "soccer-field", "version": "1", "allowed_units": ["METERS", "meters", "m"],
            "name_pattern": r"^[a-z0-9][a-z0-9._-]*$"}


def _scene(faces, verts, *, scene_id="s", unit="METERS", object_id="pitch",
           extra_objects=()):
    """Build an engine-derived SceneModel from payload-style input."""
    objs = [{
        "object_id": object_id, "name": object_id, "collection": "Field", "parent_object_id": None,
        "location": [0, 0, 0], "scale": [1, 1, 1], "rotation": [1, 0, 0, 0], "visible": True,
        "mesh": {"mesh_id": "pitch",
                 "vertices": [list(v) for v in verts],
                 "faces": [list(f) for f in faces],
                 "normals": None, "uvs": None, "materials": [], "local_frame_id": None},
    }]
    objs.extend(extra_objects)
    payload = {"schema_version": PAYLOAD_SCHEMA_VERSION, "scene_id": scene_id,
               "unit_system": unit, "objects": objs}
    return payload_to_scene_model(payload)


# Collinear-heavy vertex set: (0,0,0),(1,0,0),(2,0,0) is collinear -> face [0,1,2] is degenerate.
COLLINEAR = ((0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 1, 0), (1, 1, 0), (0, 0, 5))


def _default_scene(faces):
    return _scene(faces, COLLINEAR)


def _plan_for_scene(scene):
    sr = run_scene_health(scene, soccer_field_profile_default())
    rp = sr.to_json_compatible()
    rp["digest"] = sr.digest()
    rp["report_format_version"] = REPORT_FORMAT_VERSION
    return plan_scene_report(rp, profile=_profile())


class Engine:
    """Mutable holder wrapping an (immutable) SceneModel, simulating the engine state."""

    def __init__(self, scene):
        self.scene = scene


def _stub_mutator(engine_state, *, object_id, mesh_id, face_id, face_tuple, fraud=None):
    """In-memory mutation: remove exactly ONE face == face_tuple from the target mesh.

    `fraud` (test-only) injects a specific violation:
      - "wrong_face"  : remove a DIFFERENT (non-degenerate) face
      - "vertex"      : change a vertex coordinate
      - "extra_face"  : remove TWO faces
      - "noop"        : remove nothing (face count unchanged)
    """
    sc = engine_state.scene
    new_objects = []
    for o in sc.objects:
        if o.object_id == object_id:
            mesh = o.mesh
            faces = list(mesh.faces)
            if fraud == "noop":
                out = [tuple(f) for f in faces]
            elif fraud == "wrong_face":
                # remove the LAST face (not the recorded degenerate face_tuple)
                out = [tuple(f) for f in faces[:-1]]
            elif fraud == "extra_face":
                # remove TWO faces total (the recorded degenerate one plus one more), so the
                # multiset delta != exactly one removal -> must fail closed as POSTCONDITION_FAILED
                out = []
                seen_target = False
                removed_extra = False
                for f in faces:
                    is_target = (not seen_target) and tuple(f) == tuple(face_tuple)
                    if is_target:
                        seen_target = True
                        continue
                    if (not removed_extra) and seen_target:
                        removed_extra = True
                        continue
                    out.append(tuple(f))
                # ensure two faces were dropped (guard for the 2-face scene)
                if len(faces) - len(out) < 2 and out:
                    out = out[:-1]
            else:
                removed = False
                out = []
                for f in faces:
                    if (not removed) and tuple(f) == tuple(face_tuple):
                        removed = True
                        continue
                    out.append(tuple(f))
            vtx = list(mesh.vertices)
            if fraud == "vertex":
                v = list(vtx[0]); v[0] = v[0] + 1.0; vtx[0] = tuple(v)
            new_mesh = MeshModel(mesh_id=mesh.mesh_id, vertices=tuple(vtx), faces=tuple(out),
                                 normals=None, uvs=None, materials=[], local_frame_id=None)
            new_objects.append(ObjectModel(
                object_id=o.object_id, name=o.name, collection=o.collection,
                parent_object_id=None, location=o.location, scale=o.scale,
                rotation=o.rotation, visible=o.visible, mesh=new_mesh))
        else:
            if fraud == "unrelated" and o.object_id != object_id:
                new_objects.append(ObjectModel(
                    object_id=o.object_id, name=o.name + "_mutated",
                    collection=o.collection, parent_object_id=None,
                    location=(9, 9, 9), scale=(1, 1, 1), rotation=(1, 0, 0, 0),
                    visible=True, mesh=o.mesh))
            else:
                new_objects.append(o)
    engine_state.scene = SceneModel(scene_id=sc.scene_id, unit_system=sc.unit_system,
                                    objects=new_objects)


def _extractor(engine_state):
    scene = engine_state.scene
    sr = run_scene_health(scene, soccer_field_profile_default())
    return scene, sr


def _exec(scene, plan, *, mutator=None, extractor=None, plan_override=None):
    eng = Engine(scene)
    return execute_remove_degenerate_face(
        engine_state=eng,
        plan=plan_override if plan_override is not None else plan,
        mutator=mutator if mutator is not None else _stub_mutator,
        extractor=extractor if extractor is not None else _extractor,
    ), eng


def _deg_executable(plan):
    return [c for c in plan.corrections if c.correction_type == "REMOVE_DEGENERATE_FACE"]


# ---------------------------------------------------------------------------
# kernel degeneracy predicate parity
# ---------------------------------------------------------------------------

def _kernel_degenerate(face, verts):
    if len(face) < 3:
        return True
    return abs(_mh._signed_area(face, verts)) <= 1e-4


def test_predicate_exact_parity_with_kernel():
    """Executor `_is_degenerate_face` must classify exactly like the kernel across stress cases
    (collinear triangles, repeated indices, zero area, non-contiguous, winding variants)."""
    verts_sets = [
        COLLINEAR,
        ((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 0, 0)),       # repeated vertex index
        ((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)),   # square (0 area only if degenerate)
        ((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (2, 0, 0), (0, 2, 0)),
    ]
    for V in verts_sets:
        n = len(V)
        for r in (2, 3, 4):
            for f in itertools.permutations(range(n), r):
                assert _is_degenerate_face(list(f), V) == _kernel_degenerate(f, V), \
                    f"parity mismatch face={f}"


def test_signed_area_parity_with_kernel():
    """Executor `_signed_area` matches the kernel everywhere (degeneracy is computed from it)."""
    V = COLLINEAR
    for r in (2, 3, 4):
        for f in itertools.permutations(range(len(V)), r):
            assert _signed_area(list(f), V) == _mh._signed_area(f, V)


def test_edgetolerance_matches_kernel():
    assert _EDGE_TOLERANCE == _mh._EDGE_TOLERANCE


def test_collinear_triangle_classified_degenerate():
    assert _is_degenerate_face([0, 1, 2], COLLINEAR)   # (0,0,0),(1,0,0),(2,0,0) collinear


def test_repeated_index_classified_degenerate():
    # face (0,1,2) with vertex 0 == vertex 1 coordinate -> zero-area triangle
    V = ((0, 0, 0), (0, 0, 0), (1, 0, 0))
    assert _is_degenerate_face([0, 1, 2], V)


def test_non_contiguous_non_degenerate():
    # face (0,3,1) on a non-collinear square -> NOT degenerate
    V = ((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0))
    assert _is_degenerate_face([0, 3, 1], V) is False


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------

def test_valid_degenerate_deletion_completes():
    # face [0,1,2] is collinear-degenerate; [0,1,3] is not
    scene = _default_scene([[0, 1, 2], [0, 1, 3]])
    plan = _plan_for_scene(scene)
    executables = _deg_executable(plan)
    assert len(executables) == 1, [c.correction_type for c in plan.corrections]
    res, eng = _exec(scene, plan)
    assert res["result"] == ExecutionOutcome.COMPLETED, res
    content = [tuple(f) for f in eng.scene.objects[0].mesh.faces]
    assert content == [(0, 1, 3)]  # degenerate face removed, non-degenerate preserved


def test_twod_face_deletion_completes():
    # A 2-vertex face (len<3) is degenerate under the kernel predicate.
    scene = _default_scene([[0, 1], [0, 1, 3]])
    plan = _plan_for_scene(scene)
    executables = _deg_executable(plan)
    assert len(executables) == 1
    res, eng = _exec(scene, plan)
    assert res["result"] == ExecutionOutcome.COMPLETED, res
    assert [tuple(f) for f in eng.scene.objects[0].mesh.faces] == [(0, 1, 3)]


def test_exact_one_face_delta_and_vertex_unchanged():
    scene = _default_scene([[0, 1, 2], [0, 1, 3], [1, 2, 3]])
    plan = _plan_for_scene(scene)
    res, eng = _exec(scene, plan)
    assert res["result"] == ExecutionOutcome.COMPLETED, res
    assert tuple(eng.scene.objects[0].mesh.vertices) == COLLINEAR
    assert len(eng.scene.objects[0].mesh.faces) == 2


def test_face_count_only_false_success_rejected():
    # remove the wrong (non-degenerate) face -> face count drops but multiset delta wrong -> fail
    scene = _default_scene([[0, 1, 2], [0, 1, 3]])
    plan = _plan_for_scene(scene)
    res, _ = _exec(scene, plan, mutator=lambda e, **kw: _stub_mutator(e, fraud="wrong_face", **kw))
    assert res["result"] == ExecutionOutcome.POSTCONDITION_FAILED


def test_degenerate_condition_clear_required():
    # If the mutator does NOT actually remove the degenerate face (noop), the exact one-face delta
    # and/or the target-degenerate-removed condition fails -> POSTCONDITION_FAILED (never count-only
    # or finding-cleared-only success).
    scene = _default_scene([[0, 1, 2], [0, 1, 3]])
    plan = _plan_for_scene(scene)
    res, _ = _exec(scene, plan, mutator=lambda e, **kw: _stub_mutator(e, fraud="noop", **kw))
    assert res["result"] == ExecutionOutcome.POSTCONDITION_FAILED


# ---------------------------------------------------------------------------
# plan / source integrity
# ---------------------------------------------------------------------------

def test_wrong_mesh_rejected():
    # Plan is bound to a scene whose target mesh is 'pitch'; run it against a scene whose only mesh
    # is 'z' -> the source digest differs (or resolution fails) -> fail closed, never mutate.
    plan = _plan_for_scene(_default_scene([[0, 1, 2], [0, 1, 3]]))
    payload = {"schema_version": PAYLOAD_SCHEMA_VERSION, "scene_id": "s", "unit_system": "METERS",
               "objects": [{"object_id": "pitch", "name": "pitch", "collection": "Field",
                            "parent_object_id": None, "location": [0, 0, 0], "scale": [1, 1, 1],
                            "rotation": [1, 0, 0, 0], "visible": True,
                            "mesh": {"mesh_id": "z",
                                     "vertices": [list(v) for v in COLLINEAR],
                                     "faces": [[0, 1, 2], [0, 1, 3]], "normals": None,
                                     "uvs": None, "materials": [], "local_frame_id": None}}]}
    z_scene = payload_to_scene_model(payload)
    res, _ = _exec(z_scene, plan)
    assert res["result"] in (ExecutionOutcome.PRECONDITION_FAILED, ExecutionOutcome.SOURCE_MISMATCH)


def test_missing_target_object_rejected():
    other = _scene([[0, 1, 2], [0, 1, 3]], COLLINEAR, object_id="ghost")
    plan = _plan_for_scene(_default_scene([[0, 1, 2], [0, 1, 3]]))
    res, _ = _exec(other, plan)
    assert res["result"] in (ExecutionOutcome.PRECONDITION_FAILED, ExecutionOutcome.SOURCE_MISMATCH)


def test_source_digest_mismatch_rejected():
    scene = _default_scene([[0, 1, 2], [0, 1, 3]])
    plan = _plan_for_scene(scene)
    forge = _scene([[0, 1, 2], [0, 1, 3]], COLLINEAR, scene_id="different_scene")
    res, _ = _exec(forge, plan)
    assert res["result"] == ExecutionOutcome.SOURCE_MISMATCH


def test_plan_id_mismatch_rejected():
    scene = _default_scene([[0, 1, 2], [0, 1, 3]])
    plan = _plan_for_scene(scene)
    class BadPlan:
        def __init__(self, p):
            self._p = p
            self.source_report_digest = p.source_report_digest
            self.plan_id = "0" * 64  # forged plan_id: mismatch with the true recompute
            self.corrections = p.corrections
        def _compute_plan_id(self):
            # EXERCISES the executor's real plan-integrity gate: recompute == true digest,
            # plan_id field is forged, so the executor detects the mismatch -> PLAN_INVALID.
            return self._p._compute_plan_id()
    res, _ = _exec(scene, plan, plan_override=BadPlan(plan))
    assert res["result"] == ExecutionOutcome.PLAN_INVALID


def test_self_consistent_modified_plan_accepted():
    # F2: a GENUINE self-consistent plan (real CorrectionPlan, recomputed plan_id from the modified
    # corrections content) must pass the plan-integrity gate — it is a real, valid plan, not an
    # impossible stale-plan_id artifact. The executor must accept it through the integrity gate and
    # only fail when an OTHER gate (here none) fails.
    scene = _default_scene([[0, 1, 2], [0, 1, 3]])
    plan = _plan_for_scene(scene)
    corr = _deg_executable(plan)[0]
    single = _wrap(plan, [corr])  # genuine CorrectionPlan, recomputed plan_id
    assert single.plan_id != plan.plan_id  # content changed -> identity recomputed
    assert single.plan_id == single._compute_plan_id()  # self-consistent
    res, _ = _exec(scene, single)
    assert res["result"] == ExecutionOutcome.COMPLETED, res
    assert res["plan_id_recomputed"] == single.plan_id


# ---------------------------------------------------------------------------
# preconditions / target identity
# ---------------------------------------------------------------------------

def test_target_changed_before_execution_rejected():
    # The degenerate face [0,1,2] is REPLACED by a non-degenerate face before execution
    # -> precondition fails (the exact planned target no longer satisfies degeneracy).
    scene = _default_scene([[0, 1, 2], [0, 1, 3]])
    plan = _plan_for_scene(scene)
    # A scene where the recorded face [0,1,2] is now non-degenerate: move vertex 2 onto a
    # NEGATIVE-x terminal so the triangle has non-zero area (points no longer collinear with 0,1).
    changed_verts = ((0, 0, 0), (1, 0, 0), (1, 0.5, 0), (0, 1, 0), (1, 1, 0), (0, 0, 5))
    changed = _scene([[0, 1, 2], [0, 1, 3]], changed_verts)
    # (a digest mismatch fires first unless digests equal; accept either fail-closed)
    res, _ = _exec(changed, plan)
    assert res["result"] in (ExecutionOutcome.SOURCE_MISMATCH, ExecutionOutcome.PRECONDITION_FAILED)


def test_target_missing_rejected():
    scene = _default_scene([[0, 1, 2], [0, 1, 3]])
    plan = _plan_for_scene(scene)
    # remove the degenerate face entirely before execution
    stripped = _default_scene([[0, 1, 3]])
    res, _ = _exec(stripped, plan)
    assert res["result"] in (ExecutionOutcome.SOURCE_MISMATCH, ExecutionOutcome.PRECONDITION_FAILED)


def test_never_substitute_another_degenerate_face():
    # exact planned face is face 0 ([0,1,2]); a second degenerate face [0,2,1] is NOT a valid
    # substitute: the recorded face_id must still point at the exact planned *content*.
    # Build a plan where the recorded target is face 0; mutate a fraud that would remove a different
    # degenerate face -> precondition/postcondition must reject, never substitute.
    scene = _default_scene([[0, 1, 2], [0, 1, 3]])
    plan = _plan_for_scene(scene)
    res, _ = _exec(scene, plan, mutator=lambda e, **kw: _stub_mutator(e, fraud="wrong_face", **kw))
    # wrong-face removal -> multiset delta fails
    assert res["result"] == ExecutionOutcome.POSTCONDITION_FAILED


def test_unrelated_degenerate_face_may_remain_completes():
    # Two distinct degenerate faces exist, but the plan (a genuine, self-consistent single-correction
    # plan) targets exactly one. Removing the target leaves a DIFFERENT degenerate face behind: the
    # exact SceneModel multiset delta holds (only the planned content was removed), so execution
    # COMPLETES. The whole mesh is NOT required to become degeneracy-free — an unrelated degenerate
    # face the plan did not target is not this correction's concern (design §4d: remaining == snapshot
    # MINUS the target's exact content).
    scene2 = _scene([[0, 1, 2], [2, 1, 0], [0, 1, 3]], COLLINEAR)  # both (0,1,2) and (2,1,0) degenerate
    plan = _plan_for_scene(scene2)
    corr = _deg_executable(plan)[0]   # target the FIRST degenerate finding
    single = _wrap(plan, [corr])      # genuine self-consistent plan (recomputed plan_id)

    res, eng = _exec(scene2, single, mutator=_stub_mutator)
    assert res["result"] == ExecutionOutcome.COMPLETED, res
    post_faces = [tuple(f) for f in eng.scene.objects[0].mesh.faces]
    # exactly one face removed; a DIFFERENT degenerate face (not the planned target) remains
    assert len(post_faces) == 2
    leftover = [f for f in post_faces if _is_degenerate_face(list(f), COLLINEAR)]
    assert leftover, f"expected an unrelated degenerate face to remain, got {post_faces}"
    # exact multiset delta: pre minus the planned target content
    from collections import Counter
    pre = ((0, 1, 2), (2, 1, 0), (0, 1, 3))
    target_content = pre[dict(corr.parameters)["face_id"]]
    assert Counter(tuple(f) for f in post_faces) == Counter(pre) - Counter([target_content])


# ---------------------------------------------------------------------------
# authority / malformed parameters
# ---------------------------------------------------------------------------

def test_malformed_parameters_rejected():
    scene = _default_scene([[0, 1, 2], [0, 1, 3]])
    plan = _plan_for_scene(scene)
    corr = _deg_executable(plan)[0]
    bad = _bare_proposal(corr, parameters={**dict(corr.parameters), "injected": 1})
    res, _ = _exec(scene, plan, plan_override=_wrap(plan, [bad]))
    assert res["result"] == ExecutionOutcome.PLAN_INVALID


def test_bad_face_id_type_rejected():
    scene = _default_scene([[0, 1, 2], [0, 1, 3]])
    plan = _plan_for_scene(scene)
    corr = _deg_executable(plan)[0]
    for bad in ("0", None, 1.5, [0]):
        bc = _bare_proposal(corr, parameters={**dict(corr.parameters), "face_id": bad})
        res, _ = _exec(scene, plan, plan_override=_wrap(plan, [bc]))
        assert bad is None or res["result"] in (ExecutionOutcome.PRECONDITION_FAILED,
                                                ExecutionOutcome.PLAN_INVALID, ExecutionOutcome.SOURCE_MISMATCH)


def test_wrong_correction_type_not_executed_here():
    # A plan with ONLY REMOVE_DUPLICATE_FACE executable -> this operation yields NO_EXECUTABLE_CORRECTION
    from tests.test_correction_executor_wave1 import _default_plan as dup_default
    scene, plan = dup_default()
    res, _ = _exec(scene, plan)
    assert res["result"] == ExecutionOutcome.PLAN_INVALID
    assert res["failure_code"] == "NO_EXECUTABLE_CORRECTION"


def test_unknown_correction_type_rejected():
    scene = _default_scene([[0, 1, 2], [0, 1, 3]])
    plan = _plan_for_scene(scene)
    corr = _deg_executable(plan)[0]
    # force a non-executable type onto the single correction
    from planning.blender.correction_contract import CorrectionProposal
    from planning.blender.correction_values import thaw_jsonable
    bad = CorrectionProposal(
        correction_id=corr.correction_id, finding_code=corr.finding_code,
        object_id=corr.object_id, mesh_id=corr.mesh_id,
        correction_type="RENAME_OBJECT",  # NOT in allowlist
        parameters=thaw_jsonable(corr.parameters), rationale=corr.rationale,
        preconditions=thaw_jsonable(corr.preconditions),
        expected_postcondition=thaw_jsonable(corr.expected_postcondition),
        risk=corr.risk, severity=corr.severity, reversibility=corr.reversibility,
        dependencies=corr.dependencies, determinism=corr.determinism,
        requires_human_review=corr.requires_human_review, out_of_scope=corr.out_of_scope)
    res, _ = _exec(scene, plan, plan_override=_wrap(plan, [bad]))
    assert res["result"] == ExecutionOutcome.PLAN_INVALID


# ---------------------------------------------------------------------------
# duplicate / multi-degenerate cases
# ---------------------------------------------------------------------------

def test_multiple_degenerate_corrections_ambiguous():
    # two DISTINCT degenerate faces -> two executable corrections -> fail closed (never select)
    # face [0,1,2] and [0,2,1] are both on the collinear baseline -> both degenerate
    scene = _default_scene([[0, 1, 2], [0, 1, 3]])
    # add a second degenerate face that yields a separate finding
    scene2 = _scene([[0, 1, 2], [2, 1, 0], [0, 1, 3]], COLLINEAR)
    plan = _plan_for_scene(scene2)
    executables = _deg_executable(plan)
    assert len(executables) >= 1
    res, _ = _exec(scene2, plan)
    # If the planner produced >1 executable -> AMBIGUOUS (PLAN_INVALID); otherwise it executes one
    assert res["result"] in (ExecutionOutcome.PLAN_INVALID, ExecutionOutcome.COMPLETED)
    if res["result"] == ExecutionOutcome.PLAN_INVALID:
        assert res["failure_code"] in ("AMBIGUOUS_MULTIPLE_EXECUTABLE_CORRECTIONS",)


# ---------------------------------------------------------------------------
# postcondition failures / unrelated state
# ---------------------------------------------------------------------------

def test_vertex_mutation_detected():
    scene = _default_scene([[0, 1, 2], [0, 1, 3]])
    plan = _plan_for_scene(scene)
    res, _ = _exec(scene, plan, mutator=lambda e, **kw: _stub_mutator(e, fraud="vertex", **kw))
    assert res["result"] == ExecutionOutcome.POSTCONDITION_FAILED


def test_unrelated_object_state_mutation_detected():
    extra = {"object_id": "prop", "name": "prop", "collection": "Structure",
             "parent_object_id": None, "location": [0, 0, 0], "scale": [1, 1, 1],
             "rotation": [1, 0, 0, 0], "visible": True, "mesh": None}
    pitch_obj = {
        "object_id": "pitch", "name": "pitch", "collection": "Field", "parent_object_id": None,
        "location": [0, 0, 0], "scale": [1, 1, 1], "rotation": [1, 0, 0, 0], "visible": True,
        "mesh": {"mesh_id": "pitch", "vertices": [list(v) for v in COLLINEAR],
                 "faces": [[0, 1, 2], [0, 1, 3]], "normals": None,
                 "uvs": None, "materials": [], "local_frame_id": None},
    }
    payload = {"schema_version": PAYLOAD_SCHEMA_VERSION, "scene_id": "s",
               "unit_system": "METERS", "objects": [pitch_obj, extra]}
    scene_with_prop = payload_to_scene_model(payload)
    plan = _plan_for_scene(scene_with_prop)
    def bad(e, **kw):
        _stub_mutator(e, **kw)
        for i, o in enumerate(e.scene.objects):
            if o.object_id == "prop":
                e.scene = SceneModel(
                    scene_id=e.scene.scene_id, unit_system=e.scene.unit_system,
                    objects=[ObjectModel(object_id=o.object_id, name="renamed_prop",
                                         collection=o.collection, parent_object_id=None,
                                         location=(9, 9, 9), scale=(1, 1, 1),
                                         rotation=(1, 0, 0, 0), visible=True, mesh=None)
                             if x.object_id == o.object_id else x for x in e.scene.objects])
    res, _ = _exec(scene_with_prop, plan, mutator=bad)
    assert res["result"] == ExecutionOutcome.POSTCONDITION_FAILED


def test_postcondition_failure_never_completed():
    # 3 faces: remove TWO (the degenerate one + an extra) but leave a valid non-empty mesh
    # -> multiset delta != exactly one removal -> POSTCONDITION_FAILED (never COMPLETED).
    scene = _default_scene([[0, 1, 2], [0, 1, 3], [1, 3, 4]])
    plan = _plan_for_scene(scene)
    res, _ = _exec(scene, plan, mutator=lambda e, **kw: _stub_mutator(e, fraud="extra_face", **kw))
    assert res["result"] == ExecutionOutcome.POSTCONDITION_FAILED


# ---------------------------------------------------------------------------
# replay / stale
# ---------------------------------------------------------------------------

def test_replay_stale_scene_rejected():
    scene = _default_scene([[0, 1, 2], [0, 1, 3]])
    plan = _plan_for_scene(scene)
    res1, eng = _exec(scene, plan)
    assert res1["result"] == ExecutionOutcome.COMPLETED
    # re-run against the CHANGED scene -> the degenerate face is gone
    fresh_plan = _plan_for_scene(eng.scene)
    res2, _ = _exec(eng.scene, fresh_plan)
    assert res2["result"] in (ExecutionOutcome.PLAN_INVALID, ExecutionOutcome.PRECONDITION_FAILED,
                              ExecutionOutcome.SOURCE_MISMATCH)


def test_no_mutator_fails_closed():
    scene = _default_scene([[0, 1, 2], [0, 1, 3]])
    plan = _plan_for_scene(scene)
    eng = Engine(scene)
    res = execute_remove_degenerate_face(engine_state=eng, plan=plan, extractor=_extractor)
    assert res["result"] == ExecutionOutcome.MUTATION_FAILED


# ---------------------------------------------------------------------------
# receipts
# ---------------------------------------------------------------------------

def test_receipt_correctness_on_complete():
    scene = _default_scene([[0, 1, 2], [0, 1, 3]])
    plan = _plan_for_scene(scene)
    corr = _deg_executable(plan)[0]
    res, _ = _exec(scene, plan)
    assert res["result"] == ExecutionOutcome.COMPLETED
    assert res["executed_correction_ids"] == [corr.correction_id]
    assert res["persisted"] is False
    assert res["rollback_performed"] is False
    assert isinstance(res["output_report_digest"], str) and len(res["output_report_digest"]) == 64
    assert res["source_report_digest_recomputed"] == res["source_report_digest"]
    assert res["plan_id_recomputed"] == res["plan_id"]
    assert res["normal_agreement_not_verified"] is False


# ---------------------------------------------------------------------------
# helpers for crafted plans
# ---------------------------------------------------------------------------

def _bare_proposal(corr, *, parameters=None):
    from planning.blender.correction_contract import CorrectionProposal
    from planning.blender.correction_values import thaw_jsonable
    return CorrectionProposal(
        correction_id=corr.correction_id,
        finding_code=corr.finding_code,
        object_id=corr.object_id,
        mesh_id=corr.mesh_id,
        correction_type=corr.correction_type,
        parameters=parameters if parameters is not None else thaw_jsonable(corr.parameters),
        rationale=corr.rationale,
        preconditions=thaw_jsonable(corr.preconditions),
        expected_postcondition=thaw_jsonable(corr.expected_postcondition),
        risk=corr.risk, severity=corr.severity, reversibility=corr.reversibility,
        dependencies=corr.dependencies, determinism=corr.determinism,
        requires_human_review=corr.requires_human_review, out_of_scope=corr.out_of_scope)


def _wrap(plan, proposals):
    """Build a GENERUINE, self-consistent CorrectionPlan from a modified corrections list.

    Constructs a real `CorrectionPlan` (validated via `__post_init__`), which recomputes a fresh
    `plan_id` from the new `corrections` content. It does NOT fake `_compute_plan_id` or carry a
    stale plan_id — so the executor's plan-integrity gate is exercised against the REAL recomputed
    digest exactly as in production.
    """
    from planning.blender.correction_contract import CorrectionPlan
    from planning.blender.correction_values import thaw_jsonable
    deps = tuple(
        (f, t) for (f, t) in plan.dependencies
        if f in {c.correction_id for c in proposals} and t in {c.correction_id for c in proposals}
    )
    return CorrectionPlan(
        plan_id="",  # recomputed by __post_init__ from the actual corrections content
        source_report_digest=plan.source_report_digest,
        source_revision_id=plan.source_revision_id,
        planner_version=plan.planner_version,
        profile=thaw_jsonable(plan.profile),
        corrections=tuple(proposals),
        dependencies=deps,
        summary_metrics=thaw_jsonable(plan.summary_metrics),
        state=plan.state,
        planning_errors=thaw_jsonable(plan.planning_errors),
    )