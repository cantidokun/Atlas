"""Deterministic invariants for the engine-neutral Unreal result contract."""

import pytest

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_production_controller_integration import UnrealProductionControllerEvent
from planning.unreal_production_result_contract import (
    UnrealProductionResultContract,
    normalize_unreal_production_event,
)
from planning.unreal_production_runtime_adapter import UnrealProductionRuntimeSnapshot
from planning.unreal_render_receipt import UnrealRenderReceipt


def _snapshot(
    state: str = "complete",
    *,
    failure=None,
    waiting_for_reassessment: bool = False,
    waiting_for_replacement: bool = False,
    required_authorizations: tuple = (),
) -> UnrealProductionRuntimeSnapshot:
    return UnrealProductionRuntimeSnapshot(
        state=state,
        phase=state,
        waiting_for_reassessment=waiting_for_reassessment,
        waiting_for_replacement=waiting_for_replacement,
        failure=failure,
        recovery=None,
        required_authorizations=required_authorizations,
    )


def _evidence(*, status: str = "finished", job_id: str = "job-1") -> UnrealEvidence:
    return UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=("FIELD_SURFACE",),
        observed_state={
            "job_id": job_id,
            "sequence_asset_path": "/Game/Trusted/Sequence",
            "status": status,
            "finished": True,
            "success": True,
            "failed": False,
            "output_files": ["Saved/AtlasRenderOutput/AtlasRender_0001.png"],
        },
        verified=True,
        source="result-contract-test",
    )


def test_non_workflow_complete_event_has_successful_unverified_render_contract():
    event = UnrealProductionControllerEvent(
        operation="start",
        snapshot=_snapshot("complete"),
    )

    result = normalize_unreal_production_event(event)

    assert result.success is True
    assert result.completion_state == "complete"
    assert result.required_authorizations == ()
    assert result.verified_render is False
    assert result.final_evidence is None
    assert result.receipt is None


def test_non_workflow_reassessment_state_remains_unsuccessful_and_exposes_required_authorization():
    event = UnrealProductionControllerEvent(
        operation="start",
        snapshot=_snapshot(
            "awaiting_reassessment",
            failure={"phase": "production"},
            waiting_for_reassessment=True,
            required_authorizations=("reassessment",),
        ),
    )

    result = normalize_unreal_production_event(event)

    assert result.success is False
    assert result.completion_state == "awaiting_reassessment"
    assert result.required_authorizations == ("reassessment",)
    assert result.verified_render is False


def test_non_workflow_replacement_state_remains_unsuccessful_and_exposes_required_authorization():
    event = UnrealProductionControllerEvent(
        operation="reassess",
        snapshot=_snapshot(
            "awaiting_replacement",
            failure={"phase": "recovery"},
            waiting_for_replacement=True,
            required_authorizations=("replacement",),
        ),
    )

    result = normalize_unreal_production_event(event)

    assert result.success is False
    assert result.completion_state == "awaiting_replacement"
    assert result.required_authorizations == ("replacement",)
    assert result.verified_render is False


def test_result_contract_rejects_success_for_non_terminal_snapshot():
    with pytest.raises(
        ValueError,
        match="successful result must have a terminal production snapshot state",
    ):
        UnrealProductionResultContract(
            operation="start",
            snapshot=_snapshot(
                "awaiting_reassessment",
                waiting_for_reassessment=True,
                required_authorizations=("reassessment",),
            ),
            success=True,
        )


def test_result_contract_rejects_success_with_pending_or_failure_state():
    with pytest.raises(
        ValueError,
        match="successful result cannot contain failure, pending recovery, or required authorization state",
    ):
        UnrealProductionResultContract(
            operation="start",
            snapshot=_snapshot(
                "complete",
                failure={"phase": "production"},
            ),
            success=True,
        )


def test_result_contract_rejects_receipt_without_paired_evidence():
    evidence = _evidence()
    receipt = UnrealRenderReceipt.issue(evidence)

    with pytest.raises(ValueError, match="receipt requires paired final_evidence"):
        UnrealProductionResultContract(
            operation="start",
            snapshot=_snapshot(),
            success=True,
            job_id=receipt.job_id,
            receipt=receipt,
        )


def test_result_contract_rejects_unverified_render_evidence():
    evidence = UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=("FIELD_SURFACE",),
        observed_state={"job_id": "job-1"},
        verified=False,
        source="result-contract-test",
    )

    with pytest.raises(ValueError, match="final_evidence must be verified"):
        UnrealProductionResultContract(
            operation="start",
            snapshot=_snapshot(),
            success=True,
            job_id="job-1",
            final_evidence=evidence,
        )


def test_result_contract_rejects_non_render_evidence_operation():
    evidence = UnrealEvidence(
        operation_name="inspect_sequencer_state",
        entity_ids=("FIELD_SURFACE",),
        observed_state={"job_id": "job-1"},
        verified=True,
        source="result-contract-test",
    )

    with pytest.raises(ValueError, match="final_evidence must come from inspect_render_job"):
        UnrealProductionResultContract(
            operation="start",
            snapshot=_snapshot(),
            success=True,
            job_id="job-1",
            final_evidence=evidence,
        )


def test_result_contract_rejects_evidence_job_mismatch():
    evidence = _evidence(job_id="observed-job")

    with pytest.raises(ValueError, match="job_id does not match final_evidence"):
        UnrealProductionResultContract(
            operation="start",
            snapshot=_snapshot(),
            success=True,
            job_id="declared-job",
            final_evidence=evidence,
        )


def test_result_contract_rejects_receipt_evidence_digest_mismatch():
    receipt = UnrealRenderReceipt.issue(_evidence(status="finished", job_id="job-1"))
    changed_evidence = _evidence(status="changed", job_id="job-1")

    with pytest.raises(ValueError, match="receipt does not match final_evidence"):
        UnrealProductionResultContract(
            operation="start",
            snapshot=_snapshot(),
            success=True,
            job_id="job-1",
            final_evidence=changed_evidence,
            receipt=receipt,
        )


def test_matching_evidence_and_receipt_form_verified_render_contract():
    evidence = _evidence()
    receipt = UnrealRenderReceipt.issue(evidence)

    result = UnrealProductionResultContract(
        operation="start",
        snapshot=_snapshot(),
        success=True,
        intent_id="intent-1",
        job_id=receipt.job_id,
        final_evidence=evidence,
        receipt=receipt,
    )

    assert result.verified_render is True
    assert result.receipt.matches(result.final_evidence) is True
