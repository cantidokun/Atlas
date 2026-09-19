"""Deterministic (non-live) tests for the WAVE-3 merge executor: REPAIR_MERGE_VERTEX ONLY.

Every test is in-memory and deterministic; NO live Blender, NO bpy, NO workflow runner. The bounded
mutation boundary is STUBBED with an in-memory SceneModel transform implementing the design's
normative primitive (rebuild the target mesh's vertex/face tables from the freshly derived tables) —
the live ``from_pydata`` adapter is a SEPARATE, later, live-validated milestone and does not exist
here.

The plans and authorization artifacts are REAL: positive-path plans come from the real Slice-2
explicit-request planner over a real kernel report, the report digests are recomputed by the real
``SceneReport.digest()``, and the artifacts are parsed and verified by the real Slice-1 contract.
For the adversarial cases a SYNTHETIC plan is built through the real ``CorrectionPlan`` contract with
``plan_id`` RECOMPUTED from its own contents (never a hand-forged digest string), modelling exactly
the design's threat model: an integrity-valid plan proves nothing about provenance, which is why the
executor re-derives MR-1…MR-6 instead of trusting the body.
"""
import json

import pytest

from planning.blender.correction_authorization import (
    AUTHORIZATION_VERSION,
    mapping_digest,
    parse_authorization,
)
from planning.blender.correction_contract import CorrectionPlan, CorrectionProposal
from planning.blender.correction_executor import (
    ExecutionOutcome,
    execute_merge_vertex,
)
from planning.blender.correction_planner import (
    MERGE_PARAMETER_KEYS,
    _correction_id,
    plan_merge_vertex_correction,
)
from planning.blender.correction_values import thaw_jsonable
from planning.blender.extraction_payload import PAYLOAD_SCHEMA_VERSION, payload_to_scene_model
from planning.blender.finding_codes import FindingCode, severity_of
from planning.blender.kernel import run_scene_health, soccer_field_profile_default
from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel
from planning.blender.scene_report import REPORT_FORMAT_VERSION

PROFILE = {"name": "soccer-field", "version": "1"}
MERGE = "REPAIR_MERGE_VERTEX"
MERGE_CODE = FindingCode.MESH_DUPLICATE_VERTEX


# ---------------------------------------------------------------------------
# fixtures: real scenes -> real kernel reports -> real (or integrity-valid synthetic) plans
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
    """An unrelated object whose every field must survive a merge bit-identically (MQ-6)."""
    return {
        "object_id": object_id, "name": "goal", "collection": "Goals",
        "parent_object_id": None, "location": [5, 0, 0], "scale": [1, 1, 1],
        "rotation": [1, 0, 0, 0], "visible": True,
        "mesh": {"mesh_id": mesh_id, "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                 "faces": [[0, 1, 2]], "normals": None, "uvs": None, "materials": [],
                 "local_frame_id": None},
    }


def _payload_for(faces, verts, **kwargs):
    kwargs.setdefault("extra_objects", (_unrelated_object(),))
    return _payload(faces, verts, **kwargs)


def _scene_input_for(faces, verts, **kwargs):
    """The planner consumes the SCENE-INPUT grammar, which is the extraction payload WITHOUT the
    extraction-only ``schema_version`` field (``parse_scene_report_input`` rejects unknown fields)."""
    payload = _payload_for(faces, verts, **kwargs)
    payload.pop("schema_version")
    return payload


def _scene(faces, verts, **kwargs):
    return payload_to_scene_model(_payload_for(faces, verts, **kwargs))


def _kernel_report(scene):
    return run_scene_health(scene, soccer_field_profile_default())


def _report_dict(scene):
    report = _kernel_report(scene)
    payload = report.to_json_compatible()
    payload["digest"] = report.digest()
    payload["report_format_version"] = REPORT_FORMAT_VERSION
    return payload


def _plan_for(scene, payload=None):
    """A REAL plan from the REAL explicit-request merge planner over a REAL kernel report."""
    outcome = plan_merge_vertex_correction(
        _report_dict(scene), payload, profile=PROFILE
    )
    return outcome


def _merge_corrections(plan):
    return [c for c in plan.corrections if c.correction_type == MERGE]


def _merge_correction(plan):
    corrections = _merge_corrections(plan)
    assert len(corrections) == 1, "expected exactly one merge correction"
    return corrections[0]


def _params(correction):
    return thaw_jsonable(correction.parameters)


def _synthetic_merge_plan(scene, parameters, *, object_id="o", mesh_id="m"):
    """A plan whose merge correction carries THESE parameters, with ``plan_id`` recomputed by the
    real contract from its own canonical contents.

    This models the design's threat model exactly: ``plan_id`` proves the plan was not edited after
    construction — it proves NOTHING about provenance. A plan produced by an attacker (or a buggy
    planner) is self-consistent and integrity-valid, which is precisely why the executor re-derives
    MR-1…MR-6 and refuses rather than trusting the body.
    """
    source_digest = _kernel_report(scene).digest()
    proposal = CorrectionProposal(
        correction_id=_correction_id(MERGE_CODE, object_id, mesh_id, parameters),
        finding_code=MERGE_CODE.value,
        object_id=object_id,
        mesh_id=mesh_id,
        correction_type=MERGE,
        parameters=parameters,
        rationale="synthetic merge correction for an adversarial (integrity-valid) plan",
        preconditions=({"source_report_digest": source_digest},
                       {"finding_code": MERGE_CODE.value},
                       {"affected_entity": {"object_id": object_id, "mesh_id": mesh_id}}),
        expected_postcondition={"finding_cleared": MERGE_CODE.value,
                                "unrelated_topology_unchanged": True},
        risk="FIDELITY_GEOMETRY",
        severity=severity_of(MERGE_CODE).value,
        reversibility="partially_reversible",
        dependencies=(),
        determinism="DETERMINISTIC",
        requires_human_review=True,
        out_of_scope=False,
    )
    return CorrectionPlan(
        plan_id="",
        source_report_digest=source_digest,
        source_revision_id=None,
        planner_version="1",
        profile={"name": "soccer-field", "version": "1"},
        corrections=(proposal,),
        dependencies=(),
        summary_metrics={},
        state="REVIEW_REQUIRED",
        planning_errors=(),
    )


def _artifact(plan, correction, **overrides):
    artifact = {
        "authorization_version": AUTHORIZATION_VERSION,
        "authorization_policy_version": "1",
        "decision": "APPROVED",
        "correction_type": correction.correction_type,
        "correction_id": correction.correction_id,
        "plan_id": plan.plan_id,
        "source_report_digest": plan.source_report_digest,
        "authorized_by": "operator",
        "authorized_at_utc": "2026-09-12T12:00:00Z",
    }
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
        coordinate_frame=scene.coordinate_frame, world_bounds=scene.world_bounds,
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


def _merge_mutator(engine_state, *, object_id, mesh_id, vertices, faces, old_to_new_mapping):
    """The normative primitive, in memory: rebuild ONLY the target mesh's vertex/face tables."""
    def transform(o):
        if o.object_id != object_id:
            return o
        return _with_mesh(o, MeshModel(
            mesh_id=o.mesh.mesh_id,
            vertices=tuple(tuple(v) for v in vertices),
            faces=tuple(tuple(f) for f in faces),
            normals=o.mesh.normals, uvs=o.mesh.uvs,
            materials=o.mesh.materials, local_frame_id=o.mesh.local_frame_id,
        ))
    _rebuild(engine_state, transform)


def _run(scene, plan, artifact, *, mutator=None, extractor=None, **kwargs):
    engine = Engine(scene)
    counted = Counter(mutator if mutator is not None else _merge_mutator)
    result = execute_merge_vertex(
        engine_state=engine,
        plan=plan,
        authorization=artifact,
        mutator=counted,
        extractor=extractor if extractor is not None else _extractor,
        **kwargs,
    )
    return result, engine, counted

# ---------------------------------------------------------------------------
# fixture builders
# ---------------------------------------------------------------------------

#: Design Fixture-A shape: one bit-identical duplicate pair whose REMOVED member is the last
#: vertex, so the surviving PRE-state subsequence happens to be {0..m-1}. This is the one shape for
#: which the RETIRED planner kept set ``sorted(set(old_to_new_mapping))`` (the POST index range) was
#: accidentally correct; the general case is the middle-table regression in section 8.
TAIL_VERTS = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
              (5.0, 0.0, 0.0), (6.0, 0.0, 0.0), (5.0, 1.0, 0.0), (0.0, 0.0, 0.0)]
TAIL_FACES = [(0, 1, 2), (3, 4, 5)]

#: The general case: a bit-identical duplicate pair in the MIDDLE of the table (removed index 3
#: between kept indices), so the surviving PRE-state subsequence is [0, 1, 2, 4, 5, 6]. The executor
#: has always derived that correctly; before Wave 13 the planner used the POST index range as its kept
#: set and therefore refused this shape with PARTIAL_GROUP_COVERAGE, which is why its plan was built
#: through the real CorrectionPlan contract. The planner now emits it (section 8), and the real
#: planner -> real executor integration is pinned by
#: ``test_real_planner_middle_table_plan_is_executed_by_the_real_executor``.
MID_VERTS = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
             (0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (6.0, 0.0, 0.0), (5.0, 1.0, 0.0)]
MID_FACES = [(0, 1, 2), (4, 5, 6)]

#: Design Fixture-D shape: two faces distinct only via different members of one bit-identical
#: group, which become identical after the merge -> MP-9 must refuse (TOPOLOGY_CONSEQUENCE_PREDICTED).
DUPFACE_VERTS = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 0.0)]
DUPFACE_FACES = [(0, 1, 2), (3, 1, 2)]

#: Design Fixture-C shape: two vertices that share the rounded key but differ by 1e-7 -> SUB_GRID,
#: which MP-7 must refuse (a 1e-6-scale coordinate edit is not provably lossless).
SUBGRID_VERTS = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1e-07, 0.0, 0.0)]
SUBGRID_FACES = [(0, 1, 2), (3, 1, 2)]


def _groups_of(scene):
    """The duplicate groups the AUTHORITATIVE table proves, derived independently of the planner."""
    from planning.blender.correction_planner import _groups_from_pairs, _pairs_implied_by_table
    from planning.blender.correction_authorization import validate_duplicate_groups
    table = scene.objects[0].mesh.vertices
    pairs = sorted(_pairs_implied_by_table(table))
    return validate_duplicate_groups(_groups_from_pairs(pairs))


def _params_for(scene, *, recorded_pairs=None, duplicate_groups=None, survivor_indices=None,
                old_to_new_mapping=None, mapping_digest_value=None, all_groups_exact=True,
                predicted_topology_unchanged=True, mesh_id="m", **overrides):
    """Build a canonical merge parameter dict whose derived values are CORRECT for ``scene``."""
    from planning.blender.correction_authorization import (
        canonical_survivor_indices, make_index_mapping,
    )
    from planning.blender.correction_planner import _pairs_implied_by_table
    table = scene.objects[0].mesh.vertices
    n = len(table)
    groups = _groups_of(scene)
    pairs = sorted(_pairs_implied_by_table(table))
    mapping = make_index_mapping(n, groups)
    params = {
        "mesh_id": mesh_id,
        "recorded_pairs": recorded_pairs if recorded_pairs is not None else [list(p) for p in pairs],
        "duplicate_groups": duplicate_groups if duplicate_groups is not None else [list(g) for g in groups],
        "survivor_indices": (survivor_indices if survivor_indices is not None
                             else list(canonical_survivor_indices(groups))),
        "old_to_new_mapping": (old_to_new_mapping if old_to_new_mapping is not None
                               else list(mapping)),
        "mapping_digest": (mapping_digest_value if mapping_digest_value is not None
                           else mapping_digest(mesh_id, n, mapping)),
        "all_groups_exact": all_groups_exact,
        "predicted_topology_unchanged": predicted_topology_unchanged,
    }
    params.update(overrides)
    assert tuple(params.keys()) == MERGE_PARAMETER_KEYS
    return params


def _real_plan(scene, verts, faces, **kwargs):
    """(plan, correction) from the REAL explicit-request planner."""
    payload = _scene_input_for(faces, verts, **kwargs)
    outcome = _plan_for(scene, payload)
    assert outcome.refusal_code is None, f"planner refused: {outcome.refusal_code}"
    return outcome.plan, _merge_correction(outcome.plan)


def _synthetic_plan_for(scene, params, **kwargs):
    """(plan, correction) from an integrity-valid synthetic plan carrying THESE parameters."""
    plan = _synthetic_merge_plan(scene, params, **kwargs)
    return plan, _merge_correction(plan)


def _proposal_for(scene, params, *, object_id="o", mesh_id="m", correction_type=MERGE):
    """One contract-valid merge proposal (plan_id/source are recomputed by the contract)."""
    digest = _kernel_report(scene).digest()
    return CorrectionProposal(
        correction_id=_correction_id(MERGE_CODE, object_id, mesh_id, params),
        finding_code=MERGE_CODE.value,
        object_id=object_id,
        mesh_id=mesh_id,
        correction_type=correction_type,
        parameters=params,
        rationale="contract-valid proposal built directly for a structural test",
        preconditions=({"source_report_digest": digest},),
        expected_postcondition={"finding_cleared": MERGE_CODE.value},
        risk="FIDELITY_GEOMETRY",
        severity=severity_of(MERGE_CODE).value,
        reversibility="partially_reversible",
        dependencies=(),
        determinism="DETERMINISTIC",
        requires_human_review=True,
        out_of_scope=False,
    )


def _contract_plan(scene, *, proposals=(), source_report_digest=None):
    """A plan built through the real contract, so ``plan_id`` is CONSISTENT with its own contents.

    Used for the structural cases (zero or two executable corrections, a differently-bound source)
    that must survive plan-integrity verification in order to reach the branch under test — a mere
    ``setattr`` would be caught earlier by MP-2's plan_id recomputation.
    """
    return CorrectionPlan(
        plan_id="",
        source_report_digest=(source_report_digest if source_report_digest is not None
                              else _kernel_report(scene).digest()),
        source_revision_id=None,
        planner_version="1",
        profile={"name": "soccer-field", "version": "1"},
        corrections=tuple(proposals),
        dependencies=(),
        summary_metrics={},
        state="REVIEW_REQUIRED",
        planning_errors=(),
    )


def _fixture_tail():
    scene = _scene(TAIL_FACES, TAIL_VERTS)
    plan, corr = _real_plan(scene, TAIL_VERTS, TAIL_FACES)
    return scene, plan, corr


def _fixture_mid():
    scene = _scene(MID_FACES, MID_VERTS)
    plan, corr = _synthetic_plan_for(scene, _params_for(scene))
    return scene, plan, corr


# ---------------------------------------------------------------------------
# fraud / failure mutators (each one provokes exactly ONE postcondition)
# ---------------------------------------------------------------------------

def _noop_mutator(engine_state, *, object_id, mesh_id, vertices, faces, old_to_new_mapping):
    """Does nothing at all: the merge never happened -> MQ-1 (vertex count) must fail."""
    return None


def _drop_face_mutator(engine_state, *, object_id, mesh_id, vertices, faces, old_to_new_mapping):
    """Performs the merge but ALSO drops a face -> MQ-3 (face count) must fail."""
    _merge_mutator(engine_state, object_id=object_id, mesh_id=mesh_id, vertices=vertices,
                   faces=faces, old_to_new_mapping=old_to_new_mapping)
    def transform(o):
        if o.object_id != object_id:
            return o
        return _with_mesh(o, MeshModel(mesh_id=o.mesh.mesh_id, vertices=o.mesh.vertices,
                                       faces=tuple(o.mesh.faces)[:-1], normals=o.mesh.normals,
                                       uvs=o.mesh.uvs, materials=o.mesh.materials,
                                       local_frame_id=o.mesh.local_frame_id))
    _rebuild(engine_state, transform)


def _move_vertex_mutator(engine_state, *, object_id, mesh_id, vertices, faces, old_to_new_mapping):
    """Performs the merge but ALSO moves a surviving vertex -> MQ-1 (bitwise table) must fail."""
    _merge_mutator(engine_state, object_id=object_id, mesh_id=mesh_id, vertices=vertices,
                   faces=faces, old_to_new_mapping=old_to_new_mapping)
    def transform(o):
        if o.object_id != object_id:
            return o
        verts = [list(v) for v in o.mesh.vertices]
        verts[0][0] = verts[0][0] + 1.0
        return _with_mesh(o, MeshModel(mesh_id=o.mesh.mesh_id, vertices=tuple(tuple(v) for v in verts),
                                       faces=o.mesh.faces, normals=o.mesh.normals, uvs=o.mesh.uvs,
                                       materials=o.mesh.materials,
                                       local_frame_id=o.mesh.local_frame_id))
    _rebuild(engine_state, transform)


def _materials_mutator(engine_state, *, object_id, mesh_id, vertices, faces, old_to_new_mapping):
    """Performs the merge but ALSO assigns a material to the target mesh -> MQ-5 must fail."""
    _merge_mutator(engine_state, object_id=object_id, mesh_id=mesh_id, vertices=vertices,
                   faces=faces, old_to_new_mapping=old_to_new_mapping)
    def transform(o):
        if o.object_id != object_id:
            return o
        return _with_mesh(o, MeshModel(mesh_id=o.mesh.mesh_id, vertices=o.mesh.vertices,
                                       faces=o.mesh.faces, normals=o.mesh.normals, uvs=o.mesh.uvs,
                                       materials=("tampered",),
                                       local_frame_id=o.mesh.local_frame_id))
    _rebuild(engine_state, transform)


def _unrelated_mutator(engine_state, *, object_id, mesh_id, vertices, faces, old_to_new_mapping):
    """Performs the merge but ALSO renames an UNRELATED object -> MQ-6 must fail."""
    _merge_mutator(engine_state, object_id=object_id, mesh_id=mesh_id, vertices=vertices,
                   faces=faces, old_to_new_mapping=old_to_new_mapping)
    def transform(o):
        if o.object_id == object_id:
            return o
        return ObjectModel(object_id=o.object_id, name=o.name + "_tampered", collection=o.collection,
                           parent_object_id=o.parent_object_id, location=o.location, scale=o.scale,
                           rotation=o.rotation, visible=o.visible, mesh=o.mesh)
    _rebuild(engine_state, transform)

# ===========================================================================
# 1. POSITIVE PATHS — exactly one bounded mutation, complete receipt
# ===========================================================================

def test_valid_exact_bit_merge_completes_with_exactly_one_mutation():
    scene, plan, corr = _fixture_tail()
    result, engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert result["failure_code"] is None
    assert len(counted.calls) == 1, "exactly ONE bounded mutation per execution"
    post = engine.scene.objects[0].mesh
    # MQ-1: the exact ordered surviving subsequence of the pre-state (7 -> 6 vertices)
    assert post.vertices == tuple(TAIL_VERTS[i] for i in (0, 1, 2, 3, 4, 5))
    # MQ-3: faces are the elementwise rho∘sigma substitution
    assert post.faces == ((0, 1, 2), (3, 4, 5))
    assert result["pre_vertex_count"] == 7
    assert result["post_vertex_count"] == 6
    assert result["duplicate_groups"] == [[0, 6]]
    assert result["survivor_indices"] == [0]
    assert result["removed_vertex_indices"] == [6]
    assert result["executed_correction_ids"] == [corr.correction_id]
    assert result["target_object_mesh"] == {"object_id": "o", "mesh_id": "m"}


def test_general_case_mid_table_duplicate_completes_and_renumbers_faces():
    """The removed index sits BETWEEN kept indices, so the substitution genuinely renumbers faces."""
    scene, plan, corr = _fixture_mid()
    result, engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert len(counted.calls) == 1
    post = engine.scene.objects[0].mesh
    assert post.vertices == tuple(MID_VERTS[i] for i in (0, 1, 2, 4, 5, 6))
    assert post.faces == ((0, 1, 2), (3, 4, 5))
    assert result["removed_vertex_indices"] == [3]
    assert result["changed_face_indices"] == [1], "the second face's loop indices were renumbered"


def test_transitive_group_of_three_collapses_to_one_survivor():
    verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
             (5.0, 0.0, 0.0), (6.0, 0.0, 0.0), (5.0, 1.0, 0.0),
             (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
    faces = [(0, 1, 2), (3, 4, 5)]
    scene = _scene(faces, verts)
    assert _groups_of(scene) == ((0, 6, 7),)
    plan, corr = _synthetic_plan_for(scene, _params_for(scene))
    result, engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert len(counted.calls) == 1
    assert result["duplicate_groups"] == [[0, 6, 7]]
    assert result["removed_vertex_indices"] == [6, 7]
    assert result["post_vertex_count"] == 6
    assert engine.scene.objects[0].mesh.vertices == tuple(verts[i] for i in (0, 1, 2, 3, 4, 5))


def test_completed_receipt_is_evidence_backed_and_claims_no_authority():
    scene, plan, corr = _fixture_tail()
    result, _engine, _counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert result["receipt_version"] == "1"
    assert result["correction_type"] == MERGE
    assert result["authorization_verified"] is True
    assert result["plan_id_recomputed"] == plan.plan_id
    assert result["source_report_digest_recomputed"] == plan.source_report_digest
    assert result["old_to_new_mapping"] == [0, 1, 2, 3, 4, 5, 0]
    assert result["old_to_new_mapping_digest"] is not None
    assert len(result["old_to_new_mapping_digest"]) == 64
    # honest scope flags: this capability has no persistence/rollback/geometry/normal authority
    assert result["vertex_merge_only"] is True
    assert result["index_renumbering_only"] is True
    assert result["geometry_unverifiable"] is False
    assert result["normal_agreement_not_verified"] is True
    assert result["persisted"] is False
    assert result["rollback_performed"] is False
    # pre/post finding evidence, in the report's canonical order
    assert len(result["pre_duplicate_vertex_findings"]) == 1
    assert result["post_duplicate_vertex_findings"] == []
    assert all(entry["ok"] is True for entry in result["precondition_results"])
    assert all(entry["ok"] is True for entry in result["postcondition_results"])
    # every precondition and postcondition entry names its predicate id (§10 content rule)
    assert [e["reason"].split(":")[0] for e in result["precondition_results"]] == [
        "MP-2", "MP-10", "MP-1", "MP-3", "MP-4", "MP-5", "MP-6", "MP-7", "MP-8", "MP-9",
    ]
    assert [e["reason"].split(":")[0] for e in result["postcondition_results"]] == [
        "MQ-1", "MQ-2", "MQ-3", "MQ-4", "MQ-5", "MQ-6", "MQ-7",
    ]


def test_receipt_reports_the_full_documented_field_set():
    scene, plan, corr = _fixture_tail()
    result, _engine, _counted = _run(scene, plan, _artifact(plan, corr))
    expected = {
        "receipt_version", "result", "failure_code", "executor_version", "execution_policy_version",
        "correction_type", "correction_id", "plan_id", "plan_id_recomputed", "source_report_digest",
        "source_report_digest_recomputed", "authorization_verified", "authorization_digest",
        "authorization_policy_version", "executed_correction_ids", "skipped_correction_ids",
        "target_object_mesh", "pre_vertex_count", "post_vertex_count", "duplicate_groups",
        "survivor_indices", "removed_vertex_indices", "old_to_new_mapping", "old_to_new_mapping_digest",
        "changed_face_indices", "pre_duplicate_vertex_findings", "post_duplicate_vertex_findings",
        "pre_duplicate_face_findings", "post_duplicate_face_findings",
        "pre_degenerate_face_findings", "post_degenerate_face_findings",
        "pre_non_manifold_findings", "post_non_manifold_findings",
        "pre_winding_findings", "post_winding_findings", "precondition_results",
        "postcondition_results", "vertex_merge_only", "index_renumbering_only",
        "geometry_unverifiable", "normal_agreement_not_verified", "persisted", "rollback_performed",
        "output_report_digest",
    }
    assert set(result) == expected, "the receipt must be exactly the design's §10 field set (44)"
    assert len(expected) == 44


def test_receipt_is_byte_identical_for_equivalent_inputs():
    """Determinism: equivalent authoritative inputs -> equivalent decisions, evidence and receipt."""
    receipts = []
    for _attempt in range(2):
        scene, plan, corr = _fixture_tail()
        result, _engine, _counted = _run(scene, plan, _artifact(plan, corr))
        receipts.append(json.dumps(result, sort_keys=True, default=str))
    assert receipts[0] == receipts[1]


# ===========================================================================
# 2. AUTHORIZATION — mandatory by construction
# ===========================================================================

def test_absent_authorization_is_required_and_mutates_nothing():
    scene, plan, corr = _fixture_tail()
    result, engine, counted = _run(scene, plan, None)
    assert result["result"] == ExecutionOutcome.AUTHORIZATION_REQUIRED
    assert result["failure_code"] == "AUTHORIZATION_REQUIRED"
    assert len(counted.calls) == 0
    assert result["authorization_policy_version"] is None
    assert engine.scene.objects[0].mesh.vertices == tuple(TAIL_VERTS)


def test_malformed_authorization_is_invalid_and_mutates_nothing():
    scene, plan, corr = _fixture_tail()
    result, _engine, counted = _run(scene, plan, {"decision": "APPROVED"})
    assert result["result"] == ExecutionOutcome.AUTHORIZATION_INVALID
    assert len(counted.calls) == 0


def test_authorization_artifact_may_be_presented_as_canonical_json_text():
    scene, plan, corr = _fixture_tail()
    result, _engine, counted = _run(scene, plan, json.dumps(_artifact(plan, corr)))
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert len(counted.calls) == 1


def test_a_receipt_cannot_be_replayed_as_an_authorization():
    scene, plan, corr = _fixture_tail()
    first, _engine, _counted = _run(scene, plan, _artifact(plan, corr))
    assert first["result"] == ExecutionOutcome.COMPLETED
    scene2, plan2, corr2 = _fixture_tail()
    result, _engine2, counted2 = _run(scene2, plan2, first)
    assert result["result"] == ExecutionOutcome.AUTHORIZATION_INVALID
    assert len(counted2.calls) == 0


def test_wrong_plan_id_is_a_scope_mismatch():
    scene, plan, corr = _fixture_tail()
    artifact = _artifact(plan, corr, plan_id="0" * 64)
    result, _engine, counted = _run(scene, plan, artifact)
    assert result["result"] == ExecutionOutcome.AUTHORIZATION_SCOPE_MISMATCH
    assert len(counted.calls) == 0


def test_wrong_source_digest_is_a_scope_mismatch():
    scene, plan, corr = _fixture_tail()
    artifact = _artifact(plan, corr, source_report_digest="1" * 64)
    result, _engine, counted = _run(scene, plan, artifact)
    assert result["result"] == ExecutionOutcome.AUTHORIZATION_SCOPE_MISMATCH
    assert len(counted.calls) == 0


def test_wrong_correction_id_is_a_scope_mismatch():
    scene, plan, corr = _fixture_tail()
    artifact = _artifact(plan, corr, correction_id="MESH_DUPLICATE_VERTEX-m-deadbeef")
    result, _engine, counted = _run(scene, plan, artifact)
    assert result["result"] == ExecutionOutcome.AUTHORIZATION_SCOPE_MISMATCH
    assert len(counted.calls) == 0


def test_non_approved_decision_and_unaccepted_policy_are_invalid():
    scene, plan, corr = _fixture_tail()
    denied, _e, c1 = _run(scene, plan, _artifact(plan, corr, decision="DENIED"))
    assert denied["result"] == ExecutionOutcome.AUTHORIZATION_INVALID
    assert len(c1.calls) == 0
    scene2, plan2, corr2 = _fixture_tail()
    stale, _e2, c2 = _run(scene2, plan2, _artifact(plan2, corr2, authorization_policy_version="99"))
    assert stale["result"] == ExecutionOutcome.AUTHORIZATION_INVALID
    assert len(c2.calls) == 0


def test_merge_artifact_supplying_winding_fields_is_refused():
    """A merge artifact may never carry a winding parameter (design §8 field-applicability)."""
    scene, plan, corr = _fixture_tail()
    artifact = _artifact(plan, corr, designated_face_index=1)
    result, _engine, counted = _run(scene, plan, artifact)
    assert result["result"] == ExecutionOutcome.AUTHORIZATION_INVALID
    assert result["failure_code"] == "FIELD_NOT_APPLICABLE_TO_MERGE"
    assert len(counted.calls) == 0


def test_expected_mapping_digest_assertion_matching_is_accepted():
    scene, plan, corr = _fixture_tail()
    digest = _params(corr)["mapping_digest"]
    artifact = _artifact(plan, corr, expected_merge_mapping_digest=digest)
    result, _engine, counted = _run(scene, plan, artifact)
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert len(counted.calls) == 1


def test_expected_mapping_digest_assertion_mismatch_is_refused_before_any_mutation():
    scene, plan, corr = _fixture_tail()
    artifact = _artifact(plan, corr, expected_merge_mapping_digest="f" * 64)
    result, engine, counted = _run(scene, plan, artifact)
    assert result["result"] == ExecutionOutcome.AUTHORIZATION_SCOPE_MISMATCH
    assert result["failure_code"] == "EXPECTED_MAPPING_DIGEST_MISMATCH"
    assert len(counted.calls) == 0
    assert engine.scene.objects[0].mesh.vertices == tuple(TAIL_VERTS)

# ===========================================================================
# 3. PLAN / TARGET / GROUP / SURVIVOR / MAPPING BINDING
# ===========================================================================

def test_tampered_plan_id_is_plan_invalid_before_any_mutation():
    scene, plan, corr = _fixture_tail()
    object.__setattr__(plan, "plan_id", "0" * 64)
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PLAN_INVALID
    assert result["failure_code"] == "PLAN_ID_MISMATCH"
    assert len(counted.calls) == 0


def test_plan_without_a_merge_correction_is_refused():
    scene, _plan, corr = _fixture_mid()
    plan = _contract_plan(scene, proposals=())
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PLAN_INVALID
    assert result["failure_code"] == "NO_EXECUTABLE_CORRECTION"
    assert len(counted.calls) == 0


def test_multi_executable_merge_plan_is_refused():
    scene = _scene(MID_FACES, MID_VERTS)
    params = _params_for(scene)
    first = _proposal_for(scene, params)
    second = _proposal_for(scene, params, mesh_id="m2")
    plan = _contract_plan(scene, proposals=(first, second))
    result, _engine, counted = _run(scene, plan, _artifact(plan, first))
    assert result["result"] == ExecutionOutcome.PLAN_INVALID
    assert result["failure_code"] == "AMBIGUOUS_MULTIPLE_EXECUTABLE_CORRECTIONS"
    assert len(counted.calls) == 0


def test_merge_parameters_must_pass_the_operation_allowlist():
    scene = _scene(MID_FACES, MID_VERTS)
    poisoned = dict(_params_for(scene))
    poisoned.pop("survivor_indices")
    plan, corr = _synthetic_plan_for(scene, poisoned)
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PLAN_INVALID
    assert result["failure_code"] == "MISSING_PARAMETER:survivor_indices"
    assert len(counted.calls) == 0

    extra = dict(_params_for(scene))
    extra["survivor"] = [0]
    plan2, corr2 = _synthetic_plan_for(scene, extra)
    result2, _e2, c2 = _run(scene, plan2, _artifact(plan2, corr2))
    assert result2["result"] == ExecutionOutcome.PLAN_INVALID
    assert result2["failure_code"] == "UNEXPECTED_PARAMETER:survivor"
    assert len(c2.calls) == 0


def test_target_object_that_does_not_own_the_declared_mesh_is_unresolved():
    """Cross-scope binding: the declared pair must resolve to exactly ONE object/mesh (MP-1)."""
    scene = _scene(MID_FACES, MID_VERTS)
    params = _params_for(scene, mesh_id="m2")
    plan, corr = _synthetic_plan_for(scene, params, object_id="o")
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert result["failure_code"] == "MP-1"
    assert len(counted.calls) == 0


def test_plan_whose_groups_belong_to_another_mesh_is_refused():
    """Cross-mesh: the plan names the unrelated mesh, whose fresh evidence has no duplicate pair."""
    scene = _scene(MID_FACES, MID_VERTS)
    params = _params_for(scene, mesh_id="m2")
    params["duplicate_groups"] = [[0, 1]]
    params["recorded_pairs"] = [[0, 1]]
    plan, corr = _synthetic_plan_for(scene, params, object_id="other", mesh_id="m2")
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert result["failure_code"] == "MP-3"
    assert len(counted.calls) == 0


def test_group_mismatch_invented_group_is_refused():
    scene = _scene(MID_FACES, MID_VERTS)
    params = _params_for(scene, duplicate_groups=[[0, 3], [4, 5]])
    plan, corr = _synthetic_plan_for(scene, params)
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert result["failure_code"] == "MP-3"
    assert len(counted.calls) == 0


def test_group_ordering_mismatch_is_refused():
    """Members must be ascending. A non-canonical group representation is a plan-BODY shape defect,
    so the Slice-1 canonical-group validator refuses it at the MP-10 pre-gate — before any engine
    contact — rather than after re-derivation. Fail-closed either way: zero mutator invocations."""
    scene = _scene(MID_FACES, MID_VERTS)
    params = _params_for(scene, duplicate_groups=[[3, 0]])
    plan, corr = _synthetic_plan_for(scene, params)
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PLAN_INVALID
    assert result["failure_code"] == "MERGE_BINDING_INVALID"
    assert len(counted.calls) == 0


def test_recorded_pairs_that_contradict_the_groups_are_refused():
    scene = _scene(MID_FACES, MID_VERTS)
    params = _params_for(scene, recorded_pairs=[[0, 3], [4, 6]])
    plan, corr = _synthetic_plan_for(scene, params)
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert result["failure_code"] == "MP-3"
    assert len(counted.calls) == 0


def test_survivor_mismatch_is_refused():
    scene = _scene(MID_FACES, MID_VERTS)
    params = _params_for(scene, survivor_indices=[3])
    plan, corr = _synthetic_plan_for(scene, params)
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert result["failure_code"] == "MP-4"
    assert len(counted.calls) == 0


def test_mapping_mismatch_is_refused():
    """A declared mapping that is not the canonical rho∘sigma is refused (MP-8), never 'corrected'."""
    scene = _scene(MID_FACES, MID_VERTS)
    params = _params_for(scene, old_to_new_mapping=[0, 1, 2, 2, 3, 4, 5])
    plan, corr = _synthetic_plan_for(scene, params)
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert result["failure_code"] == "MP-8"
    assert len(counted.calls) == 0


def test_mapping_digest_mismatch_is_refused():
    scene = _scene(MID_FACES, MID_VERTS)
    params = _params_for(scene, mapping_digest_value="a" * 64)
    plan, corr = _synthetic_plan_for(scene, params)
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert result["failure_code"] == "MP-8"
    assert len(counted.calls) == 0


def test_face_referencing_two_group_members_is_refused():
    """MP-5: the post-state would repeat an index and is unrepresentable."""
    verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 0.0), (9.0, 9.0, 9.0)]
    faces = [(0, 3, 1), (2, 1, 4)]
    scene = _scene(faces, verts)
    plan, corr = _synthetic_plan_for(scene, _params_for(scene))
    result, engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert result["failure_code"] == "MP-5"
    assert len(counted.calls) == 0
    assert engine.scene.objects[0].mesh.vertices == tuple(verts)


# ===========================================================================
# 4. PRESENTATION VALUES ARE NOT AUTHORITY
# ===========================================================================

def test_sub_grid_group_is_refused_even_when_the_plan_declares_all_groups_exact():
    """MP-7: `all_groups_exact=True` in the plan body is a PRESENTATION, not evidence.

    The two vertices differ by 1e-7, so they share the kernel's rounded key but are NOT
    bit-identical. The authorization layer cannot see this (it has no vertex table); the executor
    re-derives it bitwise from fresh coordinates and refuses.
    """
    scene = _scene(SUBGRID_FACES, SUBGRID_VERTS)
    params = _params_for(scene)          # derived values, declared all_groups_exact=True
    assert params["all_groups_exact"] is True
    assert params["duplicate_groups"] == [[0, 3]]
    plan, corr = _synthetic_plan_for(scene, params)
    result, engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert result["failure_code"] == "MP-7"
    assert len(counted.calls) == 0, "a sub-grid collapse must never reach the mutator"
    assert engine.scene.objects[0].mesh.vertices == tuple(SUBGRID_VERTS)


def test_stale_presentation_digest_from_another_scene_is_refused():
    """An internally consistent plan body describing a DIFFERENT scene must not execute here."""
    other = _scene(MID_FACES, MID_VERTS)
    stale_params = _params_for(other)          # correct FOR THE OTHER SCENE
    scene = _scene(TAIL_FACES, TAIL_VERTS)
    plan, corr = _synthetic_plan_for(scene, stale_params)
    result, engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert result["failure_code"] in {"MP-3", "MP-8"}
    assert len(counted.calls) == 0
    assert engine.scene.objects[0].mesh.vertices == tuple(TAIL_VERTS)


def test_predicted_topology_consequence_refuses_before_mutation():
    """Design Fixture D: two faces distinct only via different members of one bit-identical group
    become identical after the merge -> the prediction refuses rather than the merge being cleaned up."""
    scene = _scene(DUPFACE_FACES, DUPFACE_VERTS)
    assert _groups_of(scene) == ((0, 3),)
    params = _params_for(scene)
    plan, corr = _synthetic_plan_for(scene, params)
    result, engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert result["failure_code"] == "MP-9"
    assert len(counted.calls) == 0, "TOPOLOGY_CONSEQUENCE_PREDICTED must refuse BEFORE mutation"
    assert engine.scene.objects[0].mesh.vertices == tuple(DUPFACE_VERTS)


def test_predicted_topology_unchanged_flag_is_not_trusted():
    """The plan asserts `predicted_topology_unchanged=True`; the executor re-derives it and refuses."""
    scene = _scene(DUPFACE_FACES, DUPFACE_VERTS)
    params = _params_for(scene)
    assert params["predicted_topology_unchanged"] is True
    plan, corr = _synthetic_plan_for(scene, params)
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert result["failure_code"] == "MP-9"
    assert len(counted.calls) == 0

# ===========================================================================
# 5. POSTCONDITIONS MQ-1…MQ-7 — the mutation happened, the state is checked
# ===========================================================================

def test_mq1_fires_when_the_vertex_table_is_not_the_surviving_subsequence():
    scene, plan, corr = _fixture_tail()
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr), mutator=_noop_mutator)
    assert result["result"] == ExecutionOutcome.POSTCONDITION_FAILED
    assert result["failure_code"] == "MQ-1"
    assert len(counted.calls) == 1, "the mutator ran; the POST-state is what failed"
    assert result["postcondition_results"][-1]["ok"] is False


def test_mq1_fires_when_a_surviving_vertex_coordinate_changed():
    scene, plan, corr = _fixture_tail()
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr), mutator=_move_vertex_mutator)
    assert result["result"] == ExecutionOutcome.POSTCONDITION_FAILED
    assert result["failure_code"] == "MQ-1"
    assert len(counted.calls) == 1


def test_mq3_fires_when_a_face_was_added_or_removed():
    scene, plan, corr = _fixture_tail()
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr), mutator=_drop_face_mutator)
    assert result["result"] == ExecutionOutcome.POSTCONDITION_FAILED
    assert result["failure_code"] == "MQ-3"
    assert len(counted.calls) == 1


def test_mq5_fires_when_the_target_mesh_identity_changed():
    scene, plan, corr = _fixture_tail()
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr), mutator=_materials_mutator)
    assert result["result"] == ExecutionOutcome.POSTCONDITION_FAILED
    assert result["failure_code"] == "MQ-5"
    assert len(counted.calls) == 1


def test_mq6_fires_when_an_unrelated_object_was_touched():
    scene, plan, corr = _fixture_tail()
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr), mutator=_unrelated_mutator)
    assert result["result"] == ExecutionOutcome.POSTCONDITION_FAILED
    assert result["failure_code"] == "MQ-6"
    assert len(counted.calls) == 1


def test_postcondition_failure_is_never_repaired_in_the_same_run():
    """A postcondition failure ends the run: no retry, no cleanup, no second mutation."""
    scene, plan, corr = _fixture_tail()
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr), mutator=_drop_face_mutator)
    assert result["result"] == ExecutionOutcome.POSTCONDITION_FAILED
    assert len(counted.calls) == 1, "exactly one mutator invocation even on a failing post-state"
    assert result["executed_correction_ids"] == [], "a failed run claims no executed correction"


def test_mutator_raising_is_a_declared_mutation_failure():
    def _boom(engine_state, **kwargs):
        raise RuntimeError("engine blew up")
    scene, plan, corr = _fixture_tail()
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr), mutator=_boom)
    assert result["result"] == ExecutionOutcome.MUTATION_FAILED
    assert result["failure_code"] == "MUTATION_FAILED"
    assert len(counted.calls) == 1


def test_no_mutator_is_ever_defaulted():
    """Without an injected mutator the executor must refuse to invent one."""
    scene, plan, corr = _fixture_tail()
    engine = Engine(scene)
    result = execute_merge_vertex(engine_state=engine, plan=plan, authorization=_artifact(plan, corr),
                                  extractor=_extractor)
    assert result["result"] == ExecutionOutcome.MUTATION_FAILED
    assert result["failure_code"] == "MUTATION_FAILED"
    assert result["persisted"] is False and result["rollback_performed"] is False


def test_unrelated_state_is_preserved_exactly():
    scene, plan, corr = _fixture_tail()
    before = scene.objects[1]
    result, engine, _counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.COMPLETED
    after = engine.scene.objects[1]
    assert after == before, "the unrelated object must be bit-identical in every field"
    assert [o.object_id for o in engine.scene.objects] == ["o", "other"]


# ===========================================================================
# 6. STALENESS, REPLAY AND ERROR BOUNDARIES
# ===========================================================================

def test_source_mismatch_is_rejected_before_any_mutation():
    scene, _plan, corr = _fixture_mid()
    # a plan that is internally CONSISTENT but bound to a different source revision
    plan = _contract_plan(scene, proposals=(_proposal_for(scene, _params_for(scene)),),
                          source_report_digest="2" * 64)
    corr = _merge_correction(plan)
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.SOURCE_MISMATCH
    assert result["failure_code"] == "SOURCE_DIGEST_MISMATCH"
    assert len(counted.calls) == 0


def test_extraction_failure_fails_closed():
    def _broken(engine_state):
        raise RuntimeError("no engine")
    scene, plan, corr = _fixture_tail()
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr), extractor=_broken)
    assert result["result"] == ExecutionOutcome.SOURCE_MISMATCH
    assert len(counted.calls) == 0


def test_repeated_execution_after_the_scene_changed_is_refused():
    """A second run against the already-mutated scene must refuse: its source digest no longer matches."""
    scene, plan, corr = _fixture_tail()
    first, engine, _counted = _run(scene, plan, _artifact(plan, corr))
    assert first["result"] == ExecutionOutcome.COMPLETED
    second, _engine, counted2 = _run(engine.scene, plan, _artifact(plan, corr))
    assert second["result"] == ExecutionOutcome.SOURCE_MISMATCH
    assert len(counted2.calls) == 0


def test_hostile_and_malformed_public_inputs_stay_structured():
    """No raw TypeError/KeyError/AttributeError/ValueError may escape the entry point."""
    scene, plan, corr = _fixture_tail()
    artifact = _artifact(plan, corr)
    hostile = [
        (None, artifact), (object(), artifact), ("not-a-plan", artifact), (12345, artifact),
        (plan, 12345), (plan, object()), (plan, ["APPROVED"]),
    ]
    for bad_plan, bad_artifact in hostile:
        result, _engine, counted = _run(scene, bad_plan, bad_artifact)
        assert isinstance(result, dict)
        assert result["result"] != ExecutionOutcome.COMPLETED
        assert len(counted.calls) == 0
    # A hostile PARAMETER container cannot reach this layer: the plan contract's canonical-value
    # grammar (correction_values._canonical_scalar) already rejects a non-JSON-native container at
    # construction, so the executor only ever sees the canonical mapping or a plan that failed MP-2.


def test_correction_without_a_canonical_object_id_is_refused():
    scene = _scene(MID_FACES, MID_VERTS)
    plan, corr = _synthetic_plan_for(scene, _params_for(scene), object_id="")
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PLAN_INVALID
    assert result["failure_code"] == "TARGET_OBJECT_MISSING"
    assert len(counted.calls) == 0


# ===========================================================================
# 7. REGRESSION — the existing executor capabilities are unaffected
# ===========================================================================

def test_merge_is_in_the_executor_allowlist_and_wave1_wave2_remain():
    import planning.blender.correction_executor as ce
    assert {"REMOVE_DUPLICATE_FACE", "REMOVE_DEGENERATE_FACE",
            "REPAIR_FACE_WINDING", "REPAIR_MERGE_VERTEX"} == set(ce._EXECUTABLE_TYPES)


def test_a_merge_correction_cannot_reach_the_face_removal_pipeline():
    """Cross-operation isolation: the removal entry point selects ITS OWN operation type first."""
    from planning.blender.correction_executor import execute_remove_duplicate_face
    scene, plan, corr = _fixture_tail()
    engine = Engine(scene)
    counted = Counter(_merge_mutator)
    result = execute_remove_duplicate_face(engine_state=engine, plan=plan, mutator=counted,
                                          extractor=_extractor)
    assert result["result"] == ExecutionOutcome.PLAN_INVALID
    assert result["failure_code"] == "NO_EXECUTABLE_CORRECTION"
    assert len(counted.calls) == 0


def test_merge_executor_does_not_import_bpy():
    """This slice stays bpy-free: the live `from_pydata` adapter is a LATER, separately-gated slice.

    Checked structurally over the module's real import statements (not a substring scan — the
    module's own prose legitimately says it imports no ``bpy``), plus the absence of any merge
    live-adapter entry point.
    """
    import ast
    import planning.blender.correction_executor as ce
    tree = ast.parse(open(ce.__file__, encoding="utf-8").read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "bpy" not in imported, f"bpy must not be imported here; imported: {sorted(imported)}"
    assert not hasattr(ce, "execute_merge_vertex_live")
    assert not hasattr(ce, "from_pydata")


# ===========================================================================
# 8. WAVE 13 REGRESSION — planner kept-set closure for middle-table groups
# ===========================================================================

def test_wave13_planner_closes_middle_table_kept_set():
    """A valid exact-bit merge must plan successfully when a removed vertex is not a suffix."""
    mid = _scene(MID_FACES, MID_VERTS)
    outcome = _plan_for(mid, _scene_input_for(MID_FACES, MID_VERTS))
    assert outcome.refusal_code is None
    correction = _merge_correction(outcome.plan)
    parameters = _params(correction)
    assert parameters["duplicate_groups"] == [[0, 3]]
    assert parameters["survivor_indices"] == [0]
    assert parameters["old_to_new_mapping"] == [0, 1, 2, 0, 3, 4, 5]
    assert parameters["all_groups_exact"] is True
    assert parameters["predicted_topology_unchanged"] is True

    # The actual surviving PRE-state vertices are [0, 1, 2, 4, 5, 6], not
    # the post-index range [0, 1, 2, 3, 4, 5]. The planner must therefore emit
    # the same valid merge correction the executor already knows how to apply.


def test_real_planner_middle_table_plan_is_executed_by_the_real_executor():
    """Wave 13 review finding NB-1: the REAL planner's middle-table plan flows through the REAL
    executor, offline and deterministically (no bpy, no live Blender, no workflow runner).

    The two adjacent tests each pin ONE layer: test_wave13_planner_closes_middle_table_kept_set pins
    the plan the real planner emits, and the executor's middle-table tests pin the executor against a
    contract-built plan. Neither runs the layers together, so nothing in CI would notice a future
    divergence between the planner's predicted kept set and the executor's independently re-derived
    one. This test is that integration: ``plan_merge_vertex_correction(...)`` → authorization artifact
    → ``execute_merge_vertex(...)``.

    It is also the regression for the Wave 13 defect. ``_real_plan`` asserts no refusal, so a planner
    that still derived its kept set as ``sorted(set(old_to_new_mapping))`` (the POST index range)
    refuses this fixture with PARTIAL_GROUP_COVERAGE and fails this test before any execution.
    """
    scene = _scene(MID_FACES, MID_VERTS)
    plan, corr = _real_plan(scene, MID_VERTS, MID_FACES)

    # the plan is the REAL planner's, and it authorizes the PRE-state survivor subsequence
    parameters = _params(corr)
    assert parameters["duplicate_groups"] == [[0, 3]]
    assert parameters["survivor_indices"] == [0]
    assert parameters["old_to_new_mapping"] == [0, 1, 2, 0, 3, 4, 5]
    assert parameters["all_groups_exact"] is True

    result, engine, counted = _run(scene, plan, _artifact(plan, corr))

    assert result["result"] == ExecutionOutcome.COMPLETED
    assert result["failure_code"] is None
    assert result["authorization_verified"] is True
    assert len(counted.calls) == 1, "exactly ONE bounded mutation per execution"
    assert result["executed_correction_ids"] == [corr.correction_id]
    assert result["target_object_mesh"] == {"object_id": "o", "mesh_id": "m"}
    assert result["duplicate_groups"] == [[0, 3]]
    assert result["survivor_indices"] == [0]
    assert result["removed_vertex_indices"] == [3]
    assert result["old_to_new_mapping"] == [0, 1, 2, 0, 3, 4, 5]
    assert result["pre_vertex_count"] == 7 and result["post_vertex_count"] == 6

    # MQ-1/MQ-3: the constructed post-state is the surviving PRE-state subsequence [0, 1, 2, 4, 5, 6]
    # with the middle removal renumbering the face that referenced the removed member.
    post = engine.scene.objects[0].mesh
    assert post.vertices == tuple(MID_VERTS[i] for i in (0, 1, 2, 4, 5, 6))
    assert post.faces == ((0, 1, 2), (3, 4, 5))
    assert result["changed_face_indices"] == [1]

    # MQ-6: the unrelated object survives the authorized merge bit-identically.
    other_before = next(o for o in scene.objects if o.object_id == "other")
    other_after = next(o for o in engine.scene.objects if o.object_id == "other")
    assert other_after == other_before

# ===========================================================================
# 9. F-1 REMEDIATION — an EMPTY authoritative group set must refuse, not no-op
#
# Red-team finding F-1: a hand-authored merge plan carrying an empty
# `duplicate_groups` over a duplicate-free mesh reached COMPLETED, invoked the
# mutator once, and emitted a receipt whose empty `duplicate_groups` violated
# design §10 ("empty iff result != COMPLETED"). These tests pin the remediation:
# the executor must refuse BEFORE mutation, with ZERO mutator invocations.
# ===========================================================================

#: A target mesh with NO coincident vertices: distinct rounded keys, no duplicates.
NODUP_VERTS = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
               (5.0, 0.0, 0.0), (5.0, 1.0, 0.0), (6.0, 0.0, 0.0)]
NODUP_FACES = [(0, 1, 2)]


def _fixture_no_duplicates():
    """A scene whose target mesh has no duplicate vertex, plus an artifact-bound merge plan whose
    body is INTERNALLY CONSISTENT with that fresh evidence (it honestly declares zero groups)."""
    scene = _scene(NODUP_FACES, NODUP_VERTS)
    assert _groups_of(scene) == (), "fixture must have no duplicate group"
    params = _params_for(scene)
    assert params["duplicate_groups"] == []
    assert params["recorded_pairs"] == []
    assert params["survivor_indices"] == []
    plan, corr = _synthetic_plan_for(scene, params)
    return scene, plan, corr


def test_f1_empty_group_set_is_refused_before_mutation():
    scene, plan, corr = _fixture_no_duplicates()
    result, engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert result["result"] != ExecutionOutcome.COMPLETED
    assert result["failure_code"] == "MP-3"
    # it must refuse for the EMPTY-set reason, not for a group mismatch: the plan body agreed with
    # the fresh evidence, so a mismatch refusal would be passing this test for the wrong reason.
    reasons = [e["reason"] for e in result["precondition_results"] if not e["ok"]]
    assert reasons, "a failed precondition entry must be recorded"
    assert "EMPTY" in reasons[-1], f"expected the empty-set reason, got: {reasons[-1]!r}"
    assert reasons[-1].startswith("MP-3")


def test_f1_zero_mutator_invocations_and_unchanged_geometry():
    scene, plan, corr = _fixture_no_duplicates()
    before_vertices = tuple(scene.objects[0].mesh.vertices)
    before_faces = tuple(scene.objects[0].mesh.faces)
    result, engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert len(counted.calls) == 0, "the empty-group refusal must invoke the mutator ZERO times"
    assert engine.scene.objects[0].mesh.vertices == before_vertices
    assert engine.scene.objects[0].mesh.faces == before_faces


def test_f1_refusal_is_truthful_and_claims_nothing():
    scene, plan, corr = _fixture_no_duplicates()
    result, _engine, _counted = _run(scene, plan, _artifact(plan, corr))
    assert result["failure_code"] is not None, "failure_code is null only on COMPLETED"
    assert result["executed_correction_ids"] == [], "a refused run executed no correction"
    assert result["skipped_correction_ids"] == [corr.correction_id] or \
        corr.correction_id not in result["executed_correction_ids"]
    # nothing was mutated, so the post-mutation evidence is absent, not fabricated
    assert result["post_vertex_count"] is None
    assert result["changed_face_indices"] is None
    assert result["output_report_digest"] is None
    assert result["post_duplicate_vertex_findings"] is None
    assert result["postcondition_results"] is None
    assert result["authorization_verified"] is False, "the gate never completed, so it is not claimed"
    assert result["persisted"] is False and result["rollback_performed"] is False
    # the receipt still carries the target it resolved, so the refusal is auditable
    assert result["target_object_mesh"] == {"object_id": "o", "mesh_id": "m"}


def test_f1_receipt_duplicate_groups_and_result_stay_consistent():
    """Design §10 rule: `duplicate_groups` is empty IFF `result != "COMPLETED"`."""
    zero_groups = _fixture_no_duplicates()
    r_empty, _e, _c = _run(*zero_groups[:2], _artifact(*zero_groups[1:]))
    assert r_empty["duplicate_groups"] == []
    assert r_empty["result"] != ExecutionOutcome.COMPLETED


def test_section10_duplicate_groups_invariant_holds_on_every_outcome_path():
    """The §10 invariant in the direction that constitutes the F-1 defect, across every outcome path.

    `duplicate_groups` documents `Prov = PRE` — "the groups the merge addressed". The direction that
    matters, and the one F-1 was about, is: **COMPLETED requires a NON-EMPTY group set** (a completed
    merge addressed at least one group), equivalently **empty requires a non-COMPLETED result**.

    The reverse combination — a NON-empty group set on a non-COMPLETED result — is deliberately NOT
    asserted to be impossible: a refusal that occurs AFTER the fresh groups were derived (MP-4…MP-9)
    truthfully reports the PRE-mutation groups it considered, and blanking them would destroy true
    audit evidence for exactly the refusals an operator most needs to inspect. Those receipts are
    unambiguous because they simultaneously report `executed_correction_ids == []` and a `null`
    post-state. See the F-8 observation recorded in the handoff: §10's parenthetical is an imprecise
    statement of the field's nullability convention, not a strict biconditional.
    """
    outcomes = []

    s, p, co = _fixture_tail()
    outcomes.append(("completed", _run(s, p, _artifact(p, co))[0]))
    s, p, co = _fixture_no_duplicates()
    outcomes.append(("empty groups", _run(s, p, _artifact(p, co))[0]))
    s, p, co = _fixture_tail()
    outcomes.append(("no authz", _run(s, p, None)[0]))
    s, p, co = _fixture_tail()
    outcomes.append(("bad plan id", _run(s, p, _artifact(p, co, plan_id="f" * 64))[0]))
    s, p, co = _fixture_tail()
    outcomes.append(("mq failure", _run(s, p, _artifact(p, co), mutator=_noop_mutator)[0]))
    s = _scene(SUBGRID_FACES, SUBGRID_VERTS)
    p, co = _synthetic_plan_for(s, _params_for(s))
    outcomes.append(("mp-7 refusal", _run(s, p, _artifact(p, co))[0]))

    for label, receipt in outcomes:
        groups = receipt["duplicate_groups"]
        completed = receipt["result"] == ExecutionOutcome.COMPLETED
        # (a) the F-1 direction: a COMPLETED merge must report the groups it addressed
        if completed:
            assert groups, f"{label}: COMPLETED with EMPTY duplicate_groups (the F-1 defect)"
        # (b) empty implies not COMPLETED
        if not groups:
            assert not completed, f"{label}: empty groups with a COMPLETED result"
        # (c) the reverse combination is allowed, but it must never claim an executed correction or
        #     a post-mutation state
        if groups and not completed:
            assert receipt["executed_correction_ids"] == [], f"{label}: claimed execution on a refusal"
            assert receipt["post_vertex_count"] is None, f"{label}: claimed a post-state on a refusal"
    assert outcomes[0][1]["result"] == ExecutionOutcome.COMPLETED
    assert outcomes[1][1]["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert outcomes[1][1]["duplicate_groups"] == []


def test_f1_existing_valid_merge_still_completes():
    """No over-refusal: a conforming exact-bit merge is unaffected by the new precondition."""
    for label, make in (("tail-positioned group", _fixture_tail),
                        ("mid-table group", _fixture_mid)):
        scene, plan, corr = make()
        result, engine, counted = _run(scene, plan, _artifact(plan, corr))
        assert result["result"] == ExecutionOutcome.COMPLETED, label
        assert len(counted.calls) == 1, label
        assert result["duplicate_groups"], label
        assert result["duplicate_groups"] != [], label
    # transitive group of three is likewise unaffected
    verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
             (5.0, 0.0, 0.0), (6.0, 0.0, 0.0), (5.0, 1.0, 0.0),
             (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
    scene = _scene([(0, 1, 2), (3, 4, 5)], verts)
    plan, corr = _synthetic_plan_for(scene, _params_for(scene))
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert result["duplicate_groups"] == [[0, 6, 7]]
    assert len(counted.calls) == 1


def test_f1_hostile_equivalents_still_fail_through_structured_errors():
    """A malformed body that WOULD have produced the empty-group case must still fail structurally
    (never a raw exception, never COMPLETED, never a mutation)."""
    scene = _scene(NODUP_FACES, NODUP_VERTS)

    # duplicate_groups declared as a non-sequence
    params = _params_for(scene)
    params["duplicate_groups"] = None
    plan, corr = _synthetic_plan_for(scene, params)
    result, _e, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] != ExecutionOutcome.COMPLETED
    assert isinstance(result["failure_code"], str)
    assert len(counted.calls) == 0

    # groups that name a group the fresh evidence does not support, on a duplicate-free mesh
    params = _params_for(scene, duplicate_groups=[[0, 1]], recorded_pairs=[[0, 1]])
    plan, corr = _synthetic_plan_for(scene, params)
    result, _e, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert result["failure_code"] == "MP-3"
    assert len(counted.calls) == 0

    # a hostile parameter container on the empty-group path
    params = _params_for(scene)
    params["old_to_new_mapping"] = "not-a-sequence"
    plan, corr = _synthetic_plan_for(scene, params)
    result, _e, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] != ExecutionOutcome.COMPLETED
    assert isinstance(result["failure_code"], str)
    assert len(counted.calls) == 0


def test_f1_wave1_wave2_capabilities_are_unaffected():
    """Regression guard: the new precondition lives only on the merge path."""
    import planning.blender.correction_executor as ce
    for symbol in ("execute_remove_duplicate_face", "execute_remove_degenerate_face",
                   "execute_repair_face_winding", "execute_merge_vertex"):
        assert callable(getattr(ce, symbol)), symbol
    assert {"REMOVE_DUPLICATE_FACE", "REMOVE_DEGENERATE_FACE",
            "REPAIR_FACE_WINDING", "REPAIR_MERGE_VERTEX"} == set(ce._EXECUTABLE_TYPES)
    # the new refusal is unreachable from the removal pipeline, which selects its own operation type
    s, p, co = _fixture_no_duplicates()
    engine = Engine(s)
    counted = Counter(_merge_mutator)
    removal = ce.execute_remove_duplicate_face(engine_state=engine, plan=p, mutator=counted,
                                               extractor=_extractor)
    assert removal["result"] == ExecutionOutcome.PLAN_INVALID
    assert removal["failure_code"] == "NO_EXECUTABLE_CORRECTION"
    assert len(counted.calls) == 0


# ===========================================================================
# 10. B-1 REMEDIATION — MQ-7 must not reject a contract-legal merge because a
#     PRE-EXISTING finding's MEASURED PAYLOAD INDEXES were renumbered.
#
# Independent Slice-3 gate (author-independent), blocker B-1: MQ-7 used to require the per-code
# multiset of frozen `measured` payloads to be IDENTICAL pre vs post. The authorized merge is an
# INDEX RENUMBERING, so a pre-existing winding / non-manifold / duplicate-face finding that names a
# renumbered vertex index necessarily carried a different `measured` payload afterwards — MQ-7 then
# reported POSTCONDITION_FAILED AFTER the single mutation, with no rollback authority, which the
# cleared design's fail-closed-before-mutation rule forbids.
#
# The remediation restores design §5I's OWN wording (its gloss for "exactly preserved" is that the
# merge "neither creates nor clears" those finding classes) and makes MP-9 / MQ-7 agree: MQ-7 is
# class-level (created / cleared), and it no longer compares raw payloads. Nothing was weakened —
# MP-9 already evaluates the same created/cleared delta for EVERY code on the exact predicted state
# BEFORE mutation, and the §4 monotonicity argument proves no pre-existing class can be cleared.
#
# CARRY-FORWARD FINDINGS (from the same independent gate) are deliberately NOT addressed here and
# must not be read as fixed by any test below:
#   F-2  hostile plan attribute access can escape the entry point as a raw exception (no receipt).
#   F-3  EXACT is decided numerically, not bitwise (signed zero changes a coordinate's bits while
#        the receipt asserts index_renumbering_only).
#   F-4  MQ-2's "re-derivation" is tautological against ctx (substantive pinning is MP-8+MQ-1+MQ-3).
#   F-5  MQ-4 and MQ-7's count sub-checks are defence-in-depth (unreachable once MQ-1/MQ-3 pass).
#   F-6  §10's "MP-1…MP-10 order (evaluated order)" wording is imprecise vs §6's mandated order.
#   F-7  MP-9's predicted mesh carries no normals, so a mesh whose extraction carries normals AND a
#        pre-existing MESH_NORMAL_INCONSISTENT finding is refused pre-mutation (over-refusal only —
#        verified merge-invariant here, and it cannot cause a mutate-then-fail).
# ===========================================================================

#: The independent gate's exact B-1 reproduction: two exact-bit duplicate groups whose removed
#: members sit BELOW kept indices (so the whole table is renumbered), plus a pre-existing
#: MESH_WINDING_INCONSISTENT finding whose `measured` edge [2,3] becomes [1,2] after the merge.
B1_REPRO_VERTS = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (7.0, 0.0, 0.0),
                  (3.0, 3.0, 0.0), (3.0, 3.0, 0.0), (4.0, 0.0, 5.0)]
B1_REPRO_FACES = [(0, 2, 3), (5, 2, 3)]

#: Pre-existing winding finding on an edge that the merge renumbers ([0,2] -> [0,1]).
WINDING_RENUM_VERTS = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (4.0, 0.0, 0.0),
                       (1.0, 1.0, 0.0), (0.0, 3.0, 0.0), (9.0, 9.0, 9.0)]
WINDING_RENUM_FACES = [(0, 2, 3), (0, 2, 4)]

#: Pre-existing non-manifold edge (valence 3) whose measured edge [0,2] becomes [0,1].
NONMANIFOLD_RENUM_VERTS = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (4.0, 0.0, 0.0),
                           (1.0, 1.0, 0.0), (1.0, -1.0, 0.0), (2.0, 2.0, 0.0)]
NONMANIFOLD_RENUM_FACES = [(0, 2, 3), (0, 2, 4), (0, 2, 5)]

#: Pre-existing duplicate-face finding whose measured `vertices` [2,3,4] becomes [1,2,3]; the
#: duplicate faces also carry three pre-existing winding findings, all renumbered.
DUPFACE_RENUM_VERTS = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (5.0, 0.0, 0.0),
                       (0.0, 5.0, 0.0), (0.0, 0.0, 5.0)]
DUPFACE_RENUM_FACES = [(2, 3, 4), (2, 3, 4)]

#: A transitive group of three plus a renumbered winding finding (valid mid-table merge).
TRANSITIVE_WINDING_VERTS = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0),
                            (4.0, 0.0, 0.0), (1.0, 1.0, 0.0), (1.0, -1.0, 0.0)]
TRANSITIVE_WINDING_FACES = [(0, 3, 4), (0, 3, 5)]

#: Tail-positioned group whose pre-existing winding payload is NOT renumbered (no false positive).
TAIL_WINDING_STABLE_VERTS = [(0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (1.0, 1.0, 0.0),
                             (1.0, -1.0, 0.0), (0.0, 0.0, 0.0), (9.0, 9.0, 9.0)]
TAIL_WINDING_STABLE_FACES = [(0, 1, 2), (0, 1, 3)]

#: A merge that would CREATE a winding finding (two faces become same-direction after the collapse):
#: must still be refused BEFORE mutation.
CREATES_WINDING_VERTS = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (5.0, 0.0, 0.0),
                         (2.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 3.0, 0.0)]
CREATES_WINDING_FACES = [(1, 3, 4), (0, 3, 5)]

#: A merge that would CLEAR a pre-existing winding finding (the shared edge becomes valence 3, so
#: the kernel's two-face winding predicate no longer applies) and CREATE a non-manifold edge: must
#: still be refused BEFORE mutation.
CLEARS_WINDING_VERTS = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (9.0, 9.0, 9.0), (4.0, 0.0, 0.0),
                        (1.0, 1.0, 0.0), (1.0, -1.0, 0.0), (2.0, 2.0, 0.0)]
CLEARS_WINDING_FACES = [(0, 3, 4), (0, 3, 5), (1, 3, 6)]


def _measured_of(mesh, code_token):
    """The `measured` payloads of one finding code for one mesh, in the kernel's own order."""
    from planning.blender.mesh_health import check_mesh
    return [f.measured for f in check_mesh(mesh) if f.code.value == code_token]


def _counts_of(mesh):
    from planning.blender.mesh_health import check_mesh
    counts = {}
    for finding in check_mesh(mesh):
        counts[finding.code.value] = counts.get(finding.code.value, 0) + 1
    return counts


def _kept_pre_indices(vertex_count, groups):
    """The kept PRE-index set ``S`` (design §4), derived independently of the executor."""
    survivor_of = {}
    for group in groups:
        for member in group:
            survivor_of[member] = min(group)
    return tuple(sorted({survivor_of.get(i, i) for i in range(vertex_count)}))


def _independent_predicted_counts(scene):
    """(pre_counts, predicted_counts) for the exact §4 predicted post-state, computed here."""
    from planning.blender.correction_authorization import make_index_mapping
    from planning.blender.mesh_health import check_mesh
    table = scene.objects[0].mesh.vertices
    groups = _groups_of(scene)
    mapping = make_index_mapping(len(table), groups)
    kept = _kept_pre_indices(len(table), groups)
    predicted = MeshModel(
        mesh_id="m",
        vertices=tuple(tuple(table[i]) for i in kept),
        faces=tuple(tuple(mapping[i] for i in face) for face in scene.objects[0].mesh.faces),
    )
    return _counts_of(scene.objects[0].mesh), _counts_of(predicted)


def _delta_between(pre_counts, post_counts):
    """The created/cleared class delta the contract defines (the duplicate-vertex code is the
    capability's own and is expected to be cleared, so it is excluded from `cleared`)."""
    new = sorted(c for c in post_counts if post_counts[c] > pre_counts.get(c, 0))
    cleared = sorted(c for c in pre_counts
                     if pre_counts[c] > post_counts.get(c, 0) and c != MERGE_CODE.value)
    return new, cleared


def _b1_case(verts, faces):
    """(result, engine, counted, plan, corr) for a contract-valid plan over this fixture."""
    scene = _scene(faces, verts)
    plan, corr = _synthetic_plan_for(scene, _params_for(scene))
    result, engine, counted = _run(scene, plan, _artifact(plan, corr))
    return result, engine, counted, plan, corr


def _geometry_blob(entity):
    return ([list(v) for v in entity.mesh.vertices], [list(f) for f in entity.mesh.faces])


def _mq7(result):
    return [entry for entry in (result["postcondition_results"] or [])
            if entry["reason"].startswith("MQ-7")]


def test_b1_the_independent_gate_reproduction_is_now_accepted_with_one_mutation():
    """The exact B-1 fixture: previously COMPLETED->POSTCONDITION_FAILED post-mutation, now accepted.

    Every condition the independent gate established is re-asserted here: the groups are two pairs,
    MP-2/MP-10/MP-1/MP-3..MP-9 all pass, the renumbering really happens (the winding payload edge
    moves [2,3] -> [1,2]), and the run completes with EXACTLY ONE mutation.
    """
    scene = _scene(B1_REPRO_FACES, B1_REPRO_VERTS)
    pre_winding = _measured_of(scene.objects[0].mesh, "MESH_WINDING_INCONSISTENT")
    assert pre_winding == [{"edge": [2, 3], "faces": [0, 1]}], "fixture must carry the gate's payload"

    plan, corr = _synthetic_plan_for(scene, _params_for(scene))
    result, engine, counted = _run(scene, plan, _artifact(plan, corr))

    assert result["result"] == ExecutionOutcome.COMPLETED
    assert result["failure_code"] is None
    assert len(counted.calls) == 1, "exactly one bounded mutation on the accepted path"
    assert result["executed_correction_ids"] == [corr.correction_id]
    assert result["duplicate_groups"] == [[0, 1], [3, 4]]
    assert result["removed_vertex_indices"] == [1, 4]
    assert result["post_vertex_count"] == 4
    assert result["changed_face_indices"] == [0, 1]
    assert all(entry["ok"] is True for entry in result["precondition_results"])
    assert all(entry["ok"] is True for entry in result["postcondition_results"])
    assert _mq7(result) and _mq7(result)[0]["ok"] is True

    # the renumbering is real and DISCLOSED on the receipt (audit data, both payloads present)
    post_winding = _measured_of(engine.scene.objects[0].mesh, "MESH_WINDING_INCONSISTENT")
    assert post_winding == [{"edge": [1, 2], "faces": [0, 1]}]
    assert post_winding != pre_winding
    assert result["pre_winding_findings"][0]["measured"] == {"edge": [2, 3], "faces": [0, 1]}
    assert result["post_winding_findings"][0]["measured"] == {"edge": [1, 2], "faces": [0, 1]}
    assert result["pre_duplicate_vertex_findings"] and result["post_duplicate_vertex_findings"] == []


def test_b1_pre_existing_winding_finding_with_renumbered_indices_is_accepted():
    scene = _scene(WINDING_RENUM_FACES, WINDING_RENUM_VERTS)
    assert _measured_of(scene.objects[0].mesh, "MESH_WINDING_INCONSISTENT") == [
        {"edge": [0, 2], "faces": [0, 1]}]
    result, engine, counted, _plan, _corr = _b1_case(WINDING_RENUM_VERTS, WINDING_RENUM_FACES)
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert len(counted.calls) == 1
    assert _measured_of(engine.scene.objects[0].mesh, "MESH_WINDING_INCONSISTENT") == [
        {"edge": [0, 1], "faces": [0, 1]}]
    assert _mq7(result)[0]["ok"] is True
    assert result["post_vertex_count"] == 5 and result["removed_vertex_indices"] == [1]


def test_b1_pre_existing_non_manifold_finding_with_renumbered_indices_is_accepted():
    scene = _scene(NONMANIFOLD_RENUM_FACES, NONMANIFOLD_RENUM_VERTS)
    pre = _measured_of(scene.objects[0].mesh, "MESH_NON_MANIFOLD_EDGE")
    assert pre == [{"edge": [0, 2], "face_incidence": 3}], "fixture must pre-exist non-manifold"
    result, engine, counted, _plan, _corr = _b1_case(NONMANIFOLD_RENUM_VERTS, NONMANIFOLD_RENUM_FACES)
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert len(counted.calls) == 1
    post = _measured_of(engine.scene.objects[0].mesh, "MESH_NON_MANIFOLD_EDGE")
    assert post == [{"edge": [0, 1], "face_incidence": 3}]
    assert post != pre and post[0]["face_incidence"] == pre[0]["face_incidence"]
    assert _mq7(result)[0]["ok"] is True


def test_b1_pre_existing_duplicate_face_finding_with_renumbered_indices_is_accepted():
    scene = _scene(DUPFACE_RENUM_FACES, DUPFACE_RENUM_VERTS)
    pre = _measured_of(scene.objects[0].mesh, "MESH_DUPLICATE_FACE")
    assert pre == [{"face_a": 0, "face_b": 1, "vertices": [2, 3, 4]}]
    result, engine, counted, _plan, _corr = _b1_case(DUPFACE_RENUM_VERTS, DUPFACE_RENUM_FACES)
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert len(counted.calls) == 1
    post = _measured_of(engine.scene.objects[0].mesh, "MESH_DUPLICATE_FACE")
    assert post == [{"face_a": 0, "face_b": 1, "vertices": [1, 2, 3]}]
    assert post != pre, "the duplicate-face payload must be renumbered by the merge"
    assert _mq7(result)[0]["ok"] is True


def test_b1_unchanged_classes_are_preserved_by_presence_not_by_payload():
    """Several unchanged classes whose measured indexes ALL move: preservation is class-level."""
    scene = _scene(DUPFACE_RENUM_FACES, DUPFACE_RENUM_VERTS)
    pre_counts = _counts_of(scene.objects[0].mesh)
    result, engine, counted, _plan, _corr = _b1_case(DUPFACE_RENUM_VERTS, DUPFACE_RENUM_FACES)
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert len(counted.calls) == 1
    post_counts = _counts_of(engine.scene.objects[0].mesh)
    for code in ("MESH_DUPLICATE_FACE", "MESH_WINDING_INCONSISTENT", "MESH_NON_MANIFOLD_EDGE",
                 "MESH_DEGENERATE_FACE"):
        assert post_counts.get(code, 0) == pre_counts.get(code, 0), code
        assert code != MERGE_CODE.value
    assert pre_counts["MESH_DUPLICATE_FACE"] == 1 and pre_counts["MESH_WINDING_INCONSISTENT"] == 3
    assert _measured_of(engine.scene.objects[0].mesh, "MESH_WINDING_INCONSISTENT") != \
        _measured_of(scene.objects[0].mesh, "MESH_WINDING_INCONSISTENT")
    assert _mq7(result)[0]["ok"] is True


def test_b1_a_stable_payload_is_not_disturbed():
    """A tail-positioned group leaves the winding payload untouched — no false rejection either."""
    scene = _scene(TAIL_WINDING_STABLE_FACES, TAIL_WINDING_STABLE_VERTS)
    assert _groups_of(scene) == ((0, 4),)
    pre = _measured_of(scene.objects[0].mesh, "MESH_WINDING_INCONSISTENT")
    result, engine, counted, _plan, _corr = _b1_case(TAIL_WINDING_STABLE_VERTS,
                                                    TAIL_WINDING_STABLE_FACES)
    assert result["result"] == ExecutionOutcome.COMPLETED
    assert len(counted.calls) == 1
    assert _measured_of(engine.scene.objects[0].mesh, "MESH_WINDING_INCONSISTENT") == pre
    assert _mq7(result)[0]["ok"] is True


def test_b1_face_keyed_findings_are_merge_invariant():
    """MESH_NORMAL_INCONSISTENT is keyed on a FACE index plus geometry, so the mapping cannot move it.

    This is why MQ-7's remaining class-level guard cannot fire on it, and why MP-9's normals-less
    predicted mesh (carry-forward F-7) is an over-refusal risk only, never a mutate-then-fail one.
    """
    from planning.blender.correction_authorization import make_index_mapping
    from planning.blender.mesh_health import check_mesh
    obj = dict(_unrelated_object())
    payload = {
        "schema_version": PAYLOAD_SCHEMA_VERSION, "scene_id": "s", "unit_system": "METERS",
        "objects": [{
            "object_id": "o", "name": "o", "collection": "Field", "parent_object_id": None,
            "location": [0, 0, 0], "scale": [1, 1, 1], "rotation": [1, 0, 0, 0], "visible": True,
            "mesh": {"mesh_id": "m",
                     "vertices": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [5.0, 0.0, 0.0],
                                  [0.0, 5.0, 0.0], [0.0, 0.0, 5.0]],
                     "faces": [[2, 3, 4]], "normals": [[0.0, 0.0, 1.0]], "uvs": None,
                     "materials": [], "local_frame_id": None},
        }, obj],
    }
    scene = payload_to_scene_model(payload)
    mesh = scene.objects[0].mesh
    pre_normals = _measured_of(mesh, "MESH_NORMAL_INCONSISTENT")
    assert pre_normals, "fixture must carry a pre-existing normal finding"
    groups = _groups_of(scene)
    assert groups == ((0, 1),)
    table = mesh.vertices
    mapping = make_index_mapping(len(table), groups)
    kept = _kept_pre_indices(len(table), groups)
    predicted = MeshModel(mesh_id="m",
                          vertices=tuple(tuple(table[i]) for i in kept),
                          faces=tuple(tuple(mapping[i] for i in face) for face in mesh.faces),
                          normals=mesh.normals)
    post_normals = [f.measured for f in check_mesh(predicted)
                    if f.code.value == "MESH_NORMAL_INCONSISTENT"]
    assert post_normals == pre_normals, "a face-keyed normal finding must be merge-invariant"


def test_b1_genuinely_created_class_is_still_refused_before_mutation():
    scene = _scene(CREATES_WINDING_FACES, CREATES_WINDING_VERTS)
    pre_counts, predicted_counts = _independent_predicted_counts(scene)
    new, _cleared = _delta_between(pre_counts, predicted_counts)
    assert "MESH_WINDING_INCONSISTENT" in new, "fixture must genuinely CREATE a class"
    before = _geometry_blob(scene.objects[0])
    result, engine, counted, _plan, _corr = _b1_case(CREATES_WINDING_VERTS, CREATES_WINDING_FACES)
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert result["failure_code"] == "MP-9"
    assert len(counted.calls) == 0
    assert _geometry_blob(engine.scene.objects[0]) == before


def test_b1_genuinely_cleared_class_is_still_refused_before_mutation():
    scene = _scene(CLEARS_WINDING_FACES, CLEARS_WINDING_VERTS)
    pre_counts, predicted_counts = _independent_predicted_counts(scene)
    _new, cleared = _delta_between(pre_counts, predicted_counts)
    assert "MESH_WINDING_INCONSISTENT" in cleared, "fixture must genuinely CLEAR a class"
    before = _geometry_blob(scene.objects[0])
    result, engine, counted, _plan, _corr = _b1_case(CLEARS_WINDING_VERTS, CLEARS_WINDING_FACES)
    assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED
    assert result["failure_code"] == "MP-9"
    assert len(counted.calls) == 0
    assert _geometry_blob(engine.scene.objects[0]) == before
    assert result["duplicate_groups"] == [[0, 1]], "the refusal is recorded with its evidence"


def test_b1_class_delta_guard_still_detects_created_and_cleared_classes():
    """The surviving MQ-7 guard is exercised directly: it must still report created/cleared classes.

    (After MQ-1/MQ-3 pass, the observed post-state IS the MP-9 prediction, so this guard is
    defence-in-depth — pinned here so a future refactor cannot turn MQ-7 into an always-pass.)
    """
    from planning.blender.correction_executor import _merge_topology_delta
    scene = _scene(B1_REPRO_FACES, B1_REPRO_VERTS)
    findings = _merge_topology_delta  # local alias keeps the import inside the test's scope
    from planning.blender.mesh_health import check_mesh
    pre = list(check_mesh(scene.objects[0].mesh))          # 2 duplicate vertices + 1 winding
    delta_full = findings(pre, list(pre))
    assert delta_full["new_codes"] == [] and delta_full["cleared_codes"] == []
    # a genuinely CLEARED class is reported on the non-duplicate-vertex side
    only_winding = [f for f in pre if f.code.value == "MESH_WINDING_INCONSISTENT"]
    delta_cleared = findings(only_winding, [])
    assert delta_cleared["cleared_codes"] == ["MESH_WINDING_INCONSISTENT"]
    # a genuinely CREATED class is reported
    delta_created = findings([], only_winding)
    assert delta_created["new_codes"] == ["MESH_WINDING_INCONSISTENT"]
    # the capability's OWN code is never reported as an unintended "cleared" class
    dv_only = [f for f in pre if f.code.value == MERGE_CODE.value]
    delta_dv = findings(dv_only, [])
    assert delta_dv["cleared_codes"] == [] and delta_dv["duplicate_vertex_remaining"] == 0


def test_b1_exactly_one_mutation_on_accepted_and_zero_on_refused_cases():
    accepted = (
        ("gate reproduction", B1_REPRO_VERTS, B1_REPRO_FACES),
        ("renumbered winding", WINDING_RENUM_VERTS, WINDING_RENUM_FACES),
        ("renumbered non-manifold", NONMANIFOLD_RENUM_VERTS, NONMANIFOLD_RENUM_FACES),
        ("renumbered duplicate face", DUPFACE_RENUM_VERTS, DUPFACE_RENUM_FACES),
        ("stable payload", TAIL_WINDING_STABLE_VERTS, TAIL_WINDING_STABLE_FACES),
        ("transitive group", TRANSITIVE_WINDING_VERTS, TRANSITIVE_WINDING_FACES),
    )
    for label, verts, faces in accepted:
        result, _engine, counted, _plan, _corr = _b1_case(verts, faces)
        assert result["result"] == ExecutionOutcome.COMPLETED, label
        assert len(counted.calls) == 1, label
        assert result["executed_correction_ids"], label
    for label, verts, faces in (("creates a class", CREATES_WINDING_VERTS, CREATES_WINDING_FACES),
                                ("clears a class", CLEARS_WINDING_VERTS, CLEARS_WINDING_FACES)):
        scene = _scene(faces, verts)
        before = _geometry_blob(scene.objects[0])
        result, engine, counted, _plan, _corr = _b1_case(verts, faces)
        assert result["result"] == ExecutionOutcome.PRECONDITION_FAILED, label
        assert len(counted.calls) == 0, label
        assert _geometry_blob(engine.scene.objects[0]) == before, label


def test_b1_mq1_to_mq7_regression_on_a_renumbered_payload_case():
    """MQ-1..MQ-7 still run, in order, and only MQ-7's wording changed (class-level)."""
    result, _engine, counted, _plan, _corr = _b1_case(B1_REPRO_VERTS, B1_REPRO_FACES)
    assert [entry["reason"].split(":")[0] for entry in result["postcondition_results"]] == [
        "MQ-1", "MQ-2", "MQ-3", "MQ-4", "MQ-5", "MQ-6", "MQ-7"]
    assert [entry["ok"] for entry in result["postcondition_results"]] == [True] * 7
    reason = _mq7(result)[0]["reason"]
    assert "no finding class created or cleared" in reason
    assert "renumbered" in reason
    assert len(counted.calls) == 1
    # the MQ-1/MQ-3 fraud mutators still fire on this same accepted fixture
    scene = _scene(B1_REPRO_FACES, B1_REPRO_VERTS)
    plan, corr = _synthetic_plan_for(scene, _params_for(scene))
    fraud, _engine2, counted2 = _run(scene, plan, _artifact(plan, corr), mutator=_drop_face_mutator)
    assert fraud["result"] == ExecutionOutcome.POSTCONDITION_FAILED
    assert fraud["failure_code"] == "MQ-3"
    assert len(counted2.calls) == 1
    stale, _engine3, counted3 = _run(scene, plan, _artifact(plan, corr), mutator=_noop_mutator)
    assert stale["result"] == ExecutionOutcome.POSTCONDITION_FAILED
    assert stale["failure_code"] == "MQ-1"
    assert len(counted3.calls) == 1


def test_b1_valid_tail_mid_and_transitive_merges_still_complete():
    # tail-positioned group through the REAL planner
    scene = _scene(TAIL_FACES, TAIL_VERTS)
    plan, corr = _real_plan(scene, TAIL_VERTS, TAIL_FACES)
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.COMPLETED and len(counted.calls) == 1
    # mid-table group through the REAL planner (Wave 13: the planner now derives the PRE-state
    # survivor subsequence, so this shape no longer needs a contract-built plan)
    scene = _scene(MID_FACES, MID_VERTS)
    plan, corr = _real_plan(scene, MID_VERTS, MID_FACES)
    result, _engine, counted = _run(scene, plan, _artifact(plan, corr))
    assert result["result"] == ExecutionOutcome.COMPLETED and len(counted.calls) == 1
    assert result["removed_vertex_indices"] == [3]
    # transitive group of three with a renumbered pre-existing winding finding
    scene = _scene(TRANSITIVE_WINDING_FACES, TRANSITIVE_WINDING_VERTS)
    assert _groups_of(scene) == ((0, 1, 2),)
    pre_winding = _measured_of(scene.objects[0].mesh, "MESH_WINDING_INCONSISTENT")
    assert pre_winding == [{"edge": [0, 3], "faces": [0, 1]}]
    result, engine, counted = _run(scene, *_synthetic_plan_for_and_artifact(scene))
    assert result["result"] == ExecutionOutcome.COMPLETED and len(counted.calls) == 1
    assert result["removed_vertex_indices"] == [1, 2] and result["post_vertex_count"] == 4
    assert _measured_of(engine.scene.objects[0].mesh, "MESH_WINDING_INCONSISTENT") == [
        {"edge": [0, 1], "faces": [0, 1]}]


def _synthetic_plan_for_and_artifact(scene):
    """(plan, artifact) for a contract-valid plan over ``scene`` (convenience for the merge call)."""
    plan, corr = _synthetic_plan_for(scene, _params_for(scene))
    return plan, _artifact(plan, corr)


def test_b1_no_legal_case_mutates_and_then_reports_a_postcondition_failure():
    """The mandatory safety property, over every legal B-1 fixture.

    For a case that would previously have failed MQ-7 only because of harmless index renumbering,
    the executor must either accept it (exactly one mutation, COMPLETED) or refuse it BEFORE the
    mutation — it must never mutate and then report POSTCONDITION_FAILED. Each legal fixture is also
    checked to have no class count DECREASE, which is what makes the class-level guard's
    non-firing provable rather than accidental.
    """
    legal = (
        ("gate reproduction", B1_REPRO_VERTS, B1_REPRO_FACES),
        ("renumbered winding", WINDING_RENUM_VERTS, WINDING_RENUM_FACES),
        ("renumbered non-manifold", NONMANIFOLD_RENUM_VERTS, NONMANIFOLD_RENUM_FACES),
        ("renumbered duplicate face", DUPFACE_RENUM_VERTS, DUPFACE_RENUM_FACES),
        ("stable payload", TAIL_WINDING_STABLE_VERTS, TAIL_WINDING_STABLE_FACES),
        ("transitive group", TRANSITIVE_WINDING_VERTS, TRANSITIVE_WINDING_FACES),
        ("mid-table group", MID_VERTS, MID_FACES),
        ("tail group", TAIL_VERTS, TAIL_FACES),
    )
    for label, verts, faces in legal:
        scene = _scene(faces, verts)
        pre_counts = _counts_of(scene.objects[0].mesh)
        result, engine, counted, _plan, _corr = _b1_case(verts, faces)
        assert result["result"] != ExecutionOutcome.POSTCONDITION_FAILED, label
        assert result["result"] == ExecutionOutcome.COMPLETED, label
        assert len(counted.calls) == 1, label
        post_counts = _counts_of(engine.scene.objects[0].mesh)
        for code, count in pre_counts.items():
            if code == MERGE_CODE.value:
                assert post_counts.get(code, 0) == 0, label
                continue
            assert post_counts.get(code, 0) >= count, f"{label}: {code} was CLEARED"
        assert _mq7(result)[0]["ok"] is True, label
