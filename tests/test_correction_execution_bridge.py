import json

import subprocess

import pytest

from planning.blender.correction_authorization import mapping_digest
from planning.blender.correction_contract import CorrectionPlan, CorrectionProposal
from planning.blender.correction_execution_bridge import (
    BRIDGE_VERSION,
    CorrectionExecutionBridgeValidationError,
    _EXPECTED_OPERATIONS,
    make_bridge_request,
)
from planning.blender.correction_values import thaw_jsonable
from planning.blender.finding_codes import FindingCode, severity_of


SOURCE_DIGEST = "a" * 64
W1 = "REMOVE_DUPLICATE_FACE"
W1B = "REMOVE_DEGENERATE_FACE"
W2 = "REPAIR_FACE_WINDING"
W3 = "REPAIR_MERGE_VERTEX"


def _plan(
    correction_type,
    parameters,
    *,
    object_id="o",
    mesh_id="m",
    finding_code=None,
    determinism="DETERMINISTIC",
    requires_human_review=False,
):
    code = finding_code or {
        W1: FindingCode.MESH_DUPLICATE_FACE,
        W1B: FindingCode.MESH_DEGENERATE_FACE,
        W2: FindingCode.MESH_WINDING_INCONSISTENT,
        W3: FindingCode.MESH_DUPLICATE_VERTEX,
    }[correction_type]
    proposal = CorrectionProposal(
        correction_id=f"{correction_type}-id",
        finding_code=code.value,
        object_id=object_id,
        mesh_id=mesh_id,
        correction_type=correction_type,
        parameters=parameters,
        rationale="bridge deterministic contract test",
        preconditions=({"source_report_digest": SOURCE_DIGEST},),
        expected_postcondition={"bridge_contract": correction_type},
        risk="FIDELITY_GEOMETRY",
        severity=severity_of(code).value,
        reversibility="reversible" if correction_type in {W1, W1B} else "partially_reversible",
        dependencies=(),
        determinism=determinism,
        requires_human_review=requires_human_review,
        out_of_scope=False,
    )
    return CorrectionPlan(
        plan_id="",
        source_report_digest=SOURCE_DIGEST,
        source_revision_id=None,
        planner_version="1",
        profile={"name": "soccer-field", "version": "1"},
        corrections=(proposal,),
        dependencies=(),
        summary_metrics={},
        state="REVIEW_REQUIRED",
        planning_errors=(),
    )


def _w2_artifact(plan):
    return {
        "authorization_version": "1",
        "authorization_policy_version": "1",
        "decision": "APPROVED",
        "correction_type": W2,
        "correction_id": plan.corrections[0].correction_id,
        "plan_id": plan.plan_id,
        "source_report_digest": plan.source_report_digest,
        "authorized_by": "operator",
        "authorized_at_utc": "2026-09-19T22:00:00Z",
    }


def _w3_artifact(plan):
    return {
        "authorization_version": "1",
        "authorization_policy_version": "1",
        "decision": "APPROVED",
        "correction_type": W3,
        "correction_id": plan.corrections[0].correction_id,
        "plan_id": plan.plan_id,
        "source_report_digest": plan.source_report_digest,
        "authorized_by": "operator",
        "authorized_at_utc": "2026-09-19T22:00:00Z",
    }


def test_bridge_operation_allowlist_is_explicit_and_closed():
    assert _EXPECTED_OPERATIONS == {
        W1,
        W1B,
        W2,
        W3,
    }


def test_w1_request_uses_canonical_plan_and_binding():
    plan = _plan(
        W1,
        {"mesh_id": "m", "face_ids": [0, 1], "duplicate_relationship": "exact_duplicate"},
    )
    req = make_bridge_request(plan)
    assert req.operation == W1
    assert req.plan_id == plan.plan_id
    assert req.correction_id == plan.corrections[0].correction_id
    assert req.source_report_digest == SOURCE_DIGEST
    assert req.bridge_version == BRIDGE_VERSION
    assert len(req.expected_postcondition_digest) == 64
    assert req.digest() == req.digest()
    assert json.loads(req.canonical_json())["authorization"] is None


def test_future_executor_operation_is_refused_instead_of_becoming_bridge_executable(monkeypatch):
    plan = _plan(
        W1,
        {"mesh_id": "m", "face_ids": [0, 1], "duplicate_relationship": "exact_duplicate"},
    )
    import planning.blender.correction_execution_bridge as bridge

    monkeypatch.setattr(bridge, "_EXECUTABLE_TYPES", frozenset({"FUTURE_CORRECTION"}))
    with pytest.raises(CorrectionExecutionBridgeValidationError, match="allowlist drifted"):
        make_bridge_request(plan)


def test_w2_authorization_is_rejected_before_blender_request_construction_on_scope_mismatch():
    plan = _plan(
        W2,
        {
            "mesh_id": "m",
            "designated_face_index": 0,
            "candidate_faces": None,
            "recorded_edges": [[0, 1]],
            "counterpart_faces": [1],
            "orientation": "reverse_designated_face_to_shared_edge_opposite",
        },
        determinism="HEURISTIC",
        requires_human_review=True,
    )
    artifact = _w2_artifact(plan)
    artifact["plan_id"] = "b" * 64
    with pytest.raises(CorrectionExecutionBridgeValidationError, match="authorization rejected"):
        make_bridge_request(plan, authorization=artifact)


def test_w2_authorization_validates_without_engine_contact_and_is_not_success():
    plan = _plan(
        W2,
        {
            "mesh_id": "m",
            "designated_face_index": 0,
            "candidate_faces": None,
            "recorded_edges": [[0, 1]],
            "counterpart_faces": [1],
            "orientation": "reverse_designated_face_to_shared_edge_opposite",
        },
        determinism="HEURISTIC",
        requires_human_review=True,
    )
    req = make_bridge_request(plan, authorization=_w2_artifact(plan))
    assert req.authorization is not None
    assert req.expected_postcondition_ref.startswith("correction_executor:1:")


def test_w3_authorization_binding_uses_canonical_mapping_digest():
    mapping = [0, 0, 1]
    params = {
        "mesh_id": "m",
        "recorded_pairs": [[0, 1]],
        "duplicate_groups": [[0, 1]],
        "survivor_indices": [0],
        "old_to_new_mapping": mapping,
        "mapping_digest": mapping_digest("m", 3, tuple(mapping)),
        "all_groups_exact": True,
        "predicted_topology_unchanged": True,
    }
    plan = _plan(
        W3,
        params,
        determinism="DETERMINISTIC",
        requires_human_review=True,
    )
    req = make_bridge_request(plan, authorization=_w3_artifact(plan))
    assert req.operation == W3
    assert req.authorization["correction_type"] == W3


def test_no_arbitrary_python_is_present_in_bridge_request():
    plan = _plan(
        W1B,
        {"mesh_id": "m", "face_id": 0, "reason": "degenerate_face"},
    )
    req = make_bridge_request(plan)
    text = req.canonical_json()
    assert "python_expr" not in text
    assert "bpy.ops" not in text


def test_bridge_timeout_is_fail_closed_and_ambiguous(monkeypatch):
    from planning.blender.correction_execution_bridge import (
        CorrectionExecutionBridge,
    )

    plan = _plan(
        W1,
        {"mesh_id": "m", "face_ids": [0, 1], "duplicate_relationship": "exact_duplicate"},
    )

    def _timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="blender", timeout=1)

    monkeypatch.setattr(subprocess, "run", _timeout)

    result = CorrectionExecutionBridge(blender_command="blender", timeout=1).execute(plan)

    assert result.transport_ok is False
    assert result.transport_failure_code == "BLENDER_PROCESS_TIMEOUT"
    assert result.engine_evidence["process_disposed"] is True
    assert result.engine_evidence["ambiguous_result"] is True
    assert result.correction_result is None
