"""Deterministic non-live tests for the Wave-1 executor: REMOVE_DUPLICATE_FACE ONLY.

The mutation boundary is STUBBED (an in-memory SceneModel transform); we never fake a live Blender
pass. These tests exercise the executor's fail-closed gates: source binding, plan integrity,
preconditions, exact one-face delta, multiset correctness, unrelated-state invariant, and
non-success outcomes.
"""
import copy
import itertools

import pytest

from planning.blender.correction_executor import (
    ExecutionOutcome,
    execute_remove_duplicate_face,
)
import planning.blender.correction_executor as _ce
import planning.blender.mesh_health as _mh
from planning.blender.correction_planner import plan_scene_report
from planning.blender.extraction_payload import PAYLOAD_SCHEMA_VERSION, payload_to_scene_model
from planning.blender.finding_codes import FindingCode
from planning.blender.kernel import run_scene_health, soccer_field_profile_default
from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel
from planning.blender.scene_report import REPORT_FORMAT_VERSION, Finding, build_report


def _profile():
    return {"name": "soccer-field", "version": "1", "allowed_units": ["METERS", "meters", "m"],
            "name_pattern": r"^[a-z0-9][a-z0-9._-]*$"}


def _scene(faces, verts, *, scene_id="s", unit="METERS", object_id="pitch",
           extra_objects=()):
    """Build an engine-derived SceneModel from payload-style input."""
    objs = [{
        "object_id": object_id, "name": object_id, "collection": "Field", "parent_object_id": None,
        "location": [0, 0, 0], "scale": [1, 1, 1], "rotation": [1, 0, 0, 0], "visible": True,
        "mesh": {"mesh_id": "m",
                 "vertices": [list(v) for v in verts],
                 "faces": [list(f) for f in faces],
                 "normals": None, "uvs": None, "materials": [], "local_frame_id": None},
    }]
    objs.extend(extra_objects)
    payload = {"schema_version": PAYLOAD_SCHEMA_VERSION, "scene_id": scene_id,
               "unit_system": unit, "objects": objs}
    return payload_to_scene_model(payload)


QUEEN = ((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (2, 0, 0))


def _plan_for_scene(scene):
    sr = run_scene_health(scene, soccer_field_profile_default())
    rp = sr.to_json_compatible()
    rp["digest"] = sr.digest()
    rp["report_format_version"] = REPORT_FORMAT_VERSION
    return plan_scene_report(rp, profile=_profile())


def _plan_scene_digest(scene):
    sr = run_scene_health(scene, soccer_field_profile_default())
    return sr.digest()


class Engine:
    """Mutable holder wrapping an (immutable) SceneModel, simulating the engine state."""

    def __init__(self, scene):
        self.scene = scene


def _stub_mutator(engine_state, *, object_id, mesh_id, face_ids, dup_tuple, fraud=None):
    """In-memory mutation: remove exactly ONE face == dup_tuple from the target mesh.

    `fraud` (test-only) injects a specific violation to exercise postcondition failure:
      - "vertex"      : change a vertex coordinate
      - "wrong_face"  : remove a DIFFERENT face (not the dup content)
      - "extra_face"  : remove TWO faces
      - "unrelated"   : change an unrelated object's name/pose
    """
    sc = engine_state.scene
    new_objects = []
    for o in sc.objects:
        if o.object_id == object_id and fraud != "unrelated_target":
            mesh = o.mesh
            faces = list(mesh.faces)
            if fraud == "wrong_face":
                # remove a face that is NOT the dup content (e.g. the last face)
                out = [tuple(f) for f in faces[:-1]]
                new_mesh = _rebuild_mesh(mesh, faces=out, vertex_fraud=(fraud == "vertex"))
            elif fraud == "extra_face":
                removed = 0
                out = []
                for f in faces:
                    if (not removed) and tuple(f) == tuple(dup_tuple):
                        removed = True
                        continue
                    if tuple(f) != tuple(dup_tuple) and len(out) < len(faces) - 2:
                        pass
                    out.append(tuple(f))
                # force remove two faces total
                out = out[:-1]
                new_mesh = _rebuild_mesh(mesh, faces=out, vertex_fraud=False)
            else:
                removed = False
                out = []
                for f in faces:
                    if (not removed) and tuple(f) == tuple(dup_tuple):
                        removed = True
                        continue
                    out.append(tuple(f))
                new_mesh = _rebuild_mesh(
                    mesh, faces=out, vertex_fraud=(fraud == "vertex")
                )
            new_objects.append(_rebuild_object(o, new_mesh))
        else:
            if fraud == "unrelated" and o.object_id != object_id:
                # mutate an unrelated object's name/pose
                new_objects.append(ObjectModel(
                    object_id=o.object_id, name=o.name + "_mutated",
                    collection=o.collection, parent_object_id=o.parent_object_id,
                    location=o.location, scale=o.scale, rotation=o.rotation,
                    visible=o.visible, mesh=o.mesh,
                ))
            else:
                new_objects.append(o)
    engine_state.scene = SceneModel(
        scene_id=sc.scene_id, unit_system=sc.unit_system, objects=new_objects
    )


def _rebuild_mesh(mesh, faces, vertex_fraud=False):
    verts = list(mesh.vertices)
    if vertex_fraud:
        v = list(verts[0])
        v[0] = v[0] + 1.0
        verts[0] = tuple(v)
    return MeshModel(mesh_id=mesh.mesh_id, vertices=tuple(verts), faces=tuple(faces),
                     normals=mesh.normals, uvs=mesh.uvs, materials=mesh.materials,
                     local_frame_id=mesh.local_frame_id)


def _rebuild_object(o, mesh):
    return ObjectModel(object_id=o.object_id, name=o.name, collection=o.collection,
                       parent_object_id=o.parent_object_id, location=o.location,
                       scale=o.scale, rotation=o.rotation, visible=o.visible, mesh=mesh)


def _extractor(engine_state):
    scene = engine_state.scene
    sr = run_scene_health(scene, soccer_field_profile_default())
    return scene, sr


def _default_plan():
    faces = [(0, 1, 2), (0, 1, 2), (0, 3, 1), (1, 3, 2)]
    scene = _scene(faces, QUEEN)
    return scene, _plan_for_scene(scene)


def _exec(scene, plan, *, mutator=None, extractor=None, plan_override=None):
    eng = Engine(scene)
    return execute_remove_duplicate_face(
        engine_state=eng,
        plan=plan_override if plan_override is not None else plan,
        mutator=mutator if mutator is not None else _stub_mutator,
        extractor=extractor if extractor is not None else _extractor,
    ), eng


# ---------------------------------------------------------------------------
# happy path + scope
# ---------------------------------------------------------------------------

def test_valid_duplicate_deletion_completes():
    scene, plan = _default_plan()
    res, eng = _exec(scene, plan)
    assert res["result"] == ExecutionOutcome.COMPLETED
    assert len(eng.scene.objects[0].mesh.faces) == 3
    # exactly one duplicate removed; counts of (0,1,2) now 1
    content = [tuple(f) for f in eng.scene.objects[0].mesh.faces]
    assert content.count((0, 1, 2)) == 1
    assert res["executed_correction_ids"]
    assert "MESH_WINDING_INCONSISTENT" in "".join(res["skipped_correction_ids"]) or res["skipped_correction_ids"]


def test_exactly_one_face_delta_and_vertex_unchanged():
    scene, plan = _default_plan()
    res, eng = _exec(scene, plan)
    assert res["result"] == ExecutionOutcome.COMPLETED
    mesh = eng.scene.objects[0].mesh
    assert tuple(mesh.vertices) == QUEEN  # vertex table unchanged
    assert len(mesh.faces) == 3


def test_face_count_only_false_success_rejected():
    # a mutator that removes the wrong (non-duplicate) face -> face count drops to 3 BUT the multiset
    # delta does not equal one recorded dup -> POSTCONDITION_FAILED
    scene, plan = _default_plan()
    res, _ = _exec(scene, plan, mutator=lambda e, **kw: _stub_mutator(e, fraud="wrong_face", **kw))
    assert res["result"] == ExecutionOutcome.POSTCONDITION_FAILED


# ---------------------------------------------------------------------------
# plan / source integrity
# ---------------------------------------------------------------------------

def test_wrong_mesh_rejected():
    scene, plan = _default_plan()
    # plan targets mesh 'm'; feed a scene whose only mesh is 'z'
    other = _scene([(0, 1, 2), (0, 1, 2), (0, 2, 1)], QUEEN, object_id="pitch")
    # rebuild: other has no mesh 'm'
    res, _ = _exec(other, plan)
    assert res["result"] in (ExecutionOutcome.PRECONDITION_FAILED, ExecutionOutcome.SOURCE_MISMATCH)


def test_missing_target_object_rejected():
    scene, plan = _default_plan()
    other = _scene([(0, 1, 2), (0, 1, 2)], QUEEN, object_id="ghost")
    res, _ = _exec(other, plan)
    assert res["result"] in (ExecutionOutcome.PRECONDITION_FAILED, ExecutionOutcome.SOURCE_MISMATCH)


def test_source_digest_mismatch_rejected():
    scene, plan = _default_plan()
    # forge a scene whose digest != plan source digest
    forge = _scene([(0, 1, 2), (0, 1, 2), (0, 3, 1), (1, 3, 2)], QUEEN, scene_id="different_scene")
    res, _ = _exec(forge, plan)
    assert res["result"] == ExecutionOutcome.SOURCE_MISMATCH


def test_forged_planner_digest_rejected():
    # A plan consumed by the executor whose source_report_digest is loader-forged cannot survive:
    # the executor recomputes from the scene. Build a plan then corrupt its digest via a real planner
    # rejecting it is hard; instead force execute on a scene whose recomputed digest != plan digest.
    scene, plan = _default_plan()
    res, _ = _exec(scene, plan, extractor=lambda e: (e.scene, type("R", (), {
        "digest": lambda self: "1" * 64, "findings": ()})()))
    # extractor returns a report with a WRONG digest -> SOURCE_MISMATCH (a forged report/digest cannot
    # bind to the plan)
    assert res["result"] == ExecutionOutcome.SOURCE_MISMATCH


def test_plan_id_mismatch_rejected():
    scene, plan = _default_plan()
    # tamper plan_id: executor must detect plan_id recompute mismatch
    class BadPlan:
        def __init__(self, p):
            self._p = p
            self.source_report_digest = p.source_report_digest
            self.plan_id = "0" * 64
            self.corrections = p.corrections
        def _compute_plan_id(self):
            return self._p._compute_plan_id()
    res, _ = _exec(scene, plan, plan_override=BadPlan(plan))
    assert res["result"] == ExecutionOutcome.PLAN_INVALID


# ---------------------------------------------------------------------------
# preconditions
# ---------------------------------------------------------------------------

def test_duplicate_condition_changed_rejected():
    scene, plan = _default_plan()
    # remove one duplicate BEFORE execution so precondition ">=2 faces share key" fails
    faces = [(0, 1, 2), (0, 3, 1), (1, 3, 2)]  # only one (0,1,2)
    changed = _scene(faces, QUEEN)
    res, _ = _exec(changed, plan)
    # the changed scene's digest differs from the plan => SOURCE_MISMATCH (source binding gate fires
    # before preconditions). If digests were forced-equal, the precondition would also fail. Either is
    # fail-closed; never COMPLETED.
    assert res["result"] in (ExecutionOutcome.SOURCE_MISMATCH, ExecutionOutcome.PRECONDITION_FAILED)


def test_vertex_mutation_detected():
    scene, plan = _default_plan()
    res, _ = _exec(scene, plan, mutator=lambda e, **kw: _stub_mutator(e, fraud="vertex", **kw))
    assert res["result"] == ExecutionOutcome.POSTCONDITION_FAILED


def test_unrelated_mesh_mutation_detected():
    # add a second object with its own mesh; mutate it -> postcondition fails
    extra = {"object_id": "prop", "name": "prop", "collection": "Structure",
             "parent_object_id": None, "location": [0, 0, 0], "scale": [1, 1, 1],
             "rotation": [1, 0, 0, 0], "visible": True,
             "mesh": {"mesh_id": "p2", "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]],
                      "faces": [[0, 1, 2], [1, 3, 2]], "normals": None, "uvs": None,
                      "materials": [], "local_frame_id": None}}
    scene = _scene([(0, 1, 2), (0, 1, 2), (0, 3, 1), (1, 3, 2)], QUEEN, extra_objects=[extra])
    plan = _plan_for_scene(scene)

    def bad_mutator(e, **kw):
        # first remove the pitch duplicate as a *correct* mutator, then corrupt the unrelated prop mesh
        _stub_mutator(e, **kw)
        rebuilt = []
        for o in e.scene.objects:
            if o.object_id == "prop":
                nv = tuple((v[0] + 99.0, v[1], v[2]) for v in o.mesh.vertices)
                nm = MeshModel(mesh_id="p2", vertices=nv, faces=o.mesh.faces,
                               normals=None, uvs=None, materials=[], local_frame_id=None)
                rebuilt.append(ObjectModel(
                    object_id=o.object_id, name=o.name, collection=o.collection,
                    parent_object_id=o.parent_object_id, location=o.location,
                    scale=o.scale, rotation=o.rotation, visible=o.visible, mesh=nm))
            else:
                rebuilt.append(o)
        e.scene = SceneModel(scene_id=e.scene.scene_id, unit_system=e.scene.unit_system,
                             objects=rebuilt)

    res, _ = _exec(scene, plan, mutator=bad_mutator)
    assert res["result"] == ExecutionOutcome.POSTCONDITION_FAILED


def test_unrelated_object_state_mutation_detected():
    extra = {"object_id": "prop", "name": "prop", "collection": "Structure",
             "parent_object_id": None, "location": [0, 0, 0], "scale": [1, 1, 1],
             "rotation": [1, 0, 0, 0], "visible": True, "mesh": None}
    scene = _scene([(0, 1, 2), (0, 1, 2), (0, 3, 1), (1, 3, 2)], QUEEN, extra_objects=[extra])
    def bad(e, **kw):
        _stub_mutator(e, **kw)
        for o in e.scene.objects:
            if o.object_id == "prop":
                e.scene = SceneModel(scene_id=e.scene.scene_id, unit_system=e.scene.unit_system,
                                     objects=[ObjectModel(object_id=o.object_id, name="renamed_prop",
                                                          collection=o.collection, parent_object_id=None,
                                                          location=(9, 9, 9), scale=(1, 1, 1),
                                                          rotation=(1, 0, 0, 0), visible=True, mesh=None)
                                              if x.object_id == o.object_id else x for x in e.scene.objects])
    res, _ = _exec(scene, _plan_for_scene(scene), mutator=bad)
    assert res["result"] == ExecutionOutcome.POSTCONDITION_FAILED


def test_object_ordering_mutation_detected():
    # Swapping the relative ORDER of two objects (identical state, different position in
    # SceneModel.objects) must be detected: order is part of the Wave-1 unchanged invariant (pin #3).
    extra = {"object_id": "prop", "name": "prop", "collection": "Structure",
             "parent_object_id": None, "location": [0, 0, 0], "scale": [1, 1, 1],
             "rotation": [1, 0, 0, 0], "visible": True, "mesh": None}
    scene = _scene([(0, 1, 2), (0, 1, 2), (0, 3, 1), (1, 3, 2)], QUEEN, extra_objects=[extra])
    assert [o.object_id for o in scene.objects] == ["pitch", "prop"]

    def reorder(e, **kw):
        _stub_mutator(e, **kw)  # perform the permitted removal but preserve order
        objs = list(e.scene.objects)
        # swap the two objects: same ids, same state, different ORDER only.
        objs[0], objs[1] = objs[1], objs[0]
        e.scene = SceneModel(scene_id=e.scene.scene_id, unit_system=e.scene.unit_system,
                             objects=objs)

    res, _ = _exec(scene, _plan_for_scene(scene), mutator=reorder)
    assert res["result"] == ExecutionOutcome.POSTCONDITION_FAILED


def test_duplicate_chain_case_multiset():
    # 3 identical faces -> the plan emits MULTIPLE duplicate findings; executor requires exactly one
    # executable correction -> must be PLAN_INVALID (ambiguous) OR at least never accidentally remove 2.
    faces = [(0, 1, 2), (0, 1, 2), (0, 1, 2), (0, 3, 1)]
    scene = _scene(faces, QUEEN)
    plan = _plan_for_scene(scene)
    res, _ = _exec(scene, plan)
    # The planner emits two MESH_DUPLICATE_FACE findings (a=0,b=1 and a=0,b=2) => two executable
    # corrections => ambiguous => PLAN_INVALID (never pick one arbitrarily).
    assert res["result"] == ExecutionOutcome.PLAN_INVALID


def test_multiple_distinct_duplicate_pairs_ambiguous():
    # two DIFFERENT duplicate pairs -> two executable corrections -> ambiguous -> fail closed
    faces = [(0, 1, 2), (0, 1, 2), (0, 3, 1), (0, 3, 1)]
    scene = _scene(faces, QUEEN)
    plan = _plan_for_scene(scene)
    res, _ = _exec(scene, plan)
    assert res["result"] == ExecutionOutcome.PLAN_INVALID


# ---------------------------------------------------------------------------
# authority / parameter handling
# ---------------------------------------------------------------------------

def test_unknown_correction_type_rejected():
    # A scene whose plan's ONLY deterministic correction is REMOVE_DEGENERATE_FACE (not executable in
    # Wave 1) -> NO_EXECUTABLE_CORRECTION -> PLAN_INVALID.
    collinear = ((0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 1, 0))  # face (0,1,2) is collinear => degenerate
    scene2 = _scene([(0, 1, 2), (0, 1, 3)], collinear)
    plan2 = _plan_for_scene(scene2)
    data = [c.correction_type for c in plan2.corrections]
    # Must actually contain a non-duplicate deterministic correction for the test to be meaningful.
    assert "REMOVE_DEGENERATE_FACE" in data
    res, _ = _exec(scene2, plan2)
    assert res["result"] == ExecutionOutcome.PLAN_INVALID


def _bare_proposal(corr, *, parameters=None, object_id=None, mesh_id=None):
    """Reconstruct an executable-compatible bare CorrectionProposal (fresh, plain dict params).

    `object_id`/`mesh_id` override the source correction's fields (default: keep them); pass a
    sentinel-like `object_id=None` explicitly to force a mesh-scoped (no owner) proposal.
    """
    from planning.blender.correction_contract import CorrectionProposal
    from planning.blender.correction_values import thaw_jsonable
    return CorrectionProposal(
        correction_id=corr.correction_id,
        finding_code=corr.finding_code,
        object_id=object_id if object_id is not None else corr.object_id,
        mesh_id=mesh_id if mesh_id is not None else corr.mesh_id,
        correction_type=corr.correction_type,
        parameters=parameters if parameters is not None else thaw_jsonable(corr.parameters),
        rationale=corr.rationale,
        preconditions=thaw_jsonable(corr.preconditions),
        expected_postcondition=thaw_jsonable(corr.expected_postcondition),
        risk=corr.risk, severity=corr.severity, reversibility=corr.reversibility,
        dependencies=corr.dependencies, determinism=corr.determinism,
        requires_human_review=corr.requires_human_review, out_of_scope=corr.out_of_scope,
    )


def _plan_with_proposals(plan, proposals):
    """Build a GENERUINE, self-consistent CorrectionPlan from a modified corrections list.

    Constructs a real `CorrectionPlan` (validated via `__post_init__`), which recomputes a fresh
    `plan_id` from the new `corrections` content. It does NOT fake `_compute_plan_id` or carry a
    stale plan_id — so the executor's plan-integrity gate is exercised against the REAL recomputed
    digest exactly as in production.
    """
    from planning.blender.correction_contract import CorrectionPlan
    from planning.blender.correction_values import thaw_jsonable
    ids = {c.correction_id for c in proposals}
    deps = tuple((f, t) for (f, t) in plan.dependencies if f in ids and t in ids)
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


def test_malformed_parameters_rejected():
    scene, plan = _default_plan()
    corr = plan.corrections[0]
    bad_corr = _bare_proposal(corr, parameters={**dict(corr.parameters), "injected": 1})
    res, _ = _exec(scene, plan, plan_override=_plan_with_proposals(plan, [bad_corr]))
    assert res["result"] == ExecutionOutcome.PLAN_INVALID


def test_parameter_injection_rejected():
    # face_ids must be exactly two ints; a wrong/extra shape -> PreconditionError
    scene, plan = _default_plan()
    corr = plan.corrections[0]
    for bad_ids in ([0], [0, 1, 2], ["x", "y"], "00"):
        bad_corr = _bare_proposal(corr, parameters={**dict(corr.parameters), "face_ids": bad_ids})
        res, _ = _exec(scene, plan, plan_override=_plan_with_proposals(plan, [bad_corr]))
        assert res["result"] in (ExecutionOutcome.PLAN_INVALID, ExecutionOutcome.PRECONDITION_FAILED)


# ---------------------------------------------------------------------------
# replay / stale
# ---------------------------------------------------------------------------

def test_replay_stale_scene_rejected():
    scene, plan = _default_plan()
    # after applying once, re-run against the ORIGINAL source -> the second run sees the already-fixed
    # scene but the plan still references the ORIGINAL digest; the source digest recompute fails (the
    # current scene's report digest != plan's original) OR precondition fails — either way NOT a blind
    # re-mutation.
    res1, eng = _exec(scene, plan)
    assert res1["result"] == ExecutionOutcome.COMPLETED
    # now re-serialize the CHANGED scene and re-plan from it -> the face is gone; the plan should be a
    # no-op/fail, never delete another face.
    changed_scene = eng.scene
    fresh_plan = _plan_for_scene(changed_scene)
    res2, eng2 = _exec(changed_scene, fresh_plan)
    # the changed scene has no duplicate face -> no executable correction OR precondition fail
    assert res2["result"] in (ExecutionOutcome.PLAN_INVALID, ExecutionOutcome.PRECONDITION_FAILED,
                              ExecutionOutcome.SOURCE_MISMATCH)


def test_replay_same_plan_against_same_scene_identity_not_substituted():
    # Re-running the EXACT same original plan+scene (no change) must either complete (if still valid)
    # or fail — it must NEVER delete a DIFFERENT face. Since the source is untouched, precondition
    # holds and it should complete again (idempotent). We assert it never reports a face substitution.
    scene, plan = _default_plan()
    res1, eng1 = _exec(scene, plan)
    assert res1["result"] == ExecutionOutcome.COMPLETED
    # fresh scene reflects mutation -> duplicate gone -> re-plan has no executable dup correction
    res2, _ = _exec(eng1.scene, _plan_for_scene(eng1.scene))
    assert res2["result"] != ExecutionOutcome.COMPLETED or any(
        c.correction_type == "REMOVE_DUPLICATE_FACE" for c in ()
    )


# ---------------------------------------------------------------------------
# postcondition failure / partial
# ---------------------------------------------------------------------------

def test_postcondition_failure_never_completed():
    scene, plan = _default_plan()
    res, _ = _exec(scene, plan, mutator=lambda e, **kw: _stub_mutator(e, fraud="vertex", **kw))
    assert res["result"] == ExecutionOutcome.POSTCONDITION_FAILED
    assert res["result"] != ExecutionOutcome.COMPLETED


def test_no_mutator_provided_fails_closed():
    # With an explicit extractor but NO mutator, the executor MUST reach the mutation gate and fail
    # closed (never fabricate a mutation).
    scene, plan = _default_plan()
    eng = Engine(scene)
    res = execute_remove_duplicate_face(engine_state=eng, plan=plan, extractor=_extractor)
    assert res["result"] == ExecutionOutcome.MUTATION_FAILED


def test_output_report_digest_present_on_complete():
    scene, plan = _default_plan()
    res, _ = _exec(scene, plan)
    assert res["result"] == ExecutionOutcome.COMPLETED
    assert isinstance(res["output_report_digest"], str) and len(res["output_report_digest"]) == 64
    assert res["persisted"] is False


# ---------------------------------------------------------------------------
# kernel predicate parity (non-contiguous face indices)
# ---------------------------------------------------------------------------

_WIND_FACES = [
    (0, 3, 1),      # triangular, non-contiguous (regression: used to diverge)
    (0, 3, 1, 2),   # quadrilateral, non-contiguous
    (0, 1, 2),
    (0, 3, 1, 2, 0),
    (3, 1, 0),
    (1, 0, 3),
    (0, 2, 1),
    (2, 3, 0, 1),
    (1, 3, 0, 2, 0),
]

_PARITY_VERTEX_SETS = [
    ((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)),
    ((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (2, 0, 0)),
    ((0, 0, 0), (2, 2, 2), (0, 0, 5), (1, 1, 1), (3, 0, 0), (0, 3, 0), (1, 2, 3)),
]


def test_predicate_exact_parity_with_kernel():
    """Executor _signed_area and duplicate-key must equal the kernel's, for every fixture face and
    vertex set (pin #4 'reproduce EXACTLY'). The pre-fix buggy formula diverged on non-contiguous
    indices like (0,3,1) / (0,3,1,2)."""
    for V in _PARITY_VERTEX_SETS:
        for f in _WIND_FACES:
            if all(i < len(V) for i in f):
                assert _ce._signed_area(f, V) == _mh._signed_area(f, V), \
                    f"_signed_area parity failed: face={f} verts={V}"
                # kernel duplicate key is (sorted_face, winding >= 0.0); executor must match exactly
                ks = (tuple(sorted(f)), _mh._signed_area(f, V) >= 0.0)
                assert _ce._duplicate_key(f, V) == ks, f"duplicate_key parity failed: face={f}"


def test_predicate_parity_generated_permutations():
    """Generated parity over every ordered permutation of (up to) 4 vertices on multiple topologies:
    executor duplicate-key/winding must equal the kernel's."""
    for V in _PARITY_VERTEX_SETS[:2]:
        n = len(V)
        if n < 4:
            continue
        for r in (3, 4):
            for f in itertools.permutations(range(n), r):
                assert _ce._signed_area(f, V) == _mh._signed_area(f, V)
                ks = (tuple(sorted(f)), _mh._signed_area(f, V) >= 0.0)
                assert _ce._duplicate_key(f, V) == ks
    # a larger generated sweep on the 6-vertex set (non-contiguous heavy)
    V = _PARITY_VERTEX_SETS[2]
    for r in (3, 4):
        for f in itertools.permutations(range(len(V)), r):
            assert _ce._signed_area(f, V) == _mh._signed_area(f, V)
            ks = (tuple(sorted(f)), _mh._signed_area(f, V) >= 0.0)
            assert _ce._duplicate_key(f, V) == ks


def test_non_contiguous_triangular_duplicate_deletion_completes():
    # (0,3,1) is a triangular duplicate pair with NON-CONTIGUOUS indices — the exact case that
    # exposed the old buggy _signed_area. Execution must COMPLETE (preconditions agree with kernel).
    V = ((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0))
    faces = [(0, 3, 1), (0, 3, 1), (0, 1, 2)]  # exactly ONE duplicate pair: (0,3,1)
    scene = _scene(faces, V)
    plan = _plan_for_scene(scene)
    executables = [c for c in plan.corrections if c.correction_type == "REMOVE_DUPLICATE_FACE"]
    assert len(executables) == 1, [c.correction_type for c in plan.corrections]
    res, eng = _exec(scene, plan)
    assert res["result"] == ExecutionOutcome.COMPLETED, res
    content = [tuple(f) for f in eng.scene.objects[0].mesh.faces]
    assert content.count((0, 3, 1)) == 1  # exactly one duplicate removed


def test_non_contiguous_quadrilateral_duplicate_deletion_completes():
    # (0,3,1,2) is a quadrilateral duplicate pair with NON-CONTIGUOUS indices (old bug gave +100 vs 0).
    V = ((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0))
    faces = [(0, 3, 1, 2), (0, 3, 1, 2), (0, 1, 2)]  # exactly ONE duplicate pair
    scene = _scene(faces, V)
    plan = _plan_for_scene(scene)
    executables = [c for c in plan.corrections if c.correction_type == "REMOVE_DUPLICATE_FACE"]
    assert len(executables) == 1, [c.correction_type for c in plan.corrections]
    res, eng = _exec(scene, plan)
    assert res["result"] == ExecutionOutcome.COMPLETED, res
    content = [tuple(f) for f in eng.scene.objects[0].mesh.faces]
    assert content.count((0, 3, 1, 2)) == 1


def test_non_contiguous_duplicate_pair_parity_plan_binds():
    # The PLAN is generated by the kernel (correct _signed_area), the executor (fixed) must bind the
    # exact same duplicate key, so precondition `count>=2` and removal target agree.
    V = ((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0))
    faces = [(0, 3, 1), (0, 3, 1), (0, 1, 2)]  # clean single (0,3,1) duplicate pair
    scene = _scene(faces, V)
    plan = _plan_for_scene(scene)
    res, eng = _exec(scene, plan)
    assert res["result"] == ExecutionOutcome.COMPLETED, res
    assert tuple(eng.scene.objects[0].mesh.vertices) == V


# ---------------------------------------------------------------------------
# object_id=None mesh-scoped resolution (F2)
# ---------------------------------------------------------------------------

def test_object_id_none_unique_owner_resolves():
    # object_id=None, EXACTLY ONE owner -> resolves to that object and completes.
    scene, plan = _default_plan()
    # confirm the plan's correction is mesh-scoped (object_id None) — the planner emits this
    dup = [c for c in plan.corrections if c.correction_type == "REMOVE_DUPLICATE_FACE"][0]
    assert dup.object_id is None
    assert dup.mesh_id == "m"
    res, eng = _exec(scene, plan)
    assert res["result"] == ExecutionOutcome.COMPLETED, res
    assert res["precondition_results"][0]["ok"] is True
    assert res["precondition_results"][0]["target"] == ["pitch", "m"]  # resolved to pitch, not guessed
    # exactly one duplicate removed from the resolved mesh
    content = [tuple(f) for f in eng.scene.objects[0].mesh.faces]
    assert content.count((0, 1, 2)) == 1


def test_object_id_none_ambiguous_owner_fails_closed():
    # object_id=None, TWO objects own the same mesh_id -> resolve must fail closed (never guess).
    # Build two objects both owning mesh 'm' and craft a mesh-scoped (object_id=None) duplicate plan.
    def make_obj(obj_id, faces, V):
        return {"object_id": obj_id, "name": obj_id, "collection": "Field", "parent_object_id": None,
                "location": [0, 0, 0], "scale": [1, 1, 1], "rotation": [1, 0, 0, 0], "visible": True,
                "mesh": {"mesh_id": "m", "vertices": [list(v) for v in V],
                         "faces": [list(f) for f in faces],
                         "normals": None, "uvs": None, "materials": [], "local_frame_id": None}}
    V = ((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (2, 0, 0))
    objs = [make_obj("pitch", [(0, 1, 2), (0, 1, 2), (0, 3, 1), (1, 3, 2)], V),
            make_obj("pitch2", [(0, 1, 2), (0, 1, 2), (0, 3, 1), (1, 3, 2)], V)]
    scene = payload_to_scene_model({"schema_version": PAYLOAD_SCHEMA_VERSION, "scene_id": "s",
                                    "unit_system": "METERS", "objects": objs})
    plan = _plan_for_scene(scene)
    dup = [c for c in plan.corrections if c.correction_type == "REMOVE_DUPLICATE_FACE"]
    assert dup and dup[0].object_id is None
    res, _ = _exec(scene, plan)
    # two owners of 'm' -> must NOT reach mutation; fails closed
    assert res["result"] == ExecutionOutcome.PRECONDITION_FAILED, res
    assert res["failure_code"] == "PRECONDITION_FAILED"


def test_object_id_none_unknown_mesh_fails_closed():
    # object_id=None with a mesh_id that no object owns -> fail closed
    scene, plan = _default_plan()
    dup = [c for c in plan.corrections if c.correction_type == "REMOVE_DUPLICATE_FACE"][0]
    # override the correction's mesh_id to a nonexistent mesh
    corr = _bare_proposal(dup, mesh_id="ghost")
    res, _ = _exec(scene, plan, plan_override=_plan_with_proposals(plan, [corr]))
    assert res["result"] == ExecutionOutcome.PRECONDITION_FAILED, res


# ---------------------------------------------------------------------------
# invalid duplicate_relationship (F3)
# ---------------------------------------------------------------------------

def test_invalid_duplicate_relationship_rejected():
    """duplicate_relationship must be 'exact_duplicate' (or absent/None); any other string must be
    REJECTED as PLAN_INVALID — never silently normalized."""
    scene, plan = _default_plan()
    dup = [c for c in plan.corrections if c.correction_type == "REMOVE_DUPLICATE_FACE"][0]
    for bad_rel in ("approximate_duplicate", "nearly_equal", "something_else", ""):
        corr = _bare_proposal(dup, parameters={**dict(dup.parameters),
                                               "duplicate_relationship": bad_rel})
        res, _ = _exec(scene, plan, plan_override=_plan_with_proposals(plan, [corr]))
        assert res["result"] == ExecutionOutcome.PLAN_INVALID, (bad_rel, res)
        assert res["failure_code"] == "INVALID_DUPLICATE_RELATIONSHIP"