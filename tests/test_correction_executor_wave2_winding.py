"""Deterministic (non-live) tests for the WAVE-2 winding executor: REPAIR_FACE_WINDING ONLY.

Every test is in-memory and deterministic; NO live Blender, NO bpy, NO workflow runner. The bounded
mutation boundary is STUBBED with an in-memory SceneModel transform that implements the design's
normative primitive (rebuild the face table with the designated tuple replaced by its exact plain
reversal) — the live ``from_pydata`` adapter is a SEPARATE, later, live-validated milestone.

The plans and authorization artifacts here are REAL: plans come from the real planner (or, for the
adversary cases, from the real ``CorrectionPlan`` contract with ``plan_id`` RECOMPUTED from its own
contents — never a hand-forged digest string), the report digests are recomputed by the real
``SceneReport.digest()``, and the authorization artifacts are parsed and verified by the real
Slice-1 contract. Nothing bypasses integrity validation.
"""
import json

import pytest

from planning.blender.correction_authorization import (
    ACCEPTED_AUTHORIZATION_POLICY_VERSIONS,
    AUTHORIZATION_VERSION,
    parse_authorization,
    verify_authorization,
    PresentedWork,
)
from planning.blender.correction_contract import CorrectionPlan, CorrectionProposal
from planning.blender.correction_values import thaw_jsonable
from planning.blender.correction_executor import (
    ExecutionOutcome,
    execute_repair_face_winding,
)
import planning.blender.correction_executor as _ce
from planning.blender.correction_planner import _correction_id, plan_scene_report
from planning.blender.extraction_payload import PAYLOAD_SCHEMA_VERSION, payload_to_scene_model
from planning.blender.finding_codes import FindingCode, severity_of
from planning.blender.kernel import run_scene_health, soccer_field_profile_default
from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel
from planning.blender.scene_report import REPORT_FORMAT_VERSION, Finding

PROFILE = {
    "name": "soccer-field",
    "version": "1",
    "allowed_units": ["METERS", "meters", "m"],
    "name_pattern": r"^[a-z0-9][a-z0-9._-]*$",
}
WINDING = "REPAIR_FACE_WINDING"
ORIENTATION = "reverse_designated_face_to_shared_edge_opposite"

Q = ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1))
Q6 = Q + ((0, -1, 1),)
Q8 = Q6 + ((2, 0, 1),)


# ---------------------------------------------------------------------------
# fixtures: real scenes -> real kernel reports -> real plans
# ---------------------------------------------------------------------------

def _payload(faces, verts, *, object_id="o", mesh_id="m", scene_id="s", unit="METERS",
             extra_objects=()):
    obj = {
        "object_id": object_id, "name": object_id, "collection": "Field",
        "parent_object_id": None, "location": [0, 0, 0], "scale": [1, 1, 1],
        "rotation": [1, 0, 0, 0], "visible": True,
        "mesh": {"mesh_id": mesh_id, "vertices": [list(v) for v in verts],
                 "faces": [list(f) for f in faces], "normals": None, "uvs": None,
                 "materials": [], "local_frame_id": None},
    }
    objs = [obj] + list(extra_objects)
    return {"schema_version": PAYLOAD_SCHEMA_VERSION, "scene_id": scene_id,
            "unit_system": unit, "objects": objs}


def _unrelated_object(object_id="other", mesh_id="m2"):
    """An unrelated object whose state/topology must survive every winding execution (WC-Q11)."""
    return {
        "object_id": object_id, "name": "goal", "collection": "Goals",
        "parent_object_id": None, "location": [5, 0, 0], "scale": [1, 1, 1],
        "rotation": [1, 0, 0, 0], "visible": True,
        "mesh": {"mesh_id": mesh_id, "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                 "faces": [[0, 1, 2]], "normals": None, "uvs": None, "materials": [],
                 "local_frame_id": None},
    }


def _scene(faces, verts, **kwargs):
    kwargs.setdefault("extra_objects", (_unrelated_object(),))
    return payload_to_scene_model(_payload(faces, verts, **kwargs))


def _kernel_report(scene):
    return run_scene_health(scene, soccer_field_profile_default())


def _plan_for_scene(scene, **overrides):
    """A REAL plan produced by the REAL planner from a REAL kernel report."""
    report = _kernel_report(scene)
    payload = report.to_json_compatible()
    payload["digest"] = report.digest()
    payload["report_format_version"] = REPORT_FORMAT_VERSION
    return plan_scene_report(payload, profile=PROFILE, **overrides)


def _winding_corrections(plan):
    return [c for c in plan.corrections if c.correction_type == WINDING]


def _winding_correction(plan):
    corrections = _winding_corrections(plan)
    assert len(corrections) == 1, "expected exactly one winding correction"
    return corrections[0]


def _params(correction):
    """The correction's canonical parameters as JSON-native values (they are deep-frozen on the
    proposal, so ``recorded_edges`` is a tuple of tuples on the object itself)."""
    return thaw_jsonable(correction.parameters)


def _synthetic_plan(scene, parameters, *, mesh_id="m", object_id="o", finding_code=None):
    """A plan whose winding correction carries THESE parameters, with ``plan_id`` recomputed by the
    real contract from its own canonical contents.

    This models the design's threat model exactly (§3.1): ``plan_id`` proves the plan was not edited
    after construction — it proves NOTHING about provenance. A plan produced by a buggy/older planner
    or by an attacker who can write plans is self-consistent and integrity-valid, which is precisely
    why the executor re-derives WC-P15/P16/P17 instead of trusting the plan.
    """
    code = FindingCode.MESH_WINDING_INCONSISTENT if finding_code is None else finding_code
    correction_id = _correction_id(code, object_id, mesh_id, parameters)
    proposal = CorrectionProposal(
        correction_id=correction_id,
        finding_code=code.value,
        object_id=object_id,
        mesh_id=mesh_id,
        correction_type=WINDING,
        parameters=parameters,
        rationale="synthetic winding correction for an adversarial (integrity-valid) plan",
        preconditions=({"source_report_digest": _kernel_report(scene).digest()},
                       {"finding_code": code.value},
                       {"affected_entity": {"object_id": object_id, "mesh_id": mesh_id}}),
        expected_postcondition={"finding_cleared": code.value, "unrelated_topology_unchanged": True},
        risk="FIDELITY_GEOMETRY",
        severity=severity_of(code).value,
        reversibility="partially_reversible",
        dependencies=(),
        determinism="HEURISTIC",
        requires_human_review=True,
        out_of_scope=False,
    )
    return CorrectionPlan(
        plan_id="",  # recomputed deterministically by the contract from the contents
        source_report_digest=_kernel_report(scene).digest(),
        source_revision_id=None,
        planner_version="1",
        profile={"name": "soccer-field", "version": "1"},
        corrections=(proposal,),
        dependencies=(),
        summary_metrics={},
        state="REVIEW_REQUIRED",
        planning_errors=(),
    )


def _artifact(plan, correction, *, designation=None, expected_face_tuple=None, **overrides):
    artifact = {
        "authorization_version": AUTHORIZATION_VERSION,
        "authorization_policy_version": "1",
        "decision": "APPROVED",
        "correction_type": correction.correction_type,
        "correction_id": correction.correction_id,
        "plan_id": plan.plan_id,
        "source_report_digest": plan.source_report_digest,
        "authorized_by": "operator",
        "authorized_at_utc": "2026-09-11T12:00:00Z",
        "designated_face_index": designation,
    }
    if expected_face_tuple is not None:
        artifact["expected_face_tuple"] = list(expected_face_tuple)
    artifact.update(overrides)
    return artifact


class Engine:
    """Mutable holder wrapping an immutable SceneModel (the engine state under test)."""

    def __init__(self, scene):
        self.scene = scene


def _extractor(engine_state):
    scene = engine_state.scene
    return scene, _kernel_report(scene)


def _rebuild(engine_state, transform):
    scene = engine_state.scene
    engine_state.scene = SceneModel(
        scene_id=scene.scene_id, unit_system=scene.unit_system,
        objects=tuple(transform(o) for o in scene.objects),
    )


def _with_mesh(o, mesh):
    return ObjectModel(object_id=o.object_id, name=o.name, collection=o.collection,
                       parent_object_id=o.parent_object_id, location=o.location, scale=o.scale,
                       rotation=o.rotation, visible=o.visible, mesh=mesh)


class Counter:
    """Counts mutator invocations and records the kwargs of each one."""

    def __init__(self, fn):
        self.fn = fn
        self.calls = []

    def __call__(self, engine_state, **kwargs):
        self.calls.append(kwargs)
        return self.fn(engine_state, **kwargs)


def _reverse(face):
    return tuple(face[i] for i in range(len(face) - 1, -1, -1))


def _reverse_mutator(engine_state, *, object_id, mesh_id, face_index, face_tuple):
    """The normative primitive, in memory: replace ONLY the designated tuple with its reversal."""
    def transform(o):
        if o.object_id != object_id:
            return o
        faces = [tuple(f) for f in o.mesh.faces]
        assert tuple(faces[face_index]) == tuple(face_tuple)
        faces[face_index] = _reverse(faces[face_index])
        return _with_mesh(o, MeshModel(mesh_id=o.mesh.mesh_id, vertices=o.mesh.vertices,
                                       faces=tuple(faces), normals=o.mesh.normals, uvs=o.mesh.uvs,
                                       materials=o.mesh.materials,
                                       local_frame_id=o.mesh.local_frame_id))
    _rebuild(engine_state, transform)


def _rotate_mutator(engine_state, *, object_id, mesh_id, face_index, face_tuple):
    """Fraud: rotate the tuple instead of reversing it (a rotation is not a winding repair)."""
    def transform(o):
        if o.object_id != object_id:
            return o
        faces = [tuple(f) for f in o.mesh.faces]
        f = faces[face_index]
        faces[face_index] = tuple(f[1:] + f[:1])
        return _with_mesh(o, MeshModel(mesh_id=o.mesh.mesh_id, vertices=o.mesh.vertices,
                                       faces=tuple(faces)))
    _rebuild(engine_state, transform)


def _reverse_other_face_mutator(engine_state, *, object_id, mesh_id, face_index, face_tuple):
    """Fraud: reverse a DIFFERENT face than the designated one."""
    def transform(o):
        if o.object_id != object_id:
            return o
        faces = [tuple(f) for f in o.mesh.faces]
        other = 0 if face_index != 0 else 1
        faces[other] = _reverse(faces[other])
        return _with_mesh(o, MeshModel(mesh_id=o.mesh.mesh_id, vertices=o.mesh.vertices,
                                       faces=tuple(faces)))
    _rebuild(engine_state, transform)


def _vertex_fraud_mutator(engine_state, *, object_id, mesh_id, face_index, face_tuple):
    """Fraud: perform the reversal but ALSO move a vertex (WC-Q3)."""
    def transform(o):
        if o.object_id != object_id:
            return o
        verts = list(o.mesh.vertices)
        first = list(verts[0])
        first[0] = first[0] + 1.0
        verts[0] = tuple(first)
        faces = [tuple(f) for f in o.mesh.faces]
        faces[face_index] = _reverse(faces[face_index])
        return _with_mesh(o, MeshModel(mesh_id=o.mesh.mesh_id, vertices=tuple(verts),
                                       faces=tuple(faces)))
    _rebuild(engine_state, transform)


def _unrelated_fraud_mutator(engine_state, *, object_id, mesh_id, face_index, face_tuple):
    """Fraud: reverse the face AND rename an unrelated object (WC-Q11)."""
    def transform(o):
        if o.object_id == object_id:
            return _reverse_mutator.__wrapped_object__(o, face_index) if hasattr(
                _reverse_mutator, "__wrapped_object__") else _with_mesh(o, MeshModel(
                    mesh_id=o.mesh.mesh_id, vertices=o.mesh.vertices,
                    faces=tuple(tuple(f) for f in o.mesh.faces)))
        return ObjectModel(object_id=o.object_id, name=o.name + "_tampered", collection=o.collection,
                           parent_object_id=o.parent_object_id, location=o.location, scale=o.scale,
                           rotation=o.rotation, visible=o.visible, mesh=o.mesh)
    # perform the legitimate reversal first, then tamper with the unrelated object
    _reverse_mutator(engine_state, object_id=object_id, mesh_id=mesh_id, face_index=face_index,
                     face_tuple=face_tuple)
    _rebuild(engine_state, transform)


def _face_count_mutator(engine_state, *, object_id, mesh_id, face_index, face_tuple):
    """Fraud: reverse the face AND drop another face (WC-Q2)."""
    def transform(o):
        if o.object_id != object_id:
            return o
        faces = [tuple(f) for f in o.mesh.faces]
        faces[face_index] = _reverse(faces[face_index])
        kept = [f for i, f in enumerate(faces) if i != face_index or len(faces) == 1]
        return _with_mesh(o, MeshModel(mesh_id=o.mesh.mesh_id, vertices=o.mesh.vertices,
                                       faces=tuple(kept)))
    # remove the LAST face (not the target) so WC-Q2 fires before WC-Q1/WC-Q4
    def transform_two(o):
        if o.object_id != object_id:
            return o
        faces = [tuple(f) for f in o.mesh.faces]
        faces[face_index] = _reverse(faces[face_index])
        faces = faces[:-1]
        return _with_mesh(o, MeshModel(mesh_id=o.mesh.mesh_id, vertices=o.mesh.vertices,
                                       faces=tuple(faces)))
    _rebuild(engine_state, transform_two)


def _run(scene, plan, artifact, *, mutator=None, extractor=None, **kwargs):
    engine = Engine(scene)
    counted = Counter(mutator if mutator is not None else _reverse_mutator)
    result = execute_repair_face_winding(
        engine_state=engine,
        plan=plan,
        authorization=artifact,
        mutator=counted,
        extractor=extractor if extractor is not None else _extractor,
        **kwargs,
    )
    return result, engine, counted


# ---------------------------------------------------------------------------
# positive paths: fixture A (D2), fixture B (D1 x2), fixture G (D1 x3), fixture I
# ---------------------------------------------------------------------------

def _fixture_a():
    scene = _scene([(0, 1, 2), (0, 1, 3)], Q)
    return scene, _plan_for_scene(scene)


def _fixture_b():
    scene = _scene([(0, 1, 2), (0, 1, 3), (1, 2, 4)], Q)
    return scene, _plan_for_scene(scene)


def _fixture_g():
    scene = _scene([(0, 1, 2), (0, 1, 3), (1, 2, 4), (2, 0, 5)], Q6)
    return scene, _plan_for_scene(scene)


def test_fixture_a_d2_completes_with_exactly_one_reversal():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    assert correction.parameters["designated_face_index"] is None  # D2: the operator designates
    assert _params(correction)["candidate_faces"] == [0, 1]
    result, engine, counted = _run(scene, plan,
                                   _artifact(plan, correction, designation=0))
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert len(counted.calls) == 1, "exactly one mutator invocation, never a retry"
    mesh = engine.scene.objects[0].mesh
    assert tuple(mesh.faces[0]) == (2, 1, 0)          # exact plain reversal
    assert tuple(mesh.faces[1]) == (0, 1, 3)          # untouched
    assert tuple(mesh.vertices) == Q                  # vertex table unchanged


def test_fixture_b_d1_is_evidence_designated_and_resolves_both_edges():
    scene, plan = _fixture_b()
    correction = _winding_correction(plan)
    assert correction.parameters["designated_face_index"] == 0   # D1: evidence-designated
    assert correction.parameters["candidate_faces"] is None
    assert _params(correction)["recorded_edges"] == [[0, 1], [1, 2]]
    assert _params(correction)["counterpart_faces"] == [1, 2]
    result, engine, counted = _run(scene, plan, _artifact(plan, correction, designation=None))
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert len(counted.calls) == 1
    assert tuple(engine.scene.objects[0].mesh.faces[0]) == (2, 1, 0)
    assert result["pre_winding_findings"] == [
        {"edge": [0, 1], "faces": [0, 1]}, {"edge": [1, 2], "faces": [0, 2]}
    ]
    assert result["post_winding_findings"] == []


def test_fixture_g_d1_three_findings_one_reversal():
    scene, plan = _fixture_g()
    correction = _winding_correction(plan)
    assert _params(correction)["recorded_edges"] == [[0, 1], [0, 2], [1, 2]]
    assert _params(correction)["counterpart_faces"] == [1, 3, 2]
    result, engine, counted = _run(scene, plan, _artifact(plan, correction, designation=None))
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert len(counted.calls) == 1, "one reversal resolves three findings; scope stays ONE face"
    assert len(result["pre_winding_findings"]) == 3
    assert result["post_winding_findings"] == []


def test_fixture_i_matching_expected_face_tuple_is_accepted():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    result, engine, counted = _run(
        scene, plan, _artifact(plan, correction, designation=0, expected_face_tuple=(0, 1, 2)))
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert result["target_face"]["face_tuple_before"] == [0, 1, 2]
    assert result["target_face"]["face_tuple_after"] == [2, 1, 0]
    assert len(counted.calls) == 1


def test_mismatching_expected_face_tuple_is_refused_before_any_mutation():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    result, _engine, counted = _run(
        scene, plan, _artifact(plan, correction, designation=0, expected_face_tuple=(0, 1, 5)))
    assert result["result"] == ExecutionOutcome.AUTHORIZATION_SCOPE_MISMATCH
    assert result["failure_code"] == "EXPECTED_FACE_TUPLE_MISMATCH"
    assert counted.calls == [], "an authorization mismatch must never reach the mutator"


def test_artifact_may_be_presented_as_canonical_json_text():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    artifact = parse_authorization(_artifact(plan, correction, designation=0))
    result, _engine, counted = _run(scene, plan, artifact.canonical_json())
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert result["authorization_digest"] == artifact.digest()
    assert len(counted.calls) == 1


# ---------------------------------------------------------------------------
# receipt honesty (design §8)
# ---------------------------------------------------------------------------

def test_receipt_is_evidence_backed_and_claims_no_authority():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    result, _engine, _counted = _run(scene, plan, _artifact(plan, correction, designation=0))
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert result["receipt_version"] == "1"
    assert result["normal_agreement_not_verified"] is True   # never claims normal correctness
    assert result["persisted"] is False
    assert result["rollback_performed"] is False
    assert result["topology_only_orientation_repair"] is True
    assert result["authorization_verified"] is True
    assert result["authorization_policy_version"] == "1"
    assert result["correction_id"] == correction.correction_id
    assert result["plan_id"] == plan.plan_id
    assert result["plan_id_recomputed"] == plan.plan_id
    assert result["source_report_digest"] == plan.source_report_digest
    assert result["source_report_digest_recomputed"] == plan.source_report_digest
    assert result["executed_correction_ids"] == [correction.correction_id]
    assert result["recorded_edges"] == [[0, 1]]
    assert result["counterpart_faces"] == [
        {"index": 1, "edge": [0, 1], "face_tuple": [0, 1, 3]}
    ]
    assert result["failure_code"] is None
    assert result["postcondition_results"] == []
    # the receipt is JSON-serializable audit data with no callables/objects smuggled in
    assert json.loads(json.dumps(result)) == result


def test_receipt_never_claims_normal_correctness_on_failure_paths():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    for artifact in (None, _artifact(plan, correction, designation=0, decision="REJECTED"),
                     _artifact(plan, correction, designation=1)):
        result, _engine, counted = _run(scene, plan, artifact)
        assert result["result"] != ExecutionOutcome.COMPLETED
        assert result["normal_agreement_not_verified"] is True
        assert result["persisted"] is False
        assert result["rollback_performed"] is False
        assert result["authorization_verified"] is False
        assert counted.calls == []


def test_a_receipt_cannot_be_replayed_as_an_authorization():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    result, _engine, _counted = _run(scene, plan, _artifact(plan, correction, designation=0))
    assert result["result"] == ExecutionOutcome.COMPLETED
    replayed, _engine2, counted = _run(scene, plan, result)
    assert replayed["result"] == ExecutionOutcome.AUTHORIZATION_INVALID
    assert counted.calls == []


# ---------------------------------------------------------------------------
# authorization negatives (fixture F cases 1-11) — all BEFORE any mutation
# ---------------------------------------------------------------------------

def test_no_artifact_is_authorization_required():
    scene, plan = _fixture_a()
    result, _engine, counted = _run(scene, plan, None)
    assert result["result"] == ExecutionOutcome.AUTHORIZATION_REQUIRED
    assert result["failure_code"] == "AUTHORIZATION_REQUIRED"
    assert counted.calls == []


def test_d2_without_a_designation_is_authorization_required():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    result, _engine, counted = _run(scene, plan, _artifact(plan, correction, designation=None))
    assert result["result"] == ExecutionOutcome.AUTHORIZATION_REQUIRED
    assert result["failure_code"] == "DESIGNATION_REQUIRED"
    assert counted.calls == []


def test_wrong_correction_id_is_a_scope_mismatch():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    result, _engine, counted = _run(
        scene, plan, _artifact(plan, correction, designation=0, correction_id="other-correction"))
    assert result["result"] == ExecutionOutcome.AUTHORIZATION_SCOPE_MISMATCH
    assert result["failure_code"] == "CORRECTION_ID_MISMATCH"
    assert counted.calls == []


def test_wrong_plan_id_is_a_scope_mismatch():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    result, _engine, counted = _run(
        scene, plan, _artifact(plan, correction, designation=0, plan_id="a" * 64))
    assert result["result"] == ExecutionOutcome.AUTHORIZATION_SCOPE_MISMATCH
    assert result["failure_code"] == "PLAN_ID_MISMATCH"
    assert counted.calls == []


def test_wrong_source_digest_is_a_scope_mismatch():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    result, _engine, counted = _run(
        scene, plan, _artifact(plan, correction, designation=0, source_report_digest="b" * 64))
    assert result["result"] == ExecutionOutcome.AUTHORIZATION_SCOPE_MISMATCH
    assert result["failure_code"] == "SOURCE_DIGEST_MISMATCH"
    assert counted.calls == []


def test_wrong_correction_type_is_refused():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    result, _engine, counted = _run(
        scene, plan, _artifact(plan, correction, designation=0, correction_type="RENAME_OBJECT"))
    assert result["result"] == ExecutionOutcome.AUTHORIZATION_INVALID
    assert counted.calls == []


def test_unaccepted_policy_version_and_non_approved_decision_are_invalid():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    assert ACCEPTED_AUTHORIZATION_POLICY_VERSIONS == frozenset({"1"})
    for overrides, expected in (({"authorization_policy_version": "2"}, "UNSUPPORTED_POLICY_VERSION"),
                                ({"decision": "REJECTED"}, "DECISION_NOT_APPROVED")):
        result, _engine, counted = _run(
            scene, plan, _artifact(plan, correction, designation=0, **overrides))
        assert result["result"] == ExecutionOutcome.AUTHORIZATION_INVALID
        assert result["failure_code"] == expected
        assert counted.calls == []


def test_malformed_artifact_is_invalid():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    for bad in ("{not json", [1, 2, 3], 5, {"decision": "APPROVED"}):
        result, _engine, counted = _run(scene, plan, bad)
        assert result["result"] == ExecutionOutcome.AUTHORIZATION_INVALID
        assert counted.calls == []


def test_d2_designation_outside_the_candidate_pair_is_a_scope_mismatch():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    result, _engine, counted = _run(scene, plan, _artifact(plan, correction, designation=7))
    assert result["result"] == ExecutionOutcome.AUTHORIZATION_SCOPE_MISMATCH
    assert result["failure_code"] == "DESIGNATION_NOT_IN_CANDIDATE_PAIR"
    assert counted.calls == []


def test_d1_artifact_supplying_a_designation_is_a_scope_mismatch():
    scene, plan = _fixture_b()          # D1: evidence-designated by the plan
    correction = _winding_correction(plan)
    result, _engine, counted = _run(scene, plan, _artifact(plan, correction, designation=1))
    assert result["result"] == ExecutionOutcome.AUTHORIZATION_SCOPE_MISMATCH
    assert result["failure_code"] == "DESIGNATION_SUPPLIED_FOR_D1"
    assert counted.calls == []


def test_d2_designating_the_recorded_counterpart_is_refused_by_the_counterpart_rule():
    """The recorded counterpart fixes which candidate member is designatable (design §2.2/§6 P8):
    designating the counterpart itself would make the pair's 'counterpart' the target, which the
    explicit ``counterpart != designated_face`` rule refuses before any mutation."""
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    assert _params(correction)["counterpart_faces"] == [1]
    result, _engine, counted = _run(scene, plan, _artifact(plan, correction, designation=1))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert result["failure_code"] == "PRECONDITION_FAILED"
    assert "COUNTERPART_EQUALS_DESIGNATED_FACE" in result["precondition_results"][0]["reason"]
    assert counted.calls == []


# ---------------------------------------------------------------------------
# plan / source integrity
# ---------------------------------------------------------------------------

def test_tampered_plan_id_is_rejected():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)

    class TamperedPlan:
        def __init__(self, inner):
            self._inner = inner
            self.source_report_digest = inner.source_report_digest
            self.plan_id = "0" * 64
            self.corrections = inner.corrections

        def _compute_plan_id(self):
            return self._inner._compute_plan_id()

    result, _engine, counted = _run(scene, TamperedPlan(plan),
                                    _artifact(plan, correction, designation=0))
    assert result["result"] == ExecutionOutcome.PLAN_INVALID
    assert result["failure_code"] == "PLAN_ID_MISMATCH"
    assert counted.calls == []


def test_plan_without_a_winding_correction_is_refused():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    proposal = CorrectionProposal(
        correction_id="DUPLICATE-REMOVAL-x",
        finding_code=FindingCode.MESH_DUPLICATE_FACE.value,
        object_id="o", mesh_id="m", correction_type="REMOVE_DUPLICATE_FACE",
        parameters={"mesh_id": "m", "face_ids": [0, 1], "duplicate_relationship": "exact_duplicate"},
        rationale="not a winding correction", preconditions=(),
        expected_postcondition={}, risk="FIDELITY_SAFE",
        severity=severity_of(FindingCode.MESH_DUPLICATE_FACE).value, reversibility="reversible",
        dependencies=(), determinism="DETERMINISTIC", requires_human_review=False, out_of_scope=False,
    )
    other = CorrectionPlan(plan_id="", source_report_digest=plan.source_report_digest,
                           source_revision_id=None, planner_version="1",
                           profile={"name": "soccer-field", "version": "1"},
                           corrections=(proposal,), dependencies=(), summary_metrics={},
                           state="AUTO_PROPOSALS_AVAILABLE", planning_errors=())
    result, _engine, counted = _run(scene, other, _artifact(plan, correction, designation=0))
    assert result["result"] == ExecutionOutcome.PLAN_INVALID
    assert result["failure_code"] == "NO_EXECUTABLE_CORRECTION"
    assert counted.calls == []


def test_multi_executable_winding_plan_is_refused():
    """Two aggregated winding corrections (two meshes) must be split by the operator (design §2.6)."""
    second = _unrelated_object(object_id="other", mesh_id="m2")
    second["mesh"]["vertices"] = [list(v) for v in Q]
    second["mesh"]["faces"] = [[0, 1, 2], [0, 1, 3]]
    scene_two = payload_to_scene_model(_payload(
        [(0, 1, 2), (0, 1, 3)], Q, object_id="o", mesh_id="m",
        extra_objects=(second,)))
    plan = _plan_for_scene(scene_two)
    assert len(_winding_corrections(plan)) == 2
    correction = _winding_corrections(plan)[0]
    result, _engine, counted = _run(scene_two, plan, _artifact(plan, correction, designation=None))
    assert result["result"] == ExecutionOutcome.PLAN_INVALID
    assert result["failure_code"] == "AMBIGUOUS_MULTIPLE_EXECUTABLE_CORRECTIONS"
    assert counted.calls == []


def test_winding_parameters_must_pass_the_operation_allowlist():
    scene, _plan = _fixture_a()
    cases = (
        ({"mesh_id": "m", "designated_face_index": 0, "candidate_faces": None,
          "recorded_edges": [[0, 1]], "counterpart_faces": [1],
          "orientation": ORIENTATION, "extra_authority": True}, "UNEXPECTED_PARAMETER:extra_authority"),
        ({"mesh_id": "m", "designated_face_index": 0, "candidate_faces": None,
          "recorded_edges": [[0, 1]], "counterpart_faces": [1],
          "orientation": "repair_to_shared_edge_opposite"}, "INVALID_WINDING_ORIENTATION"),
        ({"mesh_id": "m", "designated_face_index": 0, "candidate_faces": None,
          "recorded_edges": [[0, 1]], "counterpart_faces": [1]}, "MISSING_PARAMETER:orientation"),
        ({"mesh_id": "m", "designated_face_index": 0, "candidate_faces": [0, 1],
          "recorded_edges": [[0, 1]], "counterpart_faces": [1], "orientation": ORIENTATION},
         "DESIGNATION_AND_CANDIDATES_BOTH_PRESENT"),
        ({"mesh_id": "m", "designated_face_index": None, "candidate_faces": [0, 0],
          "recorded_edges": [[0, 1]], "counterpart_faces": [1], "orientation": ORIENTATION},
         "INVALID_CANDIDATE_FACES"),
        ({"mesh_id": "m", "designated_face_index": 0, "candidate_faces": None,
          "recorded_edges": [], "counterpart_faces": [], "orientation": ORIENTATION},
         "INVALID_RECORDED_EDGES"),
        ({"mesh_id": "m", "designated_face_index": 0, "candidate_faces": None,
          "recorded_edges": [[0, 1]], "counterpart_faces": [], "orientation": ORIENTATION},
         "INVALID_COUNTERPART_FACES"),
        ({"mesh_id": "", "designated_face_index": 0, "candidate_faces": None,
          "recorded_edges": [[0, 1]], "counterpart_faces": [1], "orientation": ORIENTATION},
         "INVALID_MESH_ID"),
    )
    for parameters, expected in cases:
        plan = _synthetic_plan(scene, parameters)
        result, _engine, counted = _run(scene, plan, _artifact(plan, plan.corrections[0],
                                                              designation=None))
        assert result["result"] == ExecutionOutcome.PLAN_INVALID, parameters
        assert result["failure_code"] == expected
        assert counted.calls == []


def test_source_mismatch_is_rejected_before_any_mutation():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    other_scene = _scene([(0, 1, 2), (0, 1, 3)], Q, scene_id="different")
    result, _engine, counted = _run(other_scene, plan,
                                    _artifact(plan, correction, designation=0))
    assert result["result"] == ExecutionOutcome.SOURCE_MISMATCH
    assert result["failure_code"] == "SOURCE_DIGEST_MISMATCH"
    assert counted.calls == []


def test_extraction_failure_fails_closed():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)

    def boom(_engine_state):
        raise RuntimeError("engine unavailable")

    result, _engine, counted = _run(scene, plan, _artifact(plan, correction, designation=0),
                                    extractor=boom)
    assert result["result"] == ExecutionOutcome.SOURCE_MISMATCH
    assert result["failure_code"] == "EXTRACTION_FAILED"
    assert counted.calls == []


def test_replay_after_the_scene_changed_is_rejected():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    artifact = _artifact(plan, correction, designation=0)
    first, engine, _counted = _run(scene, plan, artifact)
    assert first["result"] == ExecutionOutcome.COMPLETED
    # re-present the SAME plan+artifact against the now-mutated scene
    engine.scene = engine.scene  # unchanged reference; the digest of the state has changed
    second = execute_repair_face_winding(engine_state=engine, plan=plan, authorization=artifact,
                                         mutator=_reverse_mutator, extractor=_extractor)
    assert second["result"] == ExecutionOutcome.SOURCE_MISMATCH
    assert second["failure_code"] == "SOURCE_DIGEST_MISMATCH"


# ---------------------------------------------------------------------------
# precondition negatives reached through the REAL executor path
# ---------------------------------------------------------------------------

def test_wc_p6_unknown_target_mesh_fails_closed():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    parameters = _params(correction)
    parameters["mesh_id"] = "does-not-exist"
    synthetic = _synthetic_plan(scene, parameters)
    result, _engine, counted = _run(scene, synthetic,
                                    _artifact(synthetic, synthetic.corrections[0], designation=0))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert "WC-P6" in result["precondition_results"][0]["reason"]
    assert counted.calls == []


def test_wc_p7_out_of_range_designated_face_fails_closed():
    scene, _plan = _fixture_a()
    parameters = {"mesh_id": "m", "designated_face_index": 9, "candidate_faces": None,
                  "recorded_edges": [[0, 1]], "counterpart_faces": [1], "orientation": ORIENTATION}
    synthetic = _synthetic_plan(scene, parameters)
    result, _engine, counted = _run(scene, synthetic,
                                    _artifact(synthetic, synthetic.corrections[0], designation=None))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert "WC-P7" in result["precondition_results"][0]["reason"]
    assert counted.calls == []


def test_wc_p14_duplicate_target_is_refused_before_mutation():
    """A plan (integrity-valid) whose winding target participates in a duplicate pair is refused:
    reversing one member of a duplicate pair would MASK the duplicate (design §6 P14)."""
    scene = _scene([(0, 1, 2), (1, 2, 0), (0, 1, 3)], Q)
    report = _kernel_report(scene)
    codes = sorted({f.code.value for f in report.findings})
    assert "MESH_DUPLICATE_FACE" in codes
    parameters = {"mesh_id": "m", "designated_face_index": None, "candidate_faces": [0, 1],
                  "recorded_edges": [[0, 1]], "counterpart_faces": [1], "orientation": ORIENTATION}
    synthetic = _synthetic_plan(scene, parameters)
    result, _engine, counted = _run(scene, synthetic,
                                    _artifact(synthetic, synthetic.corrections[0], designation=0))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert "WC-P14" in result["precondition_results"][0]["reason"]
    assert "DUPLICATE" in result["precondition_results"][0]["reason"]
    assert counted.calls == [], "the duplicate-masking flip must never happen"


def test_wc_p14_degenerate_target_is_refused_before_mutation():
    # vertices chosen so that face 0 (0,1,2) has exactly zero projected area
    verts = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    scene = _scene([(0, 1, 2), (0, 1, 3)], verts)
    report = _kernel_report(scene)
    assert any(f.code.value == "MESH_DEGENERATE_FACE" for f in report.findings)
    parameters = {"mesh_id": "m", "designated_face_index": None, "candidate_faces": [0, 1],
                  "recorded_edges": [[0, 1]], "counterpart_faces": [1], "orientation": ORIENTATION}
    synthetic = _synthetic_plan(scene, parameters)
    result, _engine, counted = _run(scene, synthetic,
                                    _artifact(synthetic, synthetic.corrections[0], designation=0))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert "WC-P14" in result["precondition_results"][0]["reason"]
    assert "DEGENERATE" in result["precondition_results"][0]["reason"]
    assert counted.calls == []


def test_wc_p17_under_declared_recorded_set_is_refused():
    """Fixture B's fresh report has edges (0,1) and (1,2); a plan declaring only (0,1) is refused."""
    scene, plan = _fixture_b()
    correction = _winding_correction(plan)
    parameters = {"mesh_id": "m", "designated_face_index": None, "candidate_faces": [0, 1],
                  "recorded_edges": [[0, 1]], "counterpart_faces": [1], "orientation": ORIENTATION}
    synthetic = _synthetic_plan(scene, parameters)
    result, _engine, counted = _run(scene, synthetic,
                                    _artifact(synthetic, synthetic.corrections[0], designation=0))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert "WC-P17" in result["precondition_results"][0]["reason"]
    assert counted.calls == []
    assert correction.correction_type == WINDING


def test_wc_p17_over_declared_recorded_set_is_refused():
    scene, plan = _fixture_b()
    parameters = {"mesh_id": "m", "designated_face_index": None, "candidate_faces": [0, 1],
                  "recorded_edges": [[0, 1], [1, 2], [2, 3]], "counterpart_faces": [1, 2, 3],
                  "orientation": ORIENTATION}
    synthetic = _synthetic_plan(scene, parameters)
    result, _engine, counted = _run(scene, synthetic,
                                    _artifact(synthetic, synthetic.corrections[0], designation=0))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert "WC-P17" in result["precondition_results"][0]["reason"]
    assert counted.calls == []


def test_wc_p17_wrong_counterpart_is_refused():
    scene, plan = _fixture_a()
    parameters = {"mesh_id": "m", "designated_face_index": None, "candidate_faces": [0, 1],
                  "recorded_edges": [[0, 1]], "counterpart_faces": [3], "orientation": ORIENTATION}
    synthetic = _synthetic_plan(scene, parameters)
    result, _engine, counted = _run(scene, synthetic,
                                    _artifact(synthetic, synthetic.corrections[0], designation=0))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert "WC-P17" in result["precondition_results"][0]["reason"]
    assert counted.calls == []


def test_wc_p15_wrong_designated_face_is_refused():
    """D1 designating a face that is NOT the recomputed intersection (design §6.1 row 4).

    On this path the refusal is dual-covered and the FIRST predicate to fire is WC-P17's recorded-set
    agreement (a designation outside the recorded pair is visible there); WC-P15's own
    complete-coverage/intersection branch is exercised in the predicate test below. Either way: the
    operation is refused BEFORE any mutation.
    """
    scene, _plan = _fixture_b()          # fresh pairs {0,1} and {0,2}: the intersection is {0}
    parameters = {"mesh_id": "m", "designated_face_index": 1, "candidate_faces": None,
                  "recorded_edges": [[0, 1], [1, 2]], "counterpart_faces": [0, 2],
                  "orientation": ORIENTATION}
    synthetic = _synthetic_plan(scene, parameters)
    result, _engine, counted = _run(scene, synthetic,
                                    _artifact(synthetic, synthetic.corrections[0], designation=None))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    reason = result["precondition_results"][0]["reason"]
    assert ("WC-P15" in reason) or ("WC-P17" in reason), reason
    assert counted.calls == []


def test_wc_p15_complete_coverage_branch_fires_when_the_intersection_is_not_the_designation():
    """WC-P15's second condition (the recomputed intersection must EQUAL the designation) is
    exercised directly: with two fresh findings that share the same pair, designation 1 is covered by
    every finding yet the intersection is {0,1} != {1}. A real manifold mesh cannot produce two
    findings with an identical pair (two polygons share at most one edge), so — exactly as the
    design's own reference-predicate falsification suite did — the predicate is fed a synthetic
    report. It must fail closed, and it does so BEFORE any mutation."""
    scene, plan = _fixture_a()
    report = _kernel_report(scene)

    class FakeFinding:
        def __init__(self, edge, pair):
            self.code = FindingCode.MESH_WINDING_INCONSISTENT
            self.mesh_id = "m"
            self.measured = {"edge": list(edge), "faces": list(pair)}

    class FakeReport:
        findings = (FakeFinding((0, 1), (0, 1)), FakeFinding((1, 2), (0, 1)))

    with pytest.raises(_ce.WindingPredicateError) as excinfo:
        _ce._verify_winding_preconditions(
            scene, FakeReport(),
            object_id="o", mesh_id="m", designated_face_index=1,
            recorded_edges=[[0, 1], [1, 2]], counterpart_faces=[0, 0],
            selection_mode="D1",
        )
    assert excinfo.value.predicate_id == "WC-P15"
    assert "intersection" in excinfo.value.reason
    assert _winding_correction(plan).correction_type == WINDING


def test_wc_p16_d2_requires_exactly_one_fresh_finding():
    """A D2 claim (the artifact designates, the plan designates nothing) on a mesh whose fresh
    report has TWO findings is refused by WC-P16 — with the recorded set declared completely, so
    WC-P17 passes and WC-P16 is the predicate that fires."""
    scene, _plan = _fixture_b()      # fresh: edge (0,1)->pair {0,1}, edge (1,2)->pair {0,2}
    parameters = {"mesh_id": "m", "designated_face_index": None, "candidate_faces": [0, 1],
                  "recorded_edges": [[0, 1], [1, 2]], "counterpart_faces": [1, 2],
                  "orientation": ORIENTATION}
    synthetic = _synthetic_plan(scene, parameters)
    # the artifact designates 0 (a member of the candidate pair and of both fresh pairs), so the
    # authorization gate passes, WC-P17 agrees (complete recorded set, aligned counterparts) and
    # only the D2 aggregation invariant is violated.
    result, _engine, counted = _run(scene, synthetic,
                                    _artifact(synthetic, synthetic.corrections[0], designation=0))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    reason = result["precondition_results"][0]["reason"]
    assert "WC-P16" in reason, reason
    assert counted.calls == []


def test_duplicate_fresh_edge_is_refused_on_the_executor_path():
    """A fresh report that attributes ONE canonical edge to TWO different pairs is refused before
    mutation: the recomputed edge set cannot be mapped positionally, and the Slice-1 contract
    rejects the duplicate fresh edge inside WC-P17."""
    scene, _plan = _fixture_a()
    real_report = _kernel_report(scene)
    duplicate_finding = type(real_report.findings[0])(
        code=real_report.findings[0].code, object_id="o", mesh_id="m",
        measured={"edge": [0, 1], "faces": [2, 3]}, message="duplicate fresh edge")
    dup_report = type(real_report)(
        scene_id=real_report.scene_id, validation_state=real_report.validation_state,
        findings=tuple(real_report.findings) + (duplicate_finding,),
        scene_metrics={}, profile_name=real_report.profile_name, input_digest=None,
        source_revision_id=None)
    parameters = {"mesh_id": "m", "designated_face_index": None, "candidate_faces": [0, 1],
                  "recorded_edges": [[0, 1]], "counterpart_faces": [1], "orientation": ORIENTATION}
    synthetic = _synthetic_plan(scene, parameters)
    synthetic = CorrectionPlan(plan_id="", source_report_digest=dup_report.digest(),
                               source_revision_id=None, planner_version="1",
                               profile={"name": "soccer-field", "version": "1"},
                               corrections=synthetic.corrections, dependencies=(),
                               summary_metrics={}, state="REVIEW_REQUIRED", planning_errors=())
    result, _engine, counted = _run(
        scene, synthetic, _artifact(synthetic, synthetic.corrections[0], designation=0),
        extractor=lambda engine_state: (engine_state.scene, dup_report))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    reason = result["precondition_results"][0]["reason"]
    assert "WC-P17" in reason, reason
    assert counted.calls == []


def test_wc_p9_edge_not_shared_by_the_recorded_pair_is_refused():
    """The report claims edge (0,1) but the SceneModel shares it with a THIRD face (non-manifold)."""
    scene = _scene([(0, 1, 2), (0, 1, 3), (1, 0, 3)], Q)
    parameters = {"mesh_id": "m", "designated_face_index": None, "candidate_faces": [0, 1],
                  "recorded_edges": [[0, 1]], "counterpart_faces": [1], "orientation": ORIENTATION}
    synthetic = _synthetic_plan(scene, parameters)
    result, _engine, counted = _run(scene, synthetic,
                                    _artifact(synthetic, synthetic.corrections[0], designation=0))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    reason = result["precondition_results"][0]["reason"]
    assert ("WC-P9" in reason) or ("WC-P17" in reason) or ("WC-P11" in reason), reason
    assert counted.calls == []


def test_wc_p11_incomplete_recorded_set_for_the_target_face_is_refused():
    """Fixture G's target face 0 has THREE same-direction shared edges; declaring fewer is refused."""
    scene, _plan = _fixture_g()
    parameters = {"mesh_id": "m", "designated_face_index": 0, "candidate_faces": None,
                  "recorded_edges": [[0, 1], [0, 2]], "counterpart_faces": [1, 3],
                  "orientation": ORIENTATION}
    synthetic = _synthetic_plan(scene, parameters)
    result, _engine, counted = _run(scene, synthetic,
                                    _artifact(synthetic, synthetic.corrections[0], designation=None))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    reason = result["precondition_results"][0]["reason"]
    assert ("WC-P11" in reason) or ("WC-P17" in reason), reason
    assert counted.calls == []


# ---------------------------------------------------------------------------
# postcondition negatives: the mutation happens, is verified, and fails closed
# ---------------------------------------------------------------------------

def test_wc_q1_rotation_instead_of_plain_reversal_is_rejected():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    result, engine, counted = _run(scene, plan, _artifact(plan, correction, designation=0),
                                   mutator=_rotate_mutator)
    assert result["result"] == ExecutionOutcome.POSTCONDITION_FAILED
    assert result["failure_code"] == "WC-Q1"
    assert len(counted.calls) == 1, "one attempt, never a retry"
    assert result["target_face"]["face_tuple_after"] == [1, 2, 0]   # observed, not claimed valid


def test_wc_q1_reversing_a_different_face_is_rejected():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    result, _engine, counted = _run(scene, plan, _artifact(plan, correction, designation=0),
                                    mutator=_reverse_other_face_mutator)
    assert result["result"] == ExecutionOutcome.POSTCONDITION_FAILED
    assert result["failure_code"] in ("WC-Q1", "WC-Q4")
    assert len(counted.calls) == 1


def test_fixture_d_cascade_is_caught_by_q6():
    """Fixture D: the reversal resolves the recorded edge (Q5 passes) but creates a NEW
    inconsistency, so the operation fails on WC-Q6 alone (design §12.2)."""
    scene = _scene([(0, 1, 2), (0, 1, 3), (2, 1, 4)], Q)
    plan = _plan_for_scene(scene)
    correction = _winding_correction(plan)
    assert _params(correction)["recorded_edges"] == [[0, 1]]
    result, engine, counted = _run(scene, plan, _artifact(plan, correction, designation=0))
    assert result["result"] == ExecutionOutcome.POSTCONDITION_FAILED
    assert result["failure_code"] == "WC-Q6"
    assert len(counted.calls) == 1, "no retry, no second flip, no cascade repair"
    assert result["post_winding_findings"] == [{"edge": [1, 2], "faces": [0, 2]}]
    assert tuple(engine.scene.objects[0].mesh.faces[0]) == (2, 1, 0)


def test_wc_q3_vertex_change_is_rejected():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    result, _engine, counted = _run(scene, plan, _artifact(plan, correction, designation=0),
                                    mutator=_vertex_fraud_mutator)
    assert result["result"] == ExecutionOutcome.POSTCONDITION_FAILED
    assert result["failure_code"] == "WC-Q3"
    assert len(counted.calls) == 1


def test_wc_q2_face_count_change_is_rejected():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    result, _engine, counted = _run(scene, plan, _artifact(plan, correction, designation=0),
                                    mutator=_face_count_mutator)
    assert result["result"] == ExecutionOutcome.POSTCONDITION_FAILED
    assert result["failure_code"] == "WC-Q2"
    assert len(counted.calls) == 1


def test_wc_q11_unrelated_object_change_is_rejected():
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    result, _engine, counted = _run(scene, plan, _artifact(plan, correction, designation=0),
                                    mutator=_unrelated_fraud_mutator)
    assert result["result"] == ExecutionOutcome.POSTCONDITION_FAILED
    assert result["failure_code"] == "WC-Q11"
    assert len(counted.calls) == 1


def test_unrelated_and_vertex_state_survive_a_legitimate_execution():
    scene, plan = _fixture_b()
    correction = _winding_correction(plan)
    before_unrelated = scene.objects[1]
    result, engine, _counted = _run(scene, plan, _artifact(plan, correction, designation=None))
    assert result["result"] == ExecutionOutcome.COMPLETED
    after_unrelated = engine.scene.objects[1]
    assert after_unrelated.mesh == before_unrelated.mesh
    assert (after_unrelated.name, after_unrelated.collection, after_unrelated.location
            ) == (before_unrelated.name, before_unrelated.collection, before_unrelated.location)
    assert tuple(engine.scene.objects[0].mesh.vertices) == Q


def test_q13_backstop_fires_on_a_surviving_pre_existing_finding():
    """WC-Q13 is the report-level backstop (design §7). With WC-P15 enforced a surviving finding is
    unreachable, so the predicate is exercised directly with a synthetic surviving finding to prove
    it fires and is reported as WC-Q13 — never as a success."""
    # fixture D: reversing face 0 RESOLVES edge (0,1) and CREATES a same-direction pair on edge
    # (1,2) — that created identity is used as the "pre-existing, surviving" finding, which is
    # exactly the Q13 failure mode (present before AND after).
    scene = _scene([(0, 1, 2), (0, 1, 3), (2, 1, 4)], Q)
    plan = _plan_for_scene(scene)
    correction = _winding_correction(plan)
    snapshot = {
        "scene_id": scene.scene_id,
        "unit_system": scene.unit_system,
        "ordered_object_ids": tuple(o.object_id for o in scene.objects),
        "target_object_state": _ce._object_state_key(scene.objects[0]),
        "target": {"object_id": "o", "mesh_id": "m",
                   "ordered_vertex_table": tuple(scene.objects[0].mesh.vertices),
                   "ordered_face_tuples": tuple(scene.objects[0].mesh.faces)},
        "unrelated": {o.object_id: (_ce._object_state_key(o), _ce._mesh_state_key(o.mesh))
                      for o in scene.objects[1:]},
        "source_report_digest": plan.source_report_digest,
        "source_report": _kernel_report(scene),
    }
    surviving = (((1, 2), (0, 2)),)

    def _reversed_target(o):
        if o.object_id != "o":
            return o
        faces = [tuple(f) for f in o.mesh.faces]
        faces[0] = _reverse(faces[0])
        return _with_mesh(o, MeshModel(mesh_id=o.mesh.mesh_id, vertices=o.mesh.vertices,
                                       faces=tuple(faces)))

    mutated = SceneModel(scene_id=scene.scene_id, unit_system=scene.unit_system,
                         objects=tuple(_reversed_target(o) for o in scene.objects))
    with pytest.raises(_ce.WindingPostconditionError) as excinfo:
        _ce._verify_winding_postconditions(
            mutated, _kernel_report(mutated), snapshot,
            object_id="o", mesh_id="m", face_index=0,
            pre_face=tuple(scene.objects[0].mesh.faces[0]),
            recorded_edges=((0, 1),), counterpart_faces=(1,),
            pre_winding=surviving,
        )
    assert excinfo.value.predicate_id == "WC-Q13"
    assert "SURVIVED" in excinfo.value.reason


# ---------------------------------------------------------------------------
# determinism / repeatability / authority isolation
# ---------------------------------------------------------------------------

def test_two_identical_executions_produce_byte_identical_receipts():
    scene_a, plan_a = _fixture_g()
    scene_b, plan_b = _fixture_g()
    correction_a = _winding_correction(plan_a)
    correction_b = _winding_correction(plan_b)
    first, engine_a, _c1 = _run(scene_a, plan_a, _artifact(plan_a, correction_a, designation=None))
    second, engine_b, _c2 = _run(scene_b, plan_b, _artifact(plan_b, correction_b, designation=None))
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert tuple(f for o in engine_a.scene.objects for f in o.mesh.faces) == tuple(
        f for o in engine_b.scene.objects for f in o.mesh.faces)


def test_aggregated_plan_is_deterministic_and_review_gated():
    scene_a, plan_a = _fixture_g()
    scene_b, plan_b = _fixture_g()
    assert plan_a.canonical_json() == plan_b.canonical_json()
    assert plan_a.plan_id == plan_b.plan_id
    correction = _winding_correction(plan_a)
    assert correction.requires_human_review is True, "winding is never auto-executed"
    assert correction.determinism == "HEURISTIC"
    assert correction.risk == "FIDELITY_GEOMETRY"
    assert correction.finding_code == "MESH_WINDING_INCONSISTENT"


def test_executor_has_no_bpy_or_engine_write_and_never_defaults_a_mutator():
    import ast

    source = open(_ce.__file__, encoding="utf-8").read()
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "bpy" not in imported
    assert not ({"os", "sys", "subprocess"} & imported), "no engine/process/escalation surface"
    # the default mutator refuses to mutate: a winding execution without an injected mutator fails
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    engine = Engine(scene)
    result = execute_repair_face_winding(
        engine_state=engine, plan=plan, authorization=_artifact(plan, correction, designation=0),
        extractor=_extractor)
    assert result["result"] == ExecutionOutcome.MUTATION_FAILED
    assert result["failure_code"] == "MUTATION_FAILED"


def test_authorization_is_mandatory_by_construction():
    """The entry point cannot be called without deciding what artifact to present."""
    import inspect

    signature = inspect.signature(execute_repair_face_winding)
    parameter = signature.parameters["authorization"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty, "no default: the caller must decide"

def test_mixed_plan_executes_only_the_winding_correction():
    """A plan may also contain the Wave-1 removals (design §2.5 sequence). This entry point executes
    ONLY the winding correction and reports the others as SKIPPED — it can never run another
    operation's mutation."""
    scene, plan = _fixture_a()
    correction = _winding_correction(plan)
    duplicate_finding = Finding(
        code=FindingCode.MESH_DUPLICATE_FACE, object_id="o", mesh_id="m",
        measured={"face_a": 0, "face_b": 1}, message="duplicate")
    report = _kernel_report(scene)
    mixed_report = type(report)(scene_id=report.scene_id, validation_state=report.validation_state,
                                findings=tuple(report.findings) + (duplicate_finding,),
                                scene_metrics={}, profile_name=report.profile_name,
                                input_digest=None, source_revision_id=None)
    removal = CorrectionProposal(
        correction_id="DUPLICATE-PLACEHOLDER", finding_code=FindingCode.MESH_DUPLICATE_FACE.value,
        object_id="o", mesh_id="m", correction_type="REMOVE_DUPLICATE_FACE",
        parameters={"mesh_id": "m", "face_ids": [0, 1], "duplicate_relationship": "exact_duplicate"},
        rationale="wave-1 removal", preconditions=(), expected_postcondition={},
        risk="FIDELITY_SAFE", severity=severity_of(FindingCode.MESH_DUPLICATE_FACE).value,
        reversibility="reversible", dependencies=(), determinism="DETERMINISTIC",
        requires_human_review=False, out_of_scope=False)
    mixed = CorrectionPlan(plan_id="", source_report_digest=mixed_report.digest(),
                           source_revision_id=None, planner_version="1",
                           profile={"name": "soccer-field", "version": "1"},
                           corrections=(removal, correction), dependencies=(),
                           summary_metrics={}, state="REVIEW_REQUIRED", planning_errors=())
    calls = {"n": 0}

    def _extracting(engine_state):
        # the plan binds to the FIRST extraction (the report carrying the removal + winding
        # findings); the post-mutation extraction is the honest kernel report of the new state
        calls["n"] += 1
        report = mixed_report if calls["n"] == 1 else _kernel_report(engine_state.scene)
        return engine_state.scene, report

    result, engine, counted = _run(scene, mixed, _artifact(mixed, correction, designation=0),
                                   extractor=_extracting)
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert result["executed_correction_ids"] == [correction.correction_id]
    assert result["skipped_correction_ids"] == [removal.correction_id]
    assert len(counted.calls) == 1
    # the requested removal did NOT happen: the face count is unchanged and only the target flipped
    assert len(engine.scene.objects[0].mesh.faces) == 2
