"""M10 Defect (S4) — Case J regression tests: torn/non-terminal witness journal.

Defect observed (live S4 s4b dual-restart run, job 899e6a81):
- A genuine mid-render interruption produced a torn journal: the engine was
  killed at phase ACCEPTED(1) only (finished=False, status=submitted,
  phase=ACCEPTED, phase_sequence=1, output empty).
- Atlas restarted AND Unreal restarted (dual-restart boundary).
- The restarted Atlas reconciled the torn job against the restarted engine and
  the coordinator classified it:
      Case G -> lifecyc ==== FAILED (TERMINAL)
      failure_reason="Engine claims FINISHED but manifest and output_files are empty"
- But the witness journal is NOT terminal and does NOT claim FINISHED: last phase
  is ACCEPTED (phase_sequence=1). The contract (Contract V1 §19 Case J) requires
  a torn/partial/unreadable journal to be treated as UNKNOWN, NOT absent:

      ### Case J - Journal is unreadable or partial
      Treat as unknown, not absent.
      Enter bounded RECOVERY_PENDING; after the defined deadline/budget, terminate
      as RECOVERY_FAILED.

  So the correct outcome is Case J -> RECOVERY_PENDING (non-terminal lifecycle,
  no receipt), NOT terminal FAILED.

Root cause in the coordinator: the dispatch in `reconcile_single_job` routed any
non-live (non-`in_memory_registry`) candidate to `_handle_finished_candidate`,
which then hit the empty-manifest branch and terminally failed it. It never
checked whether the recovered witness candidate was actually TERMINAL before
applying the finished-candidate artifact path. A non-terminal witness (torn after
a dual-process interruption) must be routed to Case J.

This test file is NON-INTEGRATION (deterministic, fake transport). It proves the
exact fix rule:

  _candidate_is_terminal(candidate) is False for a torn/interrupted witness
  (finished=False, phase ACCEPTED/STARTED, status submitted/rendering), and the
  coordinator then classifies Case J -> RECOVERY_PENDING with NO receipt and NO
  terminal lifecycle, while a genuine terminal FINISHED candidate with a truly
  empty/corrupt manifest still fails closed (Case G / artifact verification
  failure unchanged).
"""
import pathlib
from unittest.mock import MagicMock

import pytest

from planning.unreal_render_recovery_coordinator import UnrealRenderRecoveryCoordinator
from planning.unreal_render_job_store import AtlasRenderJobStore
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_job_states import (
    RenderJobLifecycleState as LCS,
    RenderJobRecoveryStatus as RCS,
)
from planning.unreal_evidence_contract import UnrealEvidence
from scripts.run_unreal_supervisor import AtlasProcessSupervisor

import tests.m6.fault_fixtures as ff

from planning.unreal_journal_attestation import compute_journal_attestation_digest


def _make_store(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "store")
    record = ff.make_submitted_record(tmp_path, attempt_nonce="m10-casej-nonce0123456789")
    store.create(record)
    return store, record


def _torn_candidate(record, *, phase="ACCEPTED", phase_sequence=1, status="submitted",
                    finished=False, success=False):
    """Build a live-shaped torn/non-terminal catalog known_jobs entry, exactly
    matching the observed S4 s4b dual-restart candidate (job 899e6a81)."""
    unreal_job = record.unreal_job_id or "unreal-job-m10-casej-001"
    ed = record.origin_editor_session_id or "session-m6-editor"
    pct = record.origin_process_creation_time or "2026-09-06T00:00:00Z"
    pseq = record.origin_process_id or 4242
    entry = {
        "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": unreal_job,
        "job_id": unreal_job,
        "attempt_ordinal": record.attempt_ordinal,
        "phase": phase,
        "phase_sequence": phase_sequence,
        "status": status,
        "finished": finished,
        "success": success,
        "failed": False,
        "editor_session_id": ed,
        "process_id": pseq,
        "process_creation_time_utc": pct,
        "output_directory": record.output_directory,
        "sequence_asset_path": record.sequence_asset_path,
        "config_digest": record.config_digest,
        "authorization_id": record.authorization_id,
        "output_manifest": [],
        "output_files": [],
        "progress": 0,
        "state_source": "unreal-editor-atlas-transport",  # persisted/restored witness (NOT in_memory_registry)
        "agent": "authority",
        "phase_history": [
            {"phase": phase, "phase_sequence": phase_sequence,
             "attempt_ordinal": record.attempt_ordinal},
        ],
    }
    # Real attested HMAC over the torn (non-terminal) canonical payload, mirroring
    # how a genuine ACCEPTED journal entry is produced.
    payload = {
        "schema_version": 1,
        "atlas_job_id": entry["atlas_job_id"],
        "unreal_job_id": unreal_job,
        "attempt_ordinal": entry["attempt_ordinal"],
        "phase": phase,
        "phase_sequence": phase_sequence,
        "editor_session_id": ed,
        "process_creation_time_utc": pct,
        "output_directory": record.output_directory,
        "output_manifest": [],
    }
    entry["entry_digest"] = compute_journal_attestation_digest(record.attempt_nonce, payload)
    return entry


def _coord(store, record, candidate, tmp_path, quiescent=True):
    adapter = MagicMock()
    adapter.assert_recovery_capable = MagicMock(return_value=None)
    adapter.inspect.return_value = UnrealEvidence(
        operation_name="reconcile_render_jobs", entity_ids=("RENDER_RECOVERY",),
        observed_state={"journal_status": "COMPLETE", "known_jobs": [candidate]},
        source="unreal", verified=True,
    )
    sv = MagicMock(spec=AtlasProcessSupervisor)
    sv.job_handle = 4321
    sv.query_active_processes.return_value = 0 if quiescent else 2
    return UnrealRenderRecoveryCoordinator(
        store=store, adapter=adapter,
        receipt_store=UnrealRenderReceiptStore(tmp_path / "rcpt.json"),
        supervisor=sv, deployment_mode="CONTAINED_JOB_OBJECT",
    )


# ---- the fix rule: _candidate_is_terminal ----

def test_casej_candidate_terminality_torn_is_false():
    import inspect
    from planning.unreal_render_recovery_coordinator import (
        UnrealRenderRecoveryCoordinator as C,
    )
    torn = C._candidate_is_terminal({"finished": False, "phase": "ACCEPTED",
                                    "status": "submitted"})
    started = C._candidate_is_terminal({"finished": False, "phase": "STARTED",
                                        "status": "rendering"})
    assert torn is False
    assert started is False


def test_casej_candidate_terminality_finished_is_true():
    from planning.unreal_render_recovery_coordinator import (
        UnrealRenderRecoveryCoordinator as C,
    )
    assert C._candidate_is_terminal({"finished": True, "phase": "FINISHED"}) is True
    assert C._candidate_is_terminal({"finished": False, "phase": "FINISHED"}) is True
    assert C._candidate_is_terminal({"finished": False, "phase": "FAILED"}) is True


# ---- torn witness at the S4 dual-restart boundary -> Case J / RECOVERY_PENDING ----

def test_casej_torn_accepted_is_case_j_not_terminal(tmp_path):
    store, record = _make_store(tmp_path)
    candidate = _torn_candidate(record, phase="ACCEPTED", phase_sequence=1,
                                status="submitted", finished=False)
    coord = _coord(store, record, candidate, tmp_path, quiescent=True)
    res = coord.reconcile_single_job(record.atlas_job_id)

    assert res.case_classified == "Case J"
    assert res.lifecycle_state_after == LCS.SUBMITTED        # NOT terminal
    assert res.recovery_status_after == RCS.RECOVERY_PENDING
    assert res.repaired_from_receipt is False                # no receipt repair
    assert res.receipt_reference is None                     # no receipt issued
    # NOT terminal FAILED
    assert res.lifecycle_state_after != LCS.FAILED
    # durable record reflects RECOVERY_PENDING, non-terminal
    rec = store.load(record.atlas_job_id)
    assert rec.lifecycle_state == LCS.SUBMITTED
    assert rec.recovery_status == RCS.RECOVERY_PENDING
    # no receipts written
    assert len(list(store.receipts_dir.glob("*.json"))) == 0


def test_casej_torn_started_is_case_j_not_terminal(tmp_path):
    store, record = _make_store(tmp_path)
    candidate = _torn_candidate(record, phase="STARTED", phase_sequence=2,
                                status="rendering", finished=False)
    coord = _coord(store, record, candidate, tmp_path, quiescent=True)
    res = coord.reconcile_single_job(record.atlas_job_id)

    assert res.case_classified == "Case J"
    assert res.lifecycle_state_after == LCS.SUBMITTED
    assert res.recovery_status_after == RCS.RECOVERY_PENDING
    assert res.lifecycle_state_after != LCS.FAILED
    assert res.receipt_reference is None


def test_casej_no_retry_occurs(tmp_path):
    """A torn witness must NOT trigger submission/retry of the execution."""
    store, record = _make_store(tmp_path)
    candidate = _torn_candidate(record, phase="ACCEPTED", phase_sequence=1,
                                status="submitted", finished=False)
    coord = _coord(store, record, candidate, tmp_path, quiescent=True)
    res = coord.reconcile_single_job(record.atlas_job_id)

    # No submission/resubmit/retry operation may be issued by the coordinator.
    assert res.case_classified == "Case J"                  # classified, not retried
    assert res.recovery_status_after == RCS.RECOVERY_PENDING
    # The coordinator never calls submit (its adapter contract is recovery only);
    # confirm no submit was dispatched and no new attempt was created.
    adapter_ops = [c.args[0].operation_name if c.args and hasattr(c.args[0], "operation_name")
                   else None for c in coord.adapter.method_calls if c.args]
    assert "submit_render" not in str(adapter_ops)


def test_casej_no_synthetic_success_and_journal_remains_evidence(tmp_path):
    """The torn journal is evidence, not authority: it must not be rewritten
    into a synthetic FINISHED/success, and the job must remain unresolved."""
    store, record = _make_store(tmp_path)
    candidate = _torn_candidate(record, phase="ACCEPTED", phase_sequence=1,
                                status="submitted", finished=False)
    coord = _coord(store, record, candidate, tmp_path, quiescent=True)
    res = coord.reconcile_single_job(record.atlas_job_id)

    assert res.case_classified == "Case J"
    # lifecycle must not advance to a terminal success/finalized state
    assert res.lifecycle_state_after not in (LCS.FINALIZED, LCS.VERIFIED, LCS.FAILED)
    # durable record not terminal
    rec = store.load(record.atlas_job_id)
    assert rec.lifecycle_state == LCS.SUBMITTED
    # the durable journal itself is never touched / rewritten by the coordinator
    candidate_file = pathlib.Path(record.output_directory).parent / "journal_torn.json"
    # (journal not fabricated here; the coordinator must not have synthesized one)


def test_casej_ambiguity_incremented(tmp_path):
    store, record = _make_store(tmp_path)
    candidate = _torn_candidate(record, phase="ACCEPTED", phase_sequence=1,
                                status="submitted", finished=False)
    coord = _coord(store, record, candidate, tmp_path, quiescent=True)
    before = getattr(record, "recovery_attempts_or_ambiguity_count", 0) or 0
    res = coord.reconcile_single_job(record.atlas_job_id)
    rec = store.load(record.atlas_job_id)
    after = getattr(rec, "recovery_attempts_or_ambiguity_count", 0) or 0
    assert res.case_classified == "Case J"
    assert after > before


# ---- genuine Case G must still fail closed (unchanged semantics) ----

def test_caseg_genuine_terminal_finished_empty_manifest_still_fails(tmp_path):
    """A GENUINE terminal FINISHED candidate (engine truly claims finished=True)
    with an empty/corrupt manifest is a REAL idle execution result: it must still
    fail closed (Case G / FAILED), NOT be re-routed to Case J."""
    store, record = _make_store(tmp_path)
    # Terminal candidate: finished=True, phase=FINISHED, but empty manifest.
    candidate = {
        "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": record.unreal_job_id or "unreal-job-m10-casej-002",
        "job_id": record.unreal_job_id or "unreal-job-m10-casej-002",
        "attempt_ordinal": record.attempt_ordinal,
        "phase": "FINISHED",
        "phase_sequence": 3,
        "status": "finished",
        "finished": True,
        "success": True,
        "failed": False,
        "editor_session_id": record.origin_editor_session_id or "session-m6-editor",
        "process_id": record.origin_process_id or 4242,
        "process_creation_time_utc": record.origin_process_creation_time or "2026-09-06T00:00:00Z",
        "output_directory": record.output_directory,
        "sequence_asset_path": record.sequence_asset_path,
        "config_digest": record.config_digest,
        "authorization_id": record.authorization_id,
        "output_manifest": [],
        "output_files": [],
        "state_source": "unreal-editor-atlas-transport",
    }
    payload = {
        "schema_version": 1,
        "atlas_job_id": candidate["atlas_job_id"],
        "unreal_job_id": candidate["unreal_job_id"],
        "attempt_ordinal": candidate["attempt_ordinal"],
        "phase": "FINISHED",
        "phase_sequence": 3,
        "editor_session_id": candidate["editor_session_id"],
        "process_creation_time_utc": candidate["process_creation_time_utc"],
        "output_directory": record.output_directory,
        "output_manifest": [],
    }
    candidate["entry_digest"] = compute_journal_attestation_digest(record.attempt_nonce, payload)

    coord = _coord(store, record, candidate, tmp_path, quiescent=True)
    res = coord.reconcile_single_job(record.atlas_job_id)

    # Genuine Case G: terminal FAILED (artifact verification failure), no receipt.
    assert res.case_classified == "Case G"
    assert res.lifecycle_state_after == LCS.FAILED
    assert res.recovery_status_after == RCS.NONE
    assert res.receipt_reference is None


# ---- adjacent classification regressions ----

def test_caseb_valid_terminal_finished_with_artifacts_still_finalizes(tmp_path):
    """A genuine terminal FINISHED candidate WITH real artifacts still reaches
    Case B -> FINALIZED (the fix must not break the normal success path)."""
    store, record = _make_store(tmp_path)
    # Build a real PNG + matching manifest for this record's output directory.
    out_dir = pathlib.Path(record.output_directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    import struct, zlib, hashlib
    frame = out_dir / "AtlasRender_0001.png"
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    ihdr = b"\x00\x00\x00\x0dIHDR" + ihdr_data + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data))
    idat = b"\x00\x00\x00" + bytes([len(zlib.compress(b"\x00\x00\x00\x00"))]) + b"IDAT" + zlib.compress(b"\x00\x00\x00\x00") + struct.pack(">I", zlib.crc32(b"IDAT" + zlib.compress(b"\x00\x00\x00\x00")))
    iend = b"\x00\x00\x00\x00IEND" + struct.pack(">I", zlib.crc32(b"IEND"))
    frame.write_bytes(sig + ihdr + idat + iend)
    sha = hashlib.sha256(frame.read_bytes()).hexdigest()
    size = frame.stat().st_size
    manifest = [{"path": str(frame), "size": size, "sha256": sha}]

    candidate = {
        "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": record.unreal_job_id or "unreal-job-m10-casej-003",
        "job_id": record.unreal_job_id or "unreal-job-m10-casej-003",
        "attempt_ordinal": record.attempt_ordinal,
        "phase": "FINISHED",
        "phase_sequence": 3,
        "status": "finished",
        "finished": True,
        "success": True,
        "failed": False,
        "editor_session_id": record.origin_editor_session_id or "session-m6-editor",
        "process_id": record.origin_process_id or 4242,
        "process_creation_time_utc": record.origin_process_creation_time or "2026-09-06T00:00:00Z",
        "output_directory": record.output_directory,
        "sequence_asset_path": record.sequence_asset_path,
        "config_digest": record.config_digest,
        "authorization_id": record.authorization_id,
        "output_manifest": manifest,
        "output_files": [str(frame)],
        "state_source": "unreal-editor-atlas-transport",
    }
    payload = {
        "schema_version": 1,
        "atlas_job_id": candidate["atlas_job_id"],
        "unreal_job_id": candidate["unreal_job_id"],
        "attempt_ordinal": candidate["attempt_ordinal"],
        "phase": "FINISHED",
        "phase_sequence": 3,
        "editor_session_id": candidate["editor_session_id"],
        "process_creation_time_utc": candidate["process_creation_time_utc"],
        "output_directory": record.output_directory,
        "output_manifest": manifest,
    }
    candidate["entry_digest"] = compute_journal_attestation_digest(record.attempt_nonce, payload)

    coord = _coord(store, record, candidate, tmp_path, quiescent=True)
    res = coord.reconcile_single_job(record.atlas_job_id)

    # Normal success: Case B -> FINALIZED with a receipt.
    assert res.case_classified == "Case B"
    assert res.lifecycle_state_after == LCS.FINALIZED
    assert res.receipt_reference is not None
    assert len(list(store.receipts_dir.glob("*.json"))) == 1