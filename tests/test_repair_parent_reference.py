
import copy

import pytest

from planning.blender.correction_authorization import (
    AUTHORIZATION_VERSION,
    DECISION_APPROVED,
    PARENT_CORRECTION_TYPE,
    AuthorizationArtifact,
    ParentPresentedWork,
    verify_parent_authorization,
    AuthorizationOutcome,
)
from planning.blender.correction_executor import ExecutionOutcome, execute_repair_parent_reference
from planning.blender.correction_planner import plan_parent_reference_correction
from planning.blender.correction_values import thaw_jsonable
from planning.blender.extraction_payload import PAYLOAD_SCHEMA_VERSION, payload_to_scene_model
from planning.blender.finding_codes import FindingCode
from planning.blender.kernel import run_scene_health, soccer_field_profile_default
from planning.blender.scene_report import REPORT_FORMAT_VERSION
from planning.blender.scene_model import ObjectModel, SceneModel

PROFILE = {"name": "soccer-field", "version": "1"}


def _payload(*, parent="ghost", include_other=True):
    objects = [{
        "object_id": "child",
        "name": "child",
        "collection": "Field",
        "parent_object_id": parent,
        "location": [0, 0, 0],
        "scale": [1, 1, 1],
        "rotation": [1, 0, 0, 0],
        "visible": True,
        "mesh": {
            "mesh_id": "child_mesh",
            "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            "faces": [[0, 1, 2]],
            "normals": None,
            "uvs": None,
            "materials": [],
            "local_frame_id": None,
        },
    }]
    if include_other:
        objects.append({
            "object_id": "unrelated",
            "name": "unrelated",
            "collection": "Structure",
            "parent_object_id": None,
            "location": [5, 5, 0],
            "scale": [1, 1, 1],
            "rotation": [1, 0, 0, 0],
            "visible": True,
            "mesh": None,
        })
    return {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "scene_id": "parent_ref_scene",
        "unit_system": "METERS",
        "coordinate_frame": None,
        "world_bounds": None,
        "objects": objects,
    }


def _scene_from_payload(payload):
    return payload_to_scene_model(payload)


def _report_payload(scene):
    report = run_scene_health(scene, soccer_field_profile_default())
    body = report.to_json_compatible()
    body["digest"] = report.digest()
    body["report_format_version"] = REPORT_FORMAT_VERSION
    return body


def _scene_input(payload):
    d = copy.deepcopy(payload)
    d.pop("schema_version")
    return d


def _plan(payload, object_id="child"):
    scene = _scene_from_payload(payload)
    outcome = plan_parent_reference_correction(
        _report_payload(scene), _scene_input(payload),
        object_id=object_id, profile=PROFILE,
    )
    return scene, outcome


def _auth(plan, correction):
    return AuthorizationArtifact(
        authorization_version=AUTHORIZATION_VERSION,
        authorization_policy_version="1",
        decision=DECISION_APPROVED,
        correction_type=PARENT_CORRECTION_TYPE,
        correction_id=correction.correction_id,
        plan_id=plan.plan_id,
        source_report_digest=plan.source_report_digest,
        authorized_by="test",
        authorized_at_utc="2026-09-14T00:00:00Z",
        scope_note="detach one dangling parent",
    )


def test_planner_emits_exactly_one_review_gated_dangling_parent_proposal():
    payload = _payload()
    _, outcome = _plan(payload)
    assert outcome.refusal_code is None
    assert outcome.plan.state == "REVIEW_REQUIRED"
    assert len(outcome.plan.corrections) == 1
    correction = outcome.plan.corrections[0]
    assert correction.correction_type == PARENT_CORRECTION_TYPE
    assert correction.object_id == "child"
    assert thaw_jsonable(correction.parameters) == {
        "expected_parent_id": "ghost",
        "detach_to": None,
    }
    assert correction.requires_human_review is True
    assert correction.determinism == "REQUIRES_REVIEW"


def test_planner_refuses_cycle_without_parent_payload():
    payload = _payload(parent="unrelated")
    _, outcome = _plan(payload)
    assert outcome.plan.corrections == ()
    assert outcome.plan.state == "NO_CORRECTIONS"

    cycle_payload = _payload(parent="b", include_other=False)
    cycle_payload["objects"][0]["object_id"] = "a"
    cycle_payload["objects"][0]["name"] = "a"
    cycle_payload["objects"][0]["parent_object_id"] = "b"
    cycle_payload["objects"].append({
        "object_id": "b", "name": "b", "collection": "Structure",
        "parent_object_id": "a", "location": [0, 0, 0], "scale": [1, 1, 1],
        "rotation": [1, 0, 0, 0], "visible": True, "mesh": None,
    })
    scene = _scene_from_payload(cycle_payload)
    outcome = plan_parent_reference_correction(
        _report_payload(scene), _scene_input(cycle_payload), object_id="a", profile=PROFILE
    )
    assert outcome.plan.corrections == ()
    assert outcome.plan.state != "REVIEW_REQUIRED"


def test_planner_requires_explicit_target_when_multiple_dangling_targets_exist():
    p = _payload()
    p["objects"][0]["object_id"] = "child_a"
    p["objects"][0]["name"] = "child_a"
    p["objects"].append(copy.deepcopy(p["objects"][0]))
    p["objects"][-1]["object_id"] = "child_b"
    p["objects"][-1]["name"] = "child_b"
    scene = _scene_from_payload(p)
    outcome = plan_parent_reference_correction(
        _report_payload(scene), _scene_input(p), profile=PROFILE
    )
    assert outcome.refusal_code == "MULTIPLE_DANGLING_TARGETS"
    assert outcome.plan.state == "REVIEW_REQUIRED"


def test_authorization_binds_parent_operation():
    payload = _payload()
    _, outcome = _plan(payload)
    correction = outcome.plan.corrections[0]
    auth = _auth(outcome.plan, correction)
    work = ParentPresentedWork(
        correction_type=PARENT_CORRECTION_TYPE,
        correction_id=correction.correction_id,
        plan_id=outcome.plan.plan_id,
        source_report_digest=outcome.plan.source_report_digest,
        object_id="child",
        expected_parent_id="ghost",
    )
    verdict = verify_parent_authorization(auth, work)
    assert verdict.ok is True
    assert verdict.outcome == AuthorizationOutcome.VERIFIED


def test_authorization_rejects_cross_plan():
    payload = _payload()
    _, outcome = _plan(payload)
    correction = outcome.plan.corrections[0]
    auth = _auth(outcome.plan, correction)
    work = ParentPresentedWork(
        correction_type=PARENT_CORRECTION_TYPE,
        correction_id=correction.correction_id,
        plan_id="0" * 64,
        source_report_digest=outcome.plan.source_report_digest,
        object_id="child",
        expected_parent_id="ghost",
    )
    verdict = verify_parent_authorization(auth, work)
    assert verdict.ok is False


def test_executor_success_changes_only_target_parent():
    payload = _payload()
    scene, outcome = _plan(payload)
    plan = outcome.plan
    correction = plan.corrections[0]
    auth = _auth(plan, correction)
    state = {"scene": scene, "calls": []}

    def extractor(_engine_state):
        return state["scene"], run_scene_health(state["scene"], soccer_field_profile_default())

    def mutator(_engine_state, **kwargs):
        state["calls"].append(kwargs)
        objs = []
        for obj in state["scene"].objects:
            if obj.object_id == kwargs["object_id"]:
                objs.append(ObjectModel(
                    object_id=obj.object_id, name=obj.name, collection=obj.collection,
                    parent_object_id=kwargs["new_parent_object_id"], location=obj.location,
                    scale=obj.scale, rotation=obj.rotation, visible=obj.visible, mesh=obj.mesh,
                ))
            else:
                objs.append(obj)
        state["scene"] = SceneModel(
            scene_id=state["scene"].scene_id,
            unit_system=state["scene"].unit_system,
            coordinate_frame=state["scene"].coordinate_frame,
            world_bounds=state["scene"].world_bounds,
            objects=tuple(objs),
        )

    receipt = execute_repair_parent_reference(
        engine_state=state, plan=plan, authorization=auth, mutator=mutator, extractor=extractor
    )
    assert receipt["result"] == ExecutionOutcome.COMPLETED
    assert receipt["failure_code"] is None
    assert len(state["calls"]) == 1
    assert state["scene"].objects[0].parent_object_id is None
    assert receipt["unrelated_objects_unchanged"] is True
    assert receipt["object_count_unchanged"] is True
    assert receipt["expected_parent_absent"] is True
    assert receipt["persisted"] is False
    assert receipt["rollback_performed"] is False


@pytest.mark.parametrize("attack", [
    "missing_auth",
    "wrong_type",
    "wrong_parent",
    "wrong_object",
    "extra_param",
    "non_none_detach",
])
def test_executor_negative_attacks_are_zero_mutation(attack):
    payload = _payload()
    scene, outcome = _plan(payload)
    plan = outcome.plan
    correction = plan.corrections[0]
    auth = _auth(plan, correction)
    if attack == "wrong_type":
        auth = AuthorizationArtifact(
            authorization_version=AUTHORIZATION_VERSION, authorization_policy_version="1",
            decision=DECISION_APPROVED, correction_type="REPAIR_FACE_WINDING",
            correction_id=correction.correction_id, plan_id=plan.plan_id,
            source_report_digest=plan.source_report_digest,
            authorized_by="test", authorized_at_utc="2026-09-14T00:00:00Z"
        )
    if attack in {"wrong_parent", "wrong_object", "extra_param", "non_none_detach"}:
        from planning.blender.correction_contract import CorrectionPlan, CorrectionProposal
        from planning.blender.correction_planner import _correction_id
        params = thaw_jsonable(correction.parameters)
        if attack == "wrong_parent":
            params["expected_parent_id"] = "different"
        elif attack == "wrong_object":
            target = "other"
        elif attack == "extra_param":
            params["unexpected"] = 1
        else:
            params["detach_to"] = "new-parent"
        target = "child" if attack != "wrong_object" else "other"
        bad = CorrectionProposal(
            correction_id=_correction_id(FindingCode.OBJECT_HIERARCHY_INVALID, target, None, params),
            finding_code=FindingCode.OBJECT_HIERARCHY_INVALID.value, object_id=target, mesh_id=None,
            correction_type=PARENT_CORRECTION_TYPE, parameters=params, rationale="attack",
            preconditions=(), expected_postcondition={"target_parent_object_id": None},
            risk="FIDELITY_TRANSFORM", severity="error", reversibility="reversible",
            dependencies=(), determinism="REQUIRES_REVIEW", requires_human_review=True, out_of_scope=False,
        )
        plan = CorrectionPlan(
            plan_id="", source_report_digest=plan.source_report_digest,
            source_revision_id=plan.source_revision_id, planner_version=plan.planner_version,
            profile=thaw_jsonable(plan.profile), corrections=(bad,), dependencies=(),
            summary_metrics=thaw_jsonable(plan.summary_metrics), state=plan.state, planning_errors=(),
        )
        auth = _auth(plan, bad) if attack != "wrong_object" else auth
    calls = []

    def mutator(_engine_state, **kwargs):
        calls.append(kwargs)

    receipt = execute_repair_parent_reference(
        engine_state={"scene": scene}, plan=plan,
        authorization=(None if attack == "missing_auth" else auth),
        mutator=mutator,
        extractor=lambda _state: (scene, run_scene_health(scene, soccer_field_profile_default())),
    )
    assert len(calls) == 0
    assert receipt["result"] != ExecutionOutcome.COMPLETED


def test_executor_rejects_non_parent_target_mutation_after_detach():
    payload = _payload()
    scene, outcome = _plan(payload)
    plan = outcome.plan
    correction = plan.corrections[0]
    auth = _auth(plan, correction)
    state = {"scene": scene, "calls": []}

    def extractor(_engine_state):
        return state["scene"], run_scene_health(state["scene"], soccer_field_profile_default())

    def mutator(_engine_state, **kwargs):
        state["calls"].append(kwargs)
        objs = []
        for obj in state["scene"].objects:
            if obj.object_id == kwargs["object_id"]:
                objs.append(ObjectModel(
                    object_id=obj.object_id, name=obj.name, collection=obj.collection,
                    parent_object_id=None, location=(9.0, 9.0, 9.0), scale=obj.scale,
                    rotation=obj.rotation, visible=obj.visible, mesh=obj.mesh,
                ))
            else:
                objs.append(obj)
        state["scene"] = SceneModel(
            scene_id=state["scene"].scene_id, unit_system=state["scene"].unit_system,
            coordinate_frame=state["scene"].coordinate_frame, world_bounds=state["scene"].world_bounds,
            objects=tuple(objs),
        )

    receipt = execute_repair_parent_reference(
        engine_state=state, plan=plan, authorization=auth, mutator=mutator, extractor=extractor
    )
    assert receipt["result"] == ExecutionOutcome.POSTCONDITION_FAILED
    assert receipt["failure_code"] == "TARGET_NON_PARENT_STATE_CHANGED"
    assert receipt["target_non_parent_state_unchanged"] is False
    assert len(state["calls"]) == 1
