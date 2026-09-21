"""Deterministic unit tests for Milestone 3 Atlas Submission / Idempotency Integration.

Coverage:
1. Durable intent exists before transport send
2. Atlas-generated job ID
3. Strict job ID / path validation
4. Isolated output directory (<parent>/<atlas_job_id>/)
5. Deterministic request digest
6. Deterministic config digest
7. Exclusive per-job claim requirement
8. Successful submission binds Unreal identity and session identity
9. Capability mismatch blocks dispatch
10. Timeout becomes RECOVERY_PENDING without resubmission
11. Disconnect becomes RECOVERY_PENDING without resubmission
12. Authoritative engine rejection -> FAILED
13. ERR_JOB_ID_CONFLICT -> RECOVERY_FAILED
14. Same-job idempotency (matching parameters)
15. Conflicting same-job submission rejection (differing parameters)
16. Terminal record blocks submission
17. Corrupt record blocks submission
18. Stale-writer rejection on update
19. Receipt-first skips submission and repairs record to FINALIZED
20. No synthetic successful execution state from disk artifacts
21. Authoritative fields remain unchanged after observed identity binding
22. Session identity persisted exactly as observed
23. Transport called exactly once on acceptance-unknown
24. Phase-C: a valid durable intent carries authorization_id / attempt_nonce / attempt_ordinal
25. Phase-C: the durable record owns the identity policy (blank/absent => violation)
26. Phase-C: an identity violation fails closed before the capability assertion and
    before any transport dispatch (nothing is transmitted)
27. Phase-C: the engine capability assertion remains authoritative with a valid identity
28. Phase-C: the submission surface stays singular (no intent-only/duplicate authority)
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Mapping
import pytest

from planning.unreal_adapter_production import (
    REQUIRED_RECOVERY_CAPABILITIES,
    UnrealAdapterProduction,
)
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_render_contract import (
    UnrealRenderConfig,
    compute_render_config_digest,
    compute_render_request_digest,
    derive_isolated_output_directory,
)
from planning.unreal_render_job_record import (
    AtlasRenderJobRecord,
    AtlasRenderJobRecordError,
    validate_canonical_atlas_job_id,
)
from planning.unreal_render_job_states import (
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
from planning.unreal_render_job_store import (
    AtlasRenderJobStore,
    AtlasRenderJobStoreError,
    AtlasRenderJobStoreLockError,
    AtlasRenderJobStoreStaleWriterError,
)
from planning.unreal_render_receipt import UnrealRenderReceipt
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_submission import (
    RenderSubmissionResult,
    UnrealRenderSubmissionError,
    UnrealRenderSubmissionService,
)
from planning.unreal_transport_contract import (
    UnrealTransportRequest,
    UnrealTransportResponse,
)
from planning.unreal_transport_named_pipe import (
    NamedPipeTransportDisconnectedError,
    NamedPipeTransportTimeoutError,
)


class MockUnrealTransport:
    def __init__(self, handler=None):
        self.handler = handler or self.default_handler
        self.sent_requests: list[UnrealTransportRequest] = []
        self.send_call_count = 0

    def default_handler(self, request: UnrealTransportRequest) -> UnrealTransportResponse:
        if request.operation_name == "get_capabilities":
            return UnrealTransportResponse(
                request_id=request.request_id,
                operation_name=request.operation_name,
                entity_ids=request.entity_ids,
                success=True,
                observed_state={"capabilities": list(REQUIRED_RECOVERY_CAPABILITIES)},
                error="",
                source="unreal-editor-5.6",
                schema_version=1,
                error_code="",
                session_identity={
                    "editor_session_id": "sess-test-ue56",
                    "process_id": 4321,
                    "process_creation_time_utc": "2026-09-06T00:00:00Z",
                    "server_start_time_utc": "2026-09-06T00:00:01Z",
                    "engine_version": "5.6",
                    "project_identity": "AtlasUnrealHarness",
                },
            )
        elif request.operation_name == "submit_render":
            atlas_id = request.arguments.get("atlas_job_id", "job-unreal-default")
            return UnrealTransportResponse(
                request_id=request.request_id,
                operation_name=request.operation_name,
                entity_ids=request.entity_ids,
                success=True,
                observed_state={
                    "render_job": {
                        "job_id": "unreal-guid-12345",
                        "atlas_job_id": atlas_id,
                        "status": "submitted",
                        "progress": 0.0,
                    }
                },
                error="",
                source="unreal-editor-5.6",
                schema_version=1,
                error_code="",
                session_identity={
                    "editor_session_id": "sess-test-ue56",
                    "process_id": 4321,
                    "process_creation_time_utc": "2026-09-06T00:00:00Z",
                    "server_start_time_utc": "2026-09-06T00:00:01Z",
                    "engine_version": "5.6",
                    "project_identity": "AtlasUnrealHarness",
                },
            )
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=False,
            observed_state={},
            error="Unhandled mock operation",
            source="mock",
            schema_version=1,
            error_code="ERR_UNHANDLED",
            session_identity={},
        )

    def send(self, request: UnrealTransportRequest) -> UnrealTransportResponse:
        self.sent_requests.append(request)
        self.send_call_count += 1
        return self.handler(request)


def _default_render_config():
    return UnrealRenderConfig(
        width=1920,
        height=1080,
        start_frame=0,
        end_frame=24,
        output_directory="placeholder",
        output_format="png",
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_durable_intent_persisted_before_transport_send(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockTransportWithPreSendAssert(store)
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)

    result = service.submit_render(
        authorization_id="auth-m3-test",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/Test.Test",
        output_parent_directory="C:/Renders",
        render_config=_default_render_config(),
    )

    assert result.record.lifecycle_state == RenderJobLifecycleState.SUBMITTED
    assert result.record.unreal_job_id == "unreal-guid-12345"
    assert store.exists(result.record.atlas_job_id)


class MockTransportWithPreSendAssert(MockUnrealTransport):
    def __init__(self, store: AtlasRenderJobStore):
        super().__init__()
        self._store = store

    def send(self, request: UnrealTransportRequest) -> UnrealTransportResponse:
        if request.operation_name == "submit_render":
            atlas_id = request.arguments["atlas_job_id"]
            # Assert file is already on disk in PENDING_SUBMISSION state before transport send!
            assert self._store.exists(atlas_id), "Durable intent record MUST exist before send()"
            record = self._store.load(atlas_id)
            assert record.lifecycle_state == RenderJobLifecycleState.PENDING_SUBMISSION
        return super().send(request)


def test_atlas_generated_job_id_and_isolated_output_path(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport()
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)

    result = service.submit_render(
        authorization_id="auth-m3-test",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/Test.Test",
        output_parent_directory="C:/Renders",
        render_config=_default_render_config(),
    )

    record = result.record
    assert record.atlas_job_id.startswith("atlas-render-job-")
    assert record.output_directory == f"C:/Renders/{record.atlas_job_id}"
    # Verify attempt_nonce is generated and passed
    assert record.attempt_nonce is not None
    assert len(record.attempt_nonce) == 64
    # Verify submit_render request received the exact isolated output_directory
    submit_req = [r for r in transport.sent_requests if r.operation_name == "submit_render"][0]
    assert submit_req.arguments["output_directory"] == f"C:/Renders/{record.atlas_job_id}"
    assert submit_req.arguments["attempt_nonce"] == record.attempt_nonce


def test_strict_job_id_and_path_validation():
    with pytest.raises(AtlasRenderJobRecordError, match="illegal path characters"):
        derive_isolated_output_directory("C:/Renders", "atlas-render-job-../hack")
    with pytest.raises(AtlasRenderJobRecordError, match="canonical identifier format"):
        derive_isolated_output_directory("C:/Renders", "not-a-uuid")


def test_deterministic_digests():
    cfg1 = _default_render_config()
    cfg2 = _default_render_config()
    d1 = compute_render_config_digest(cfg1)
    d2 = compute_render_config_digest(cfg2)
    assert d1 == d2
    assert len(d1) == 64

    req_d1 = compute_render_request_digest(
        sequence_asset_path="/Game/Test.Test",
        output_directory="C:/Renders/job-1",
        config_digest=d1,
        authorization_id="auth-1",
        entity_ids=("FIELD_SURFACE",),
    )
    req_d2 = compute_render_request_digest(
        sequence_asset_path="/Game/Test.Test",
        output_directory="C:/Renders/job-1",
        config_digest=d2,
        authorization_id="auth-1",
        entity_ids=("FIELD_SURFACE",),
    )
    assert req_d1 == req_d2
    assert len(req_d1) == 64


def test_exclusive_per_job_claim_requirement(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport()
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)

    atlas_id = "atlas-render-job-77777777-8888-9999-aaaa-bbbbbbbbbbbb"
    # Hold exclusive job claim in background
    with store.acquire_job_claim(atlas_id, "external-worker"):
        with pytest.raises(AtlasRenderJobStoreLockError, match="Exclusive execution claim"):
            service.submit_render(
                authorization_id="auth-test",
                canonical_digital_twin_id="twin-test",
                sequence_asset_path="/Game/Test.Test",
                output_parent_directory="C:/Renders",
                render_config=_default_render_config(),
                existing_atlas_job_id=atlas_id,
            )


def test_successful_submission_binds_unreal_and_session_identity(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport()
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)

    result = service.submit_render(
        authorization_id="auth-m3-test",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/Test.Test",
        output_parent_directory="C:/Renders",
        render_config=_default_render_config(),
    )

    rec = result.record
    assert rec.lifecycle_state == RenderJobLifecycleState.SUBMITTED
    assert rec.recovery_status == RenderJobRecoveryStatus.NONE
    assert rec.unreal_job_id == "unreal-guid-12345"
    assert rec.origin_editor_session_id == "sess-test-ue56"
    assert rec.origin_process_id == 4321
    assert rec.origin_process_creation_time == "2026-09-06T00:00:00Z"
    assert rec.engine_accepted_at is not None
    assert rec.last_observed_revision == 1


def test_capability_mismatch_blocks_dispatch(tmp_path):
    def missing_caps_handler(request):
        if request.operation_name == "get_capabilities":
            return UnrealTransportResponse(
                request_id=request.request_id,
                operation_name=request.operation_name,
                entity_ids=request.entity_ids,
                success=True,
                observed_state={"capabilities": ["atlas_job_id"]},  # Missing required capabilities
                error="",
                source="unreal-editor-5.6",
                schema_version=1,
                error_code="",
                session_identity={},
            )
        pytest.fail("submit_render must not be called if capabilities mismatch!")

    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport(handler=missing_caps_handler)
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)

    atlas_id = "atlas-render-job-cccccccc-dddd-eeee-ffff-000000000000"
    with pytest.raises(UnrealRenderSubmissionError, match="capability gate"):
        service.submit_render(
            authorization_id="auth-test",
            canonical_digital_twin_id="twin-test",
            sequence_asset_path="/Game/Test.Test",
            output_parent_directory="C:/Renders",
            render_config=_default_render_config(),
            existing_atlas_job_id=atlas_id,
        )

    # Verify record was marked FAILED on disk
    rec = store.load(atlas_id)
    assert rec.lifecycle_state == RenderJobLifecycleState.FAILED
    assert "capability assertion failed" in (rec.failure_reason or "")


def test_transport_timeout_becomes_recovery_pending_without_resubmission(tmp_path):
    def timeout_handler(request):
        if request.operation_name == "get_capabilities":
            return MockUnrealTransport().default_handler(request)
        elif request.operation_name == "submit_render":
            raise NamedPipeTransportTimeoutError("Named pipe read timed out")
        raise RuntimeError("Unexpected operation")

    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport(handler=timeout_handler)
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)

    result = service.submit_render(
        authorization_id="auth-timeout-test",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/Test.Test",
        output_parent_directory="C:/Renders",
        render_config=_default_render_config(),
    )

    assert result.acceptance_unknown is True
    assert result.record.lifecycle_state == RenderJobLifecycleState.PENDING_SUBMISSION
    assert result.record.recovery_status == RenderJobRecoveryStatus.RECOVERY_PENDING
    assert result.record.recovery_attempts_or_ambiguity_count == 1
    assert "Transport uncertainty" in (result.record.failure_reason or "")
    # Transport was called exactly once for submit_render (NO blind resubmission)
    submit_calls = [r for r in transport.sent_requests if r.operation_name == "submit_render"]
    assert len(submit_calls) == 1


def test_transport_disconnect_becomes_recovery_pending_without_resubmission(tmp_path):
    def disconnect_handler(request):
        if request.operation_name == "get_capabilities":
            return MockUnrealTransport().default_handler(request)
        elif request.operation_name == "submit_render":
            raise NamedPipeTransportDisconnectedError("Named pipe server disconnected")
        raise RuntimeError("Unexpected operation")

    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport(handler=disconnect_handler)
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)

    result = service.submit_render(
        authorization_id="auth-disconnect-test",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/Test.Test",
        output_parent_directory="C:/Renders",
        render_config=_default_render_config(),
    )

    assert result.acceptance_unknown is True
    assert result.record.lifecycle_state == RenderJobLifecycleState.PENDING_SUBMISSION
    assert result.record.recovery_status == RenderJobRecoveryStatus.RECOVERY_PENDING


def test_engine_conflict_rejection_transitions_to_recovery_failed(tmp_path):
    def conflict_handler(request):
        if request.operation_name == "get_capabilities":
            return MockUnrealTransport().default_handler(request)
        elif request.operation_name == "submit_render":
            return UnrealTransportResponse(
                request_id=request.request_id,
                operation_name=request.operation_name,
                entity_ids=request.entity_ids,
                success=False,
                observed_state={},
                error="Conflicting reuse of existing atlas_job_id",
                source="unreal-editor-5.6",
                schema_version=1,
                error_code="ERR_JOB_ID_CONFLICT",
                session_identity={},
            )
        raise RuntimeError("Unexpected operation")

    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport(handler=conflict_handler)
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)

    result = service.submit_render(
        authorization_id="auth-conflict-test",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/Test.Test",
        output_parent_directory="C:/Renders",
        render_config=_default_render_config(),
    )

    assert result.rejection_code == "ERR_JOB_ID_CONFLICT"
    assert result.record.lifecycle_state == RenderJobLifecycleState.RECOVERY_FAILED


def test_authoritative_engine_rejection_transitions_to_failed(tmp_path):
    def reject_handler(request):
        if request.operation_name == "get_capabilities":
            return MockUnrealTransport().default_handler(request)
        elif request.operation_name == "submit_render":
            return UnrealTransportResponse(
                request_id=request.request_id,
                operation_name=request.operation_name,
                entity_ids=request.entity_ids,
                success=False,
                observed_state={},
                error="Level sequence asset not found",
                source="unreal-editor-5.6",
                schema_version=1,
                error_code="ERR_SEQUENCE_NOT_FOUND",
                session_identity={},
            )
        raise RuntimeError("Unexpected operation")

    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport(handler=reject_handler)
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)

    result = service.submit_render(
        authorization_id="auth-reject-test",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/MissingSequence",
        output_parent_directory="C:/Renders",
        render_config=_default_render_config(),
    )

    assert result.record.lifecycle_state == RenderJobLifecycleState.FAILED


def test_idempotent_duplicate_submission(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport()
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)

    atlas_id = "atlas-render-job-11111111-2222-3333-4444-555555555555"
    kwargs = dict(
        authorization_id="auth-idem-test",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/Test.Test",
        output_parent_directory="C:/Renders",
        render_config=_default_render_config(),
        existing_atlas_job_id=atlas_id,
    )

    res1 = service.submit_render(**kwargs)
    assert res1.is_duplicate is False
    assert res1.record.lifecycle_state == RenderJobLifecycleState.SUBMITTED

    # Second submission with identical parameters
    res2 = service.submit_render(**kwargs)
    assert res2.is_duplicate is True
    assert res2.record == res1.record
    # Only 1 submit_render transport request was dispatched!
    submit_calls = [r for r in transport.sent_requests if r.operation_name == "submit_render"]
    assert len(submit_calls) == 1


def test_conflicting_same_job_submission_rejected(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport()
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)

    atlas_id = "atlas-render-job-11111111-2222-3333-4444-555555555555"
    service.submit_render(
        authorization_id="auth-orig",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/SeqA",
        output_parent_directory="C:/Renders",
        render_config=_default_render_config(),
        existing_atlas_job_id=atlas_id,
    )

    # Submitting same atlas_id with different sequence must fail closed
    with pytest.raises(UnrealRenderSubmissionError, match="Conflicting reuse"):
        service.submit_render(
            authorization_id="auth-orig",
            canonical_digital_twin_id="twin-test",
            sequence_asset_path="/Game/SeqB_DIFFERENT",
            output_parent_directory="C:/Renders",
            render_config=_default_render_config(),
            existing_atlas_job_id=atlas_id,
        )


def test_terminal_record_blocks_submission(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport()
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)

    atlas_id = "atlas-render-job-11111111-2222-3333-4444-555555555555"
    res = service.submit_render(
        authorization_id="auth-term",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/Test.Test",
        output_parent_directory="C:/Renders",
        render_config=_default_render_config(),
        existing_atlas_job_id=atlas_id,
    )

    # Transition record to FAILED
    failed = res.record.transition(lifecycle_state=RenderJobLifecycleState.FAILED)
    store.update(failed, expected_revision=res.record.last_observed_revision)

    # Attempting to submit again must be rejected
    with pytest.raises(UnrealRenderSubmissionError, match="record is terminal"):
        service.submit_render(
            authorization_id="auth-term",
            canonical_digital_twin_id="twin-test",
            sequence_asset_path="/Game/Test.Test",
            output_parent_directory="C:/Renders",
            render_config=_default_render_config(),
            existing_atlas_job_id=atlas_id,
        )


def test_corrupt_record_blocks_submission(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport()
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)

    atlas_id = "atlas-render-job-11111111-2222-3333-4444-555555555555"
    service.submit_render(
        authorization_id="auth-corrupt",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/Test.Test",
        output_parent_directory="C:/Renders",
        render_config=_default_render_config(),
        existing_atlas_job_id=atlas_id,
    )

    # Corrupt the record file on disk
    file_path = store._job_file_path(atlas_id)
    file_path.write_text("CORRUPTED_JSON", encoding="utf-8")

    # Re-submitting must fail closed and quarantine
    with pytest.raises(Exception):
        service.submit_render(
            authorization_id="auth-corrupt",
            canonical_digital_twin_id="twin-test",
            sequence_asset_path="/Game/Test.Test",
            output_parent_directory="C:/Renders",
            render_config=_default_render_config(),
            existing_atlas_job_id=atlas_id,
        )


def test_receipt_first_skips_submission_and_repairs(tmp_path):
    receipt_file = tmp_path / "render-receipt.json"
    receipt_store = UnrealRenderReceiptStore(receipt_file)

    evidence = UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=("FIELD_SURFACE",),
        observed_state={
            "job_id": "job-existing-receipt-999",
            "status": "finished",
            "finished": True,
            "success": True,
            "failed": False,
            "sequence_asset_path": "/Game/Test.Test",
            "output_directory": "Saved/AtlasRenderOutput",
            "output_format": "png",
            "output_files": ["C:/Renders/frame_001.png"],
        },
        verified=True,
        source="unreal-editor-5.6",
    )
    receipt = UnrealRenderReceipt.issue(evidence)
    receipt_store.save(receipt)

    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport()
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
    )

    result = service.submit_render(
        authorization_id="auth-receipt-first",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/Test.Test",
        output_parent_directory="C:/Renders",
        render_config=_default_render_config(),
    )

    assert result.is_repaired_from_receipt is True
    assert result.record.lifecycle_state == RenderJobLifecycleState.FINALIZED
    assert result.record.unreal_job_id == "job-existing-receipt-999"
    # Ensure NO submit_render calls were made over transport
    submit_calls = [r for r in transport.sent_requests if r.operation_name == "submit_render"]
    assert len(submit_calls) == 0


def test_receipt_first_rejects_unrelated_sequence_receipt(tmp_path):
    receipt_file = tmp_path / "render-receipt.json"
    receipt_store = UnrealRenderReceiptStore(receipt_file)

    evidence = UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=("FIELD_SURFACE",),
        observed_state={
            "job_id": "job-other-seq-999",
            "status": "finished",
            "finished": True,
            "success": True,
            "failed": False,
            "sequence_asset_path": "/Game/OtherSequence.OtherSequence",
            "output_directory": "Saved/AtlasRenderOutput",
            "output_format": "png",
            "output_files": ["C:/Renders/frame_001.png"],
        },
        verified=True,
        source="unreal-editor-5.6",
    )
    receipt = UnrealRenderReceipt.issue(evidence)
    receipt_store.save(receipt)

    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport()
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
    )

    # Submitting for /Game/Test.Test should NOT adopt the receipt for /Game/OtherSequence
    result = service.submit_render(
        authorization_id="auth-diff-seq",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/Test.Test",
        output_parent_directory="C:/Renders",
        render_config=_default_render_config(),
    )

    assert result.is_repaired_from_receipt is False
    assert result.record.lifecycle_state == RenderJobLifecycleState.SUBMITTED
    assert result.record.unreal_job_id == "unreal-guid-12345"
    submit_calls = [r for r in transport.sent_requests if r.operation_name == "submit_render"]
    assert len(submit_calls) == 1



def test_receipt_first_rejects_corrupted_receipt_file(tmp_path):
    receipt_file = tmp_path / "render-receipt.json"
    receipt_file.write_text("CORRUPTED_RECEIPT_JSON", encoding="utf-8")
    receipt_store = UnrealRenderReceiptStore(receipt_file)

    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport()
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
    )

    # Corrupt receipt file must NOT create synthetic success or repair
    result = service.submit_render(
        authorization_id="auth-corrupt-rcpt",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/Test.Test",
        output_parent_directory="C:/Renders",
        render_config=_default_render_config(),
    )

    assert result.is_repaired_from_receipt is False
    assert result.record.lifecycle_state == RenderJobLifecycleState.SUBMITTED
    assert result.record.unreal_job_id == "unreal-guid-12345"
    submit_calls = [r for r in transport.sent_requests if r.operation_name == "submit_render"]
    assert len(submit_calls) == 1


def test_stale_writer_rejected_on_submission_update(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport()
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)

    atlas_id = "atlas-render-job-11111111-2222-3333-4444-555555555555"

    # Pre-populate intent record with revision 0
    intent = AtlasRenderJobRecord.create_intent(
        atlas_job_id=atlas_id,
        attempt_ordinal=1,
        authorization_id="auth-stale",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/Test.Test",
        request_digest=compute_render_request_digest(
            sequence_asset_path="/Game/Test.Test",
            output_directory=f"C:/Renders/{atlas_id}",
            config_digest=compute_render_config_digest(_default_render_config()),
            authorization_id="auth-stale",
            entity_ids=("FIELD_SURFACE",),
        ),
        config_digest=compute_render_config_digest(_default_render_config()),
        output_parent_directory="C:/Renders",
        output_directory=f"C:/Renders/{atlas_id}",
        expected_output_spec={"format": "png", "width": 1920, "height": 1080, "start_frame": 0, "end_frame": 24},
        created_at="2026-09-06T00:00:00Z",
    )
    store.create(intent)

    # Concurrently bump revision on disk to 1
    bumped = intent.transition(
        failure_reason="Concurrent external modification",
    )
    store.update(bumped, expected_revision=0)

    # Now simulate a service running with stale cached revision 0 and attempting update
    stale_attempt = intent.transition(
        lifecycle_state=RenderJobLifecycleState.SUBMITTED,
    )
    with pytest.raises(AtlasRenderJobStoreStaleWriterError, match="Stale writer"):
        store.update(stale_attempt, expected_revision=0)


def test_disallowed_synthetic_success_from_disk_artifacts():
    kwargs = {
        "atlas_job_id": "atlas-render-job-00000000-1111-2222-3333-444444444444",
        "attempt_ordinal": 1,
        "authorization_id": "auth-synthetic",
        "canonical_digital_twin_id": "twin-test",
        "sequence_asset_path": "/Game/Test.Test",
        "request_digest": "req-d",
        "config_digest": "cfg-d",
        "output_parent_directory": "C:/Renders",
        "output_directory": "C:/Renders/atlas-render-job-00000000-1111-2222-3333-444444444444",
        "expected_output_spec": {"format": "png"},
        "created_at": "2026-09-06T00:00:00Z",
    }
    rec = AtlasRenderJobRecord.create_intent(**kwargs)
    # Attempting transition to VERIFIED or FINALIZED without attributable engine job ID fails closed
    with pytest.raises(AtlasRenderJobRecordError, match="attributable engine job identity"):
        rec.transition(lifecycle_state=RenderJobLifecycleState.VERIFIED)
    with pytest.raises(AtlasRenderJobRecordError, match="attributable engine job identity"):
        rec.transition(lifecycle_state=RenderJobLifecycleState.FINALIZED)


def test_session_identity_persisted_exactly_as_observed(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport()
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)

    res = service.submit_render(
        authorization_id="auth-sess-test",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/Test.Test",
        output_parent_directory="C:/Renders",
        render_config=_default_render_config(),
    )

    rec = res.record
    assert rec.origin_editor_session_id == "sess-test-ue56"
    assert rec.origin_process_id == 4321
    assert rec.origin_process_creation_time == "2026-09-06T00:00:00Z"


def test_authoritative_fields_remain_unchanged_after_submission(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport()
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)

    result = service.submit_render(
        authorization_id="auth-invariant-test",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/Test.Test",
        output_parent_directory="C:/Renders",
        render_config=_default_render_config(),
    )

    rec = result.record
    # Authoritative digest must match original computed digest
    assert len(rec.authoritative_digest) == 64
    assert rec.sequence_asset_path == "/Game/Test.Test"
    assert rec.authorization_id == "auth-invariant-test"
    assert rec.canonical_digital_twin_id == "twin-test"
    assert rec.output_directory == f"C:/Renders/{rec.atlas_job_id}"


# ── Phase-C submission-identity invariant (F-M7-2 follow-up) ──────────────────


def _identity_submission_kwargs() -> dict:
    return dict(
        authorization_id="auth-phase-c-test",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/Test.Test",
        output_parent_directory="C:/Renders",
        render_config=_default_render_config(),
    )


def _submit_once_for_identity(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport()
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)
    result = service.submit_render(**_identity_submission_kwargs())
    return store, transport, service, store.load(result.record.atlas_job_id)


def test_valid_durable_intent_carries_required_submission_identity(tmp_path):
    """(1) A valid durable intent carries non-empty authorization_id, non-empty
    attempt_nonce and a valid attempt_ordinal, per the record's own policy."""
    _store, _transport, _service, rec = _submit_once_for_identity(tmp_path)

    assert isinstance(rec.authorization_id, str) and rec.authorization_id.strip()
    assert isinstance(rec.attempt_nonce, str) and rec.attempt_nonce.strip()
    assert isinstance(rec.attempt_ordinal, int) and rec.attempt_ordinal >= 1
    assert rec.submission_identity_errors() == ()
    rec.validate_submission_identity()  # must not raise


def test_record_owns_the_submission_identity_policy(tmp_path):
    """(2) Absent/blank identity values are violations in the record-owned policy."""
    _store, _transport, _service, rec = _submit_once_for_identity(tmp_path)

    assert rec.submission_identity_errors() == ()
    assert dataclasses.replace(rec, attempt_nonce=None).submission_identity_errors() == ("attempt_nonce",)
    assert dataclasses.replace(rec, attempt_nonce="   ").submission_identity_errors() == ("attempt_nonce",)

    with pytest.raises(AtlasRenderJobRecordError) as exc_info:
        dataclasses.replace(rec, attempt_nonce=None).validate_submission_identity()
    assert "attempt_nonce" in str(exc_info.value)


def test_identity_violation_fails_closed_before_capability_and_dispatch(tmp_path):
    """(3)(4) A durable intent lacking required identity is never transmitted: the
    submission transaction fails closed BEFORE the capability assertion and before
    any transport dispatch, and the job is marked FAILED."""
    def timeout_handler(request):
        if request.operation_name == "get_capabilities":
            return MockUnrealTransport().default_handler(request)
        if request.operation_name == "submit_render":
            raise NamedPipeTransportTimeoutError("Named pipe read timed out")
        raise RuntimeError("Unexpected operation")

    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport(handler=timeout_handler)
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)
    kwargs = _identity_submission_kwargs()

    # An authorized submission whose acceptance is unknown leaves a durable
    # PENDING_SUBMISSION intent carrying the full identity.
    first = service.submit_render(**kwargs)
    assert first.acceptance_unknown is True
    atlas_id = first.record.atlas_job_id
    record = store.load(atlas_id)
    assert record.submission_identity_errors() == ()

    # Model a legacy/repair-materialized intent: durable record without the M8 nonce.
    stripped = dataclasses.replace(record, attempt_nonce=None)
    store.update(stripped, expected_revision=record.last_observed_revision)

    sends_before = transport.send_call_count
    with pytest.raises(UnrealRenderSubmissionError) as exc_info:
        service.submit_render(**kwargs, existing_atlas_job_id=atlas_id)

    assert "identity gate" in str(exc_info.value)
    assert "attempt_nonce" in str(exc_info.value)

    # Ordering proof: neither the capability RPC nor the render dispatch occurred.
    assert transport.send_call_count == sends_before
    assert transport.sent_requests[sends_before:] == []
    submit_ops = [r for r in transport.sent_requests if r.operation_name == "submit_render"]
    assert len(submit_ops) == 1  # only the first, accepted-unknown attempt

    failed = store.load(atlas_id)
    assert failed.lifecycle_state == RenderJobLifecycleState.FAILED
    assert "identity invariant failed" in (failed.failure_reason or "")


def test_capability_assertion_remains_authoritative_with_valid_identity(tmp_path):
    """(5) The engine capability assertion is unchanged and still blocks dispatch."""
    def degraded_capability_handler(request):
        if request.operation_name == "get_capabilities":
            return UnrealTransportResponse(
                request_id=request.request_id,
                operation_name=request.operation_name,
                entity_ids=request.entity_ids,
                success=True,
                observed_state={"capabilities": ["render"]},
                error="",
                source="unreal-editor-5.6",
                schema_version=1,
                error_code="",
                session_identity={},
            )
        if request.operation_name == "submit_render":
            raise AssertionError("submit_render must not dispatch when the capability gate fails")
        raise RuntimeError("Unexpected operation")

    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    transport = MockUnrealTransport(handler=degraded_capability_handler)
    adapter = UnrealAdapterProduction(transport)
    service = UnrealRenderSubmissionService(store=store, adapter=adapter)

    with pytest.raises(UnrealRenderSubmissionError) as exc_info:
        service.submit_render(**_identity_submission_kwargs())
    assert "capability gate" in str(exc_info.value)
    assert not [r for r in transport.sent_requests if r.operation_name == "submit_render"]

    record = next(iter(store.list_job_ids()))
    assert store.load(record).lifecycle_state == RenderJobLifecycleState.FAILED


def test_submission_surface_stays_singular_with_record_owned_identity_policy():
    """(6) No duplicate submission API and no new authorization authority: the
    identity policy lives on the existing durable record."""
    public_methods = {name for name in dir(UnrealRenderSubmissionService) if not name.startswith("_")}
    assert public_methods == {"submit_render"}  # no separate intent-only API

    assert callable(getattr(AtlasRenderJobRecord, "submission_identity_errors", None))
    assert callable(getattr(AtlasRenderJobRecord, "validate_submission_identity", None))

    import planning.unreal_render_submission as submission_module
    src = Path(submission_module.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "unreal_production_controller_bridge",
        "unreal_autonomous_execution_loop",
        "unreal_authorized_execution_gate",
        "unreal_production_autonomous_loop",
        "unreal_plan_authorization",
        "unreal_recovery_authority",
        "unreal_plan_executor",
    ):
        assert forbidden not in src




