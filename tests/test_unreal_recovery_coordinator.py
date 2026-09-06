"""Deterministic tests for UnrealRenderRecoveryCoordinator (Milestone 4).

Authoritative specification: docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md.
"""

import hashlib
import json
import os
import struct
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from planning.unreal_adapter_production import UnrealAdapterError, UnrealAdapterProduction
from planning.unreal_evidence_contract import (
    UnrealEvidence,
    verify_png_completeness,
)
from planning.unreal_operation_contract import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_render_job_record import (
    AtlasRenderJobRecord,
    compute_authoritative_digest,
)
from planning.unreal_render_job_states import (
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
from planning.unreal_render_job_store import (
    AtlasRenderJobStore,
    AtlasRenderJobStoreStaleWriterError,
)
from planning.unreal_render_receipt import UnrealRenderReceipt
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_recovery_coordinator import (
    UnrealRenderRecoveryCoordinator,
    compute_journal_hmac,
)
from scripts.run_unreal_supervisor import AtlasProcessSupervisor, ProcessQuiescenceResult


def _create_minimal_valid_png(path: Path) -> None:
    """Create a minimal valid 1x1 PNG file with valid signature, IHDR, IDAT, and IEND."""
    import zlib
    path.parent.mkdir(parents=True, exist_ok=True)
    # Minimal 1x1 8-bit RGB PNG
    sig = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
    # IHDR chunk
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", 0x907753DE)  # CRC32 of b'IHDR' + ihdr_data
    ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + ihdr_crc
    # IDAT chunk: filter byte (0) + 3 bytes RGB (0, 0, 0) compressed with zlib
    raw_scanlines = b"\x00\x00\x00\x00"
    compressed_idat = zlib.compress(raw_scanlines)
    idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + compressed_idat) & 0xFFFFFFFF)
    idat = struct.pack(">I", len(compressed_idat)) + b"IDAT" + compressed_idat + idat_crc
    # IEND chunk
    iend_crc = struct.pack(">I", 0xAE426082)
    iend = struct.pack(">I", 0) + b"IEND" + iend_crc
    with path.open("wb") as f:
        f.write(sig + ihdr + idat + iend)


def _sample_intent_record(
    tmp_path: Path,
    atlas_job_id: str = "atlas-render-job-44444444-5555-6666-7777-888888888888",
    attempt_nonce: str = "nonce-secret-1234567890abcdef12345678",
) -> AtlasRenderJobRecord:
    out_parent = str(tmp_path / "renders")
    out_dir = str(tmp_path / "renders" / atlas_job_id)
    return AtlasRenderJobRecord.create_intent(
        atlas_job_id=atlas_job_id,
        attempt_ordinal=1,
        authorization_id="auth-test-rec",
        canonical_digital_twin_id="twin-test",
        sequence_asset_path="/Game/TestSequence",
        request_digest="req-digest",
        config_digest="cfg-digest",
        output_parent_directory=out_parent,
        output_directory=out_dir,
        expected_output_spec={"format": "png", "width": 1, "height": 1, "start_frame": 1, "end_frame": 1},
        created_at="2026-09-06T00:00:00Z",
        attempt_nonce=attempt_nonce,
    )


def test_png_completeness_validator(tmp_path):
    png_path = tmp_path / "frame.png"
    _create_minimal_valid_png(png_path)
    assert verify_png_completeness(png_path)

    # Truncated file must fail
    trunc_path = tmp_path / "truncated.png"
    trunc_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert not verify_png_completeness(trunc_path)


def test_journal_hmac_computation():
    nonce = "secret-nonce-123"
    payload = {"atlas_job_id": "job-1", "phase": "FINISHED"}
    h1 = compute_journal_hmac(nonce, payload)
    h2 = compute_journal_hmac(nonce, payload)
    assert h1 == h2

    # Different nonce must diverge
    h3 = compute_journal_hmac("other-nonce", payload)
    assert h1 != h3


def test_case_c_no_engine_evidence_no_artifacts(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "store")
    record = _sample_intent_record(tmp_path)
    store.create(record)

    adapter = MagicMock()
    adapter.assert_recovery_capable = MagicMock(return_value=None)
    adapter.apply_authorized.return_value = UnrealEvidence(
        operation_name="reconcile_render_jobs",
        entity_ids=("RENDER_RECOVERY",),
        observed_state={"journal_status": "COMPLETE", "known_jobs": []},
        source="unreal",
        verified=True,
    )
    receipt_store = UnrealRenderReceiptStore(tmp_path / "receipts" / "rcpt.json")

    coord = UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
        deployment_mode="CONTAINED_JOB_OBJECT",
    )

    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.case_classified == "Case C"
    assert res.lifecycle_state_after == RenderJobLifecycleState.ORPHANED
    assert res.recovery_status_after == RenderJobRecoveryStatus.NONE


def test_case_d_artifacts_present_non_mutating(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "store")
    record = _sample_intent_record(tmp_path)
    store.create(record)

    # Create dummy artifact on disk in output directory
    art_path = Path(record.output_directory) / "AtlasRender_0001.png"
    art_path.parent.mkdir(parents=True, exist_ok=True)
    art_path.write_bytes(b"dummy bytes")

    adapter = MagicMock()
    adapter.assert_recovery_capable = MagicMock(return_value=None)
    adapter.apply_authorized.return_value = UnrealEvidence(
        operation_name="reconcile_render_jobs",
        entity_ids=("RENDER_RECOVERY",),
        observed_state={"journal_status": "COMPLETE", "known_jobs": []},
        source="unreal",
        verified=True,
    )
    receipt_store = UnrealRenderReceiptStore(tmp_path / "receipts" / "rcpt.json")

    coord = UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
        deployment_mode="CONTAINED_JOB_OBJECT",
    )

    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.case_classified == "Case D"
    assert res.lifecycle_state_after == RenderJobLifecycleState.ORPHANED_ARTIFACTS_PRESENT
    assert res.recovery_status_after == RenderJobRecoveryStatus.NONE

    # Non-mutation invariant: File MUST NOT be deleted or moved
    assert art_path.is_file()
    assert art_path.read_bytes() == b"dummy bytes"


def test_case_a_live_job_continues_tracking(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "store")
    record = _sample_intent_record(tmp_path)
    store.create(record)

    adapter = MagicMock()
    adapter.assert_recovery_capable = MagicMock(return_value=None)
    adapter.apply_authorized.return_value = UnrealEvidence(
        operation_name="reconcile_render_jobs",
        entity_ids=("RENDER_RECOVERY",),
        observed_state={
            "journal_status": "COMPLETE",
            "known_jobs": [
                {
                    "atlas_job_id": record.atlas_job_id,
                    "job_id": "unreal-live-job",
                    "sequence_asset_path": record.sequence_asset_path,
                    "config_digest": record.config_digest,
                    "output_directory": record.output_directory,
                    "state_source": "in_memory_registry",
                    "finished": False,
                }
            ],
        },
        source="unreal",
        verified=True,
    )
    receipt_store = UnrealRenderReceiptStore(tmp_path / "receipts" / "rcpt.json")

    coord = UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
        deployment_mode="CONTAINED_JOB_OBJECT",
    )

    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.case_classified == "Case A"
    assert res.lifecycle_state_after == RenderJobLifecycleState.RENDERING
    assert res.recovery_status_after == RenderJobRecoveryStatus.NONE


def test_case_b_finished_quiescent_hmac_verified(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "store")
    nonce = "secret-nonce-val-1234567890abcdef"
    record = _sample_intent_record(tmp_path, attempt_nonce=nonce)
    store.create(record)

    # Set origin fields on record to match
    record = record.transition(
        origin_editor_session_id="session-1",
        origin_process_id=12345,
        origin_process_creation_time="2026-09-06T00:00:00Z",
    )
    store.update(record, expected_revision=0)

    # Create real valid PNG on disk
    frame_path = Path(record.output_directory) / "AtlasRender_0001.png"
    _create_minimal_valid_png(frame_path)
    file_bytes = frame_path.read_bytes()
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()
    file_size = len(file_bytes)

    # Build matching manifest
    manifest = [{"path": str(frame_path), "size": file_size, "sha256": sha256_hash}]
    unreal_job_id = "unreal-job-finished-888"

    canonical_payload = {
        "schema_version": 1,
        "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": unreal_job_id,
        "attempt_ordinal": record.attempt_ordinal,
        "phase": "FINISHED",
        "phase_sequence": 3,
        "editor_session_id": "session-1",
        "process_creation_time_utc": "2026-09-06T00:00:00Z",
        "output_directory": record.output_directory,
        "output_manifest": manifest,
    }
    digest = compute_journal_hmac(nonce, canonical_payload)

    candidate = {
        "atlas_job_id": record.atlas_job_id,
        "job_id": unreal_job_id,
        "sequence_asset_path": record.sequence_asset_path,
        "authorization_id": record.authorization_id,
        "canonical_digital_twin_id": record.canonical_digital_twin_id,
        "config_digest": record.config_digest,
        "output_directory": record.output_directory,
        "phase": "FINISHED",
        "phase_sequence": 3,
        "editor_session_id": "session-1",
        "process_id": 12345,
        "process_creation_time_utc": "2026-09-06T00:00:00Z",
        "expected_output_spec": {"format": "png", "width": 1, "height": 1, "start_frame": 1, "end_frame": 1},
        "status": "completed",
        "finished": True,
        "success": True,
        "failed": False,
        "output_manifest": manifest,
        "output_files": [str(frame_path)],
        "entry_digest": digest,
        "state_source": "witness_journal",
    }

    adapter = MagicMock()
    adapter.assert_recovery_capable = MagicMock(return_value=None)
    adapter.apply_authorized.return_value = UnrealEvidence(
        operation_name="reconcile_render_jobs",
        entity_ids=("RENDER_RECOVERY",),
        observed_state={"journal_status": "COMPLETE", "known_jobs": [candidate]},
        source="unreal",
        verified=True,
    )
    receipt_store = UnrealRenderReceiptStore(tmp_path / "receipts" / "rcpt.json")

    # Mock supervisor: exactly 0 active processes in Job Object
    mock_supervisor = MagicMock(spec=AtlasProcessSupervisor)
    mock_supervisor.job_handle = 1234
    mock_supervisor.query_active_processes.return_value = 0

    coord = UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
        supervisor=mock_supervisor,
        deployment_mode="CONTAINED_JOB_OBJECT",
    )

    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.case_classified == "Case B"
    assert res.lifecycle_state_after == RenderJobLifecycleState.FINALIZED
    assert res.recovery_status_after == RenderJobRecoveryStatus.RESOLVED


def test_case_k_uncontained_attached_mode_fails_closed(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "store")
    record = _sample_intent_record(tmp_path)
    store.create(record)

    candidate = {
        "atlas_job_id": record.atlas_job_id,
        "job_id": "unreal-job-777",
        "sequence_asset_path": record.sequence_asset_path,
        "config_digest": record.config_digest,
        "output_directory": record.output_directory,
        "phase": "FINISHED",
        "finished": True,
    }

    adapter = MagicMock()
    adapter.assert_recovery_capable = MagicMock(return_value=None)
    adapter.apply_authorized.return_value = UnrealEvidence(
        operation_name="reconcile_render_jobs",
        entity_ids=("RENDER_RECOVERY",),
        observed_state={"journal_status": "COMPLETE", "known_jobs": [candidate]},
        source="unreal",
        verified=True,
    )
    receipt_store = UnrealRenderReceiptStore(tmp_path / "receipts" / "rcpt.json")

    # In UNCONTAINED_ATTACHED mode, quiescence cannot be proven -> fails closed
    coord = UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
        deployment_mode="UNCONTAINED_ATTACHED",
    )

    res = coord.reconcile_single_job(record.atlas_job_id)
    assert "Case K" in res.case_classified
    assert res.recovery_status_after == RenderJobRecoveryStatus.WAITING_FOR_ENGINE_QUIESCENCE
    assert res.lifecycle_state_after != RenderJobLifecycleState.FINALIZED


def test_reconcile_all_non_terminal_jobs(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "store")
    rec1 = _sample_intent_record(tmp_path, atlas_job_id="atlas-render-job-aaaaaaaa-bbbb-cccc-dddd-111111111111")
    rec2 = _sample_intent_record(tmp_path, atlas_job_id="atlas-render-job-aaaaaaaa-bbbb-cccc-dddd-222222222222")
    store.create(rec1)
    store.create(rec2)

    adapter = MagicMock()
    adapter.assert_recovery_capable = MagicMock(return_value=None)
    adapter.apply_authorized.return_value = UnrealEvidence(
        operation_name="reconcile_render_jobs",
        entity_ids=("RENDER_RECOVERY",),
        observed_state={"journal_status": "COMPLETE", "known_jobs": []},
        source="unreal",
        verified=True,
    )
    receipt_store = UnrealRenderReceiptStore(tmp_path / "receipts" / "rcpt.json")

    coord = UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
        deployment_mode="CONTAINED_JOB_OBJECT",
    )

    results = coord.reconcile_all_non_terminal_jobs(lease_token=5)
    assert len(results) == 2
    assert all(r.case_classified == "Case C" for r in results)


def test_case_e_f_binding_mismatch_fails_closed(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "store")
    record = _sample_intent_record(tmp_path)
    store.create(record)

    candidate = {
        "atlas_job_id": record.atlas_job_id,
        "job_id": "unreal-job-mismatch",
        "sequence_asset_path": "/Game/WrongSequencePath",
        "config_digest": record.config_digest,
        "output_directory": record.output_directory,
    }

    adapter = MagicMock()
    adapter.assert_recovery_capable = MagicMock(return_value=None)
    adapter.apply_authorized.return_value = UnrealEvidence(
        operation_name="reconcile_render_jobs",
        entity_ids=("RENDER_RECOVERY",),
        observed_state={"journal_status": "COMPLETE", "known_jobs": [candidate]},
        source="unreal",
        verified=True,
    )
    receipt_store = UnrealRenderReceiptStore(tmp_path / "receipts" / "rcpt.json")

    coord = UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
        deployment_mode="CONTAINED_JOB_OBJECT",
    )

    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.case_classified == "Case E/F"
    assert res.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED


def test_case_h_duplicate_engine_executions_fails_closed(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "store")
    record = _sample_intent_record(tmp_path)
    store.create(record)

    cand1 = {
        "atlas_job_id": record.atlas_job_id,
        "job_id": "unreal-job-1",
        "sequence_asset_path": record.sequence_asset_path,
        "config_digest": record.config_digest,
        "output_directory": record.output_directory,
    }
    cand2 = {
        "atlas_job_id": record.atlas_job_id,
        "job_id": "unreal-job-2",
        "sequence_asset_path": record.sequence_asset_path,
        "config_digest": record.config_digest,
        "output_directory": record.output_directory,
    }

    adapter = MagicMock()
    adapter.assert_recovery_capable = MagicMock(return_value=None)
    adapter.apply_authorized.return_value = UnrealEvidence(
        operation_name="reconcile_render_jobs",
        entity_ids=("RENDER_RECOVERY",),
        observed_state={"journal_status": "COMPLETE", "known_jobs": [cand1, cand2]},
        source="unreal",
        verified=True,
    )
    receipt_store = UnrealRenderReceiptStore(tmp_path / "receipts" / "rcpt.json")

    coord = UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
        deployment_mode="CONTAINED_JOB_OBJECT",
    )

    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.case_classified == "Case H"
    assert res.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED


def test_case_j_unreadable_journal_sets_recovery_pending(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "store")
    record = _sample_intent_record(tmp_path)
    store.create(record)

    adapter = MagicMock()
    adapter.assert_recovery_capable = MagicMock(return_value=None)
    adapter.apply_authorized.return_value = UnrealEvidence(
        operation_name="reconcile_render_jobs",
        entity_ids=("RENDER_RECOVERY",),
        observed_state={"journal_status": "UNREADABLE", "known_jobs": []},
        source="unreal",
        verified=True,
    )
    receipt_store = UnrealRenderReceiptStore(tmp_path / "receipts" / "rcpt.json")

    coord = UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
        deployment_mode="CONTAINED_JOB_OBJECT",
    )

    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.case_classified == "Case J"
    assert res.recovery_status_after == RenderJobRecoveryStatus.RECOVERY_PENDING
    assert res.lifecycle_state_after == record.lifecycle_state


def test_hmac_mismatch_classified_untrusted_witness(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "store")
    record = _sample_intent_record(tmp_path, attempt_nonce="correct-nonce")
    store.create(record)

    # Candidate has invalid entry_digest HMAC
    candidate = {
        "atlas_job_id": record.atlas_job_id,
        "job_id": "unreal-job-bad-hmac",
        "sequence_asset_path": record.sequence_asset_path,
        "config_digest": record.config_digest,
        "output_directory": record.output_directory,
        "phase": "FINISHED",
        "entry_digest": "bogus-forged-digest-hmac",
        "output_manifest": [],
        "output_files": [],
    }

    adapter = MagicMock()
    adapter.assert_recovery_capable = MagicMock(return_value=None)
    adapter.apply_authorized.return_value = UnrealEvidence(
        operation_name="reconcile_render_jobs",
        entity_ids=("RENDER_RECOVERY",),
        observed_state={"journal_status": "COMPLETE", "known_jobs": [candidate]},
        source="unreal",
        verified=True,
    )
    receipt_store = UnrealRenderReceiptStore(tmp_path / "receipts" / "rcpt.json")

    mock_supervisor = MagicMock()
    mock_supervisor.job_handle = 1234
    mock_supervisor.query_active_processes.return_value = 0

    coord = UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
        supervisor=mock_supervisor,
        deployment_mode="CONTAINED_JOB_OBJECT",
    )

    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.case_classified == "UNTRUSTED_WITNESS"
    assert res.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED


def test_receipt_first_10_field_identity_binding(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "store")
    record = _sample_intent_record(tmp_path)
    # Transition record with engine job and session identity
    rec_submitted = record.transition(
        lifecycle_state=RenderJobLifecycleState.SUBMITTED,
        unreal_job_id="unreal-job-bound-1",
        origin_editor_session_id="session-guid-1",
        origin_process_creation_time="2026-09-06T00:00:00Z",
    )
    store.create(rec_submitted)

    receipt_file = tmp_path / "receipts" / "rcpt.json"
    receipt_store = UnrealRenderReceiptStore(receipt_file)

    # Valid receipt with matching all 10 identity fields
    valid_receipt = UnrealRenderReceipt(
        job_id="unreal-job-bound-1",
        sequence_asset_path=record.sequence_asset_path,
        evidence_digest="evidence-digest-123",
        atlas_job_id=record.atlas_job_id,
        attempt_ordinal=record.attempt_ordinal,
        authorization_id=record.authorization_id,
        canonical_digital_twin_id=record.canonical_digital_twin_id,
        config_digest=record.config_digest,
        output_directory=record.output_directory,
        unreal_job_id="unreal-job-bound-1",
        editor_session_id="session-guid-1",
        process_creation_time="2026-09-06T00:00:00Z",
    )
    receipt_store.save(valid_receipt)

    adapter = MagicMock()
    coord = UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
        deployment_mode="CONTAINED_JOB_OBJECT",
    )

    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.repaired_from_receipt is True
    assert res.lifecycle_state_after == RenderJobLifecycleState.FINALIZED
    assert res.recovery_status_after == RenderJobRecoveryStatus.RESOLVED


def test_receipt_first_rejects_mismatched_unreal_job_id(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "store")
    record = _sample_intent_record(tmp_path)
    rec_submitted = record.transition(
        lifecycle_state=RenderJobLifecycleState.SUBMITTED,
        unreal_job_id="unreal-job-bound-1",
        origin_editor_session_id="session-guid-1",
        origin_process_creation_time="2026-09-06T00:00:00Z",
    )
    store.create(rec_submitted)

    receipt_file = tmp_path / "receipts" / "rcpt.json"
    receipt_store = UnrealRenderReceiptStore(receipt_file)
    mismatched_job_receipt = UnrealRenderReceipt(
        job_id="unreal-job-WRONG-999",
        sequence_asset_path=record.sequence_asset_path,
        evidence_digest="evidence-digest-123",
        atlas_job_id=record.atlas_job_id,
        attempt_ordinal=record.attempt_ordinal,
        authorization_id=record.authorization_id,
        canonical_digital_twin_id=record.canonical_digital_twin_id,
        config_digest=record.config_digest,
        output_directory=record.output_directory,
        unreal_job_id="unreal-job-WRONG-999",
        editor_session_id="session-guid-1",
        process_creation_time="2026-09-06T00:00:00Z",
    )
    receipt_store.save(mismatched_job_receipt)

    adapter = MagicMock()
    adapter.assert_recovery_capable = MagicMock(return_value=None)
    adapter.apply_authorized.return_value = UnrealEvidence(
        operation_name="reconcile_render_jobs",
        entity_ids=("RENDER_RECOVERY",),
        observed_state={"journal_status": "COMPLETE", "known_jobs": []},
        source="unreal",
        verified=True,
    )

    coord = UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
        deployment_mode="CONTAINED_JOB_OBJECT",
    )

    # Receipt is NOT adopted; falls through to Case C
    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.repaired_from_receipt is False
    assert res.case_classified == "Case C"


def test_receipt_first_rejects_mismatched_session_identity(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "store")
    record = _sample_intent_record(tmp_path)
    rec_submitted = record.transition(
        lifecycle_state=RenderJobLifecycleState.SUBMITTED,
        unreal_job_id="unreal-job-bound-1",
        origin_editor_session_id="session-guid-1",
        origin_process_creation_time="2026-09-06T00:00:00Z",
    )
    store.create(rec_submitted)

    receipt_file = tmp_path / "receipts" / "rcpt.json"
    receipt_store = UnrealRenderReceiptStore(receipt_file)

    # Receipt with mismatched editor_session_id
    mismatched_receipt = UnrealRenderReceipt(
        job_id="unreal-job-bound-1",
        sequence_asset_path=record.sequence_asset_path,
        evidence_digest="evidence-digest-123",
        atlas_job_id=record.atlas_job_id,
        attempt_ordinal=record.attempt_ordinal,
        authorization_id=record.authorization_id,
        canonical_digital_twin_id=record.canonical_digital_twin_id,
        config_digest=record.config_digest,
        output_directory=record.output_directory,
        unreal_job_id="unreal-job-bound-1",
        editor_session_id="session-WRONG-999",
        process_creation_time="2026-09-06T00:00:00Z",
    )
    receipt_store.save(mismatched_receipt)

    adapter = MagicMock()
    adapter.assert_recovery_capable = MagicMock(return_value=None)
    adapter.apply_authorized.return_value = UnrealEvidence(
        operation_name="reconcile_render_jobs",
        entity_ids=("RENDER_RECOVERY",),
        observed_state={"journal_status": "COMPLETE", "known_jobs": []},
        source="unreal",
        verified=True,
    )

    coord = UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
        deployment_mode="CONTAINED_JOB_OBJECT",
    )

    # Receipt is NOT adopted; falls through to Case C (no engine evidence, no disk artifacts)
    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.repaired_from_receipt is False
    assert res.case_classified == "Case C"
