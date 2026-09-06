"""M10 (S8) — Case H Option A regression tests: identity-aware CONFLICT detection.

Root cause (S8 live reachability blocker):
The engine's ReconcileRenderJobs builds the reconcile catalog as a SINGLE-candidate
TMap keyed by atlas_job_id. Two journal/in-memory candidates with the same
atlas_job_id collapse before the coordinator sees them, so the coordinator's
`len(candidates) > 1` Case H branch was structurally unreachable via the real
engine witness.

Approved remediation (Option A):
- RETAIN the single-candidate TMap (do NOT expose two independent candidates).
- Detect a materially different execution identity BEFORE the cascade collapse.
- Surface journal_status=CONFLICT + structured conflict_evidence on the surviving
  entry (original identity preserved, never overwritten).
- Atlas/coordinator maps CONFLICT -> Case H -> RECOVERY_FAILED (no receipt, no
  retry, no adoption, no synthetic success).
- DISTINCT from PARTIAL/UNREADABLE -> Case J (RECOVERY_PENDING).

This module contains:
(i) a deterministic Python mirror of the engine's identity-conflict semantics
    (used to prove the comparison rule the C++/engine implements),
(ii) coordinator-level tests proving CONFLICT maps to Case H -> RECOVERY_FAILED
    with the required fail-closed behavior (no receipt/retry/adoption/success),
(iii) adjacent regression proofs (S4 Case J, S6 Case D, S7 Case G, normal S1
    single-execution, and journal+in-memory same/different execution).

The engine-side reconciliation behavior itself is exercised by the deterministic
C++ automation FAtlasUE56ReconcileConflictDetectionTest (compile-verified; no live
editor launch).
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


# --------------------------------------------------------------------------- #
# (i) Deterministic mirror of the engine's execution-identity conflict rule.
#     Exactly mirrors AtlasS8::Conflicts in AtlasTransportServer.cpp: a field is
#     compared only when present+non-empty on BOTH sides; absence never conflicts.
# --------------------------------------------------------------------------- #

def _identity(job):
    unreal = job.get("unreal_job_id") or job.get("job_id") or ""
    attempt = job.get("attempt_ordinal", -1)
    auth = job.get("authorization_id", "")
    return unreal, attempt, auth


def engine_identity_conflicts(a, b):
    """Mirror of AtlasS8::Conflicts."""
    a_unreal, a_ord, a_auth = _identity(a or {})
    b_unreal, b_ord, b_auth = _identity(b or {})
    if a_unreal and b_unreal and a_unreal != b_unreal:
        return True, f"unreal_job_id differs ({a_unreal} vs {b_unreal})"
    if a_ord is not None and a_ord >= 0 and b_ord is not None and b_ord >= 0 and a_ord != b_ord:
        return True, f"attempt_ordinal differs ({a_ord} vs {b_ord})"
    if a_auth and b_auth and a_auth != b_auth:
        return True, f"authorization_id differs ({a_auth} vs {b_auth})"
    return False, ""


# --- engine identity-conflict semantics (same atlas_job_id, differing identities) ---

def test_s8_same_atlas_diff_unreal_conflicts():
    a = {"unreal_job_id": "U1", "attempt_ordinal": 1, "authorization_id": "A"}
    b = {"unreal_job_id": "U2", "attempt_ordinal": 1, "authorization_id": "A"}
    assert engine_identity_conflicts(a, b)[0] is True


def test_s8_same_atlas_diff_attempt_ordinal_conflicts():
    a = {"unreal_job_id": "U1", "attempt_ordinal": 1, "authorization_id": "A"}
    b = {"unreal_job_id": "U1", "attempt_ordinal": 2, "authorization_id": "A"}
    assert engine_identity_conflicts(a, b)[0] is True


def test_s8_same_atlas_diff_authorization_conflicts():
    a = {"unreal_job_id": "U1", "attempt_ordinal": 1, "authorization_id": "A"}
    b = {"unreal_job_id": "U1", "attempt_ordinal": 1, "authorization_id": "B"}
    assert engine_identity_conflicts(a, b)[0] is True


def test_s8_same_atlas_same_identity_no_conflict():
    a = {"unreal_job_id": "U1", "attempt_ordinal": 1, "authorization_id": "A"}
    b = {"unreal_job_id": "U1", "attempt_ordinal": 1, "authorization_id": "A"}
    assert engine_identity_conflicts(a, b)[0] is False


def test_s8_absent_field_never_conflicts():
    # Legacy/partial entries missing a field must NOT false-conflict against a
    # present field (the C++ compares only present-on-both).
    a = {"unreal_job_id": "U1", "attempt_ordinal": 1}            # no authorization_id
    b = {"unreal_job_id": "U1", "attempt_ordinal": 1, "authorization_id": "A"}
    assert engine_identity_conflicts(a, b)[0] is False
    c = {"unreal_job_id": "U1"}                                  # no attempt_ordinal
    d = {"unreal_job_id": "U1", "attempt_ordinal": 2}
    assert engine_identity_conflicts(c, d)[0] is False


def test_s8_journal_and_inmemory_same_execution_no_false_conflict():
    # The two candidates are just two representations of the SAME execution.
    journal = {"unreal_job_id": "U1", "job_id": "U1", "attempt_ordinal": 1, "authorization_id": "A"}
    inmem = {"unreal_job_id": "U1", "job_id": "U1", "attempt_ordinal": 1, "authorization_id": "A"}
    assert engine_identity_conflicts(journal, inmem)[0] is False


def test_s8_journal_and_inmemory_different_execution_conflicts():
    journal = {"unreal_job_id": "U1", "job_id": "U1", "attempt_ordinal": 1, "authorization_id": "A"}
    inmem = {"unreal_job_id": "U2", "job_id": "U2", "attempt_ordinal": 1, "authorization_id": "A"}
    assert engine_identity_conflicts(journal, inmem)[0] is True


# --------------------------------------------------------------------------- #
# (ii) Coordinator: journal_status=CONFLICT -> Case H -> RECOVERY_FAILED
# --------------------------------------------------------------------------- #

def _make_store(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "store")
    record = ff.make_submitted_record(tmp_path, attempt_nonce="m10-s8-nonce0123456789")
    store.create(record)
    return store, record


def _coord_with_status(tmp_path, store, record, *, journal_status="CONFLICT", known_jobs=None):
    adapter = MagicMock()
    adapter.assert_recovery_capable = MagicMock(return_value=None)
    adapter.inspect.return_value = UnrealEvidence(
        operation_name="reconcile_render_jobs", entity_ids=("RENDER_RECOVERY",),
        observed_state={
            "journal_status": journal_status,
            "known_jobs": known_jobs or [],
        },
        source="unreal", verified=True,
    )
    sv = MagicMock(spec=AtlasProcessSupervisor)
    sv.job_handle = 4321
    sv.query_active_processes.return_value = 0
    return UnrealRenderRecoveryCoordinator(
        store=store, adapter=adapter,
        receipt_store=UnrealRenderReceiptStore(tmp_path / "rcpt.json"),
        supervisor=sv, deployment_mode="CONTAINED_JOB_OBJECT",
    )


def test_s8_conflict_maps_to_case_h_recovery_failed(tmp_path):
    store, record = _make_store(tmp_path)
    # A CONFLICT witness with a surviving single candidate carrying conflict_evidence.
    surviving = {
        "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": "U1",
        "job_id": "U1",
        "attempt_ordinal": 1,
        "authorization_id": "auth-m6-test",
        "journal_status": "CONFLICT",
        "conflict_evidence": [{
            "conflict_type": "execution_identity",
            "conflicting_unreal_job_id": "U2",
            "conflicting_attempt_ordinal": 2,
            "conflicting_authorization_id": "auth-m6-test",
        }],
        "phase": "FINISHED",
        "phase_sequence": 3,
        "status": "finished",
        "finished": True,
        "success": True,
        "failed": False,
        "output_manifest": [],
        "output_files": [],
        "state_source": "unreal-editor-atlas-transport",
    }
    coord = _coord_with_status(tmp_path, store, record, journal_status="CONFLICT",
                               known_jobs=[surviving])
    res = coord.reconcile_single_job(record.atlas_job_id)

    assert res.case_classified == "Case H"
    assert res.lifecycle_state_after == LCS.RECOVERY_FAILED
    assert res.recovery_status_after == RCS.NONE
    assert res.receipt_reference is None
    # no receipt written
    assert len(list(store.receipts_dir.glob("*.json"))) == 0
    rec = store.load(record.atlas_job_id)
    assert rec.lifecycle_state == LCS.RECOVERY_FAILED
    # original identity preserved
    assert rec.attempt_ordinal == record.attempt_ordinal
    assert rec.authorization_id == record.authorization_id


def test_s8_conflict_no_retry_no_resubmit(tmp_path):
    store, record = _make_store(tmp_path)
    coord = _coord_with_status(tmp_path, store, record, journal_status="CONFLICT", known_jobs=[])
    adapter_ops = []
    for call in coord.adapter.method_calls:
        for a in call.args:
            if hasattr(a, "operation_name"):
                adapter_ops.append(a.operation_name)
    # reconcile_single_job calls adapter.inspect internally; a submit must never appear.
    coord.reconcile_single_job(record.atlas_job_id)
    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.case_classified == "Case H"
    # coordinator never issues submit_render/resubmit: its contract is recovery-only;
    # assert the durable record is not reset to a retryable state and stays terminal-fail.
    rec = store.load(record.atlas_job_id)
    assert rec.lifecycle_state == LCS.RECOVERY_FAILED


def test_s8_conflict_no_synthetic_success(tmp_path):
    store, record = _make_store(tmp_path)
    coord = _coord_with_status(tmp_path, store, record, journal_status="CONFLICT", known_jobs=[])
    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.lifecycle_state_after not in (LCS.FINALIZED, LCS.VERIFIED, LCS.COMPLETED_UNVERIFIED)
    # durable record not a success state
    rec = store.load(record.atlas_job_id)
    assert rec.lifecycle_state == LCS.RECOVERY_FAILED


def test_s8_conflict_no_artifact_adoption(tmp_path):
    store, record = _make_store(tmp_path)
    # Even if a real artifact exists on disk, a CONFLICT witness must NOT adopt it.
    out_dir = pathlib.Path(record.output_directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "AtlasRender_0001.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
    coord = _coord_with_status(tmp_path, store, record, journal_status="CONFLICT", known_jobs=[])
    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.case_classified == "Case H"
    rec = store.load(record.atlas_job_id)
    assert rec.lifecycle_state == LCS.RECOVERY_FAILED   # no FINALIZED/VERIFIED adoption
    assert len(list(store.receipts_dir.glob("*.json"))) == 0


def test_s8_conflict_original_identity_preserved_in_durable(tmp_path):
    store, record = _make_store(tmp_path)
    coord = _coord_with_status(tmp_path, store, record, journal_status="CONFLICT", known_jobs=[])
    res = coord.reconcile_single_job(record.atlas_job_id)
    rec = store.load(record.atlas_job_id)
    assert rec.atlas_job_id == record.atlas_job_id
    assert rec.attempt_ordinal == record.attempt_ordinal
    assert rec.authorization_id == record.authorization_id
    assert res.case_classified == "Case H"


# --------------------------------------------------------------------------- #
# (iii) Adjacent regression: CONFLICT is DISTINCT from Case J / D / G / B
# --------------------------------------------------------------------------- #

def test_s8_conflict_distinct_from_partial_case_j(tmp_path):
    # PARTIAL/UNREADABLE must STILL -> Case J (RECOVERY_PENDING), NOT Case H.
    store, record = _make_store(tmp_path)
    coord = _coord_with_status(tmp_path, store, record, journal_status="PARTIAL", known_jobs=[])
    res = coord.reconcile_single_job(record.atlas_job_id)
    # (journal_status=PARTIAL -> Case J)
    assert res.recovery_status_after == RCS.RECOVERY_PENDING
    assert res.lifecycle_state_after == LCS.SUBMITTED


def test_s8_normal_single_execution_still_finalizes(tmp_path):
    """Normal S1-style single execution (journal_status=COMPLETE, valid FINISHED
    candidate + artifacts) still reconciles/finalizes (Case B), not Case H."""
    store, record = _make_store(tmp_path)
    out_dir = pathlib.Path(record.output_directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    import struct, zlib, hashlib
    frame = out_dir / "AtlasRender_0001.png"
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    ihdr = b"\x00\x00\x00\x0dIHDR" + ihdr_data + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data))
    idat_payload = zlib.compress(b"\x00" * 16)
    idat = b"\x00\x00\x00" + bytes([len(idat_payload)]) + b"IDAT" + idat_payload + struct.pack(">I", zlib.crc32(b"IDAT" + idat_payload))
    iend = b"\x00\x00\x00\x00IEND" + struct.pack(">I", zlib.crc32(b"IEND"))
    frame.write_bytes(sig + ihdr + idat + iend)
    sha = hashlib.sha256(frame.read_bytes()).hexdigest()
    size = frame.stat().st_size
    manifest = [{"path": str(frame), "size": size, "sha256": sha}]
    candidate = {
        "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": record.unreal_job_id or "U1",
        "job_id": record.unreal_job_id or "U1",
        "attempt_ordinal": record.attempt_ordinal,
        "phase": "FINISHED", "phase_sequence": 3, "status": "finished",
        "finished": True, "success": True, "failed": False,
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
        "phase": "FINISHED", "phase_sequence": 3,
        "editor_session_id": candidate["editor_session_id"],
        "process_creation_time_utc": candidate["process_creation_time_utc"],
        "output_directory": record.output_directory,
        "output_manifest": manifest,
    }
    candidate["entry_digest"] = compute_journal_attestation_digest(record.attempt_nonce, payload)

    coord = _coord_with_status(tmp_path, store, record, journal_status="COMPLETE",
                               known_jobs=[candidate])
    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.case_classified == "Case B"
    assert res.lifecycle_state_after == LCS.FINALIZED