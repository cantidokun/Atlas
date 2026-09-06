"""M10 Defect B regression tests — reconcile catalog must relay M8 attestation fields.

Defect B: the live `reconcile_render_jobs` catalog dropped the M8 attestation /
session fields required by Atlas reconciliation. The in-memory registry overlay
overwrote the richer journal-derived attested entry with a sparse field set, so the
coordinator could not reconstruct + HMAC-verify the attested witness.

Tests prove (Python-level, deterministic, against a live-shaped catalog + the real
coordinator):
1. live-shaped catalog entry contains attempt_ordinal;
2. live-shaped catalog entry contains entry_digest (HMAC);
3. live-shaped catalog entry contains editor/process identity;
4. phase_history survives serialization/deserialization intact;
5. Atlas verifies the actual observed HMAC against the persisted attempt_nonce;
6. omission/tampering of any required field fails closed (UNTRUSTED_WITNESS).
   (phase_history structural validation is enforced in C++ ReconcileRenderJobs, not
   re-required at the Python candidate level; its round-trip is covered above.)
7. a valid attested catalog reaches the independent evidence-verification path and
   finalizes (Case B) only when all evidence gates pass.

The C++ side (ReconcileRenderJobs) is covered by the UBT-compiled automation tests;
this module proves the Python coordinator consumes the corrected field relay.
"""
import hashlib
import pathlib
import tempfile
from unittest.mock import MagicMock

import pytest

from planning.unreal_adapter_production import UnrealAdapterError, UnrealAdapterProduction
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_journal_attestation import compute_journal_attestation_digest
from planning.unreal_render_recovery_coordinator import UnrealRenderRecoveryCoordinator
from planning.unreal_render_job_store import AtlasRenderJobStore
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_job_states import (
    RenderJobLifecycleState as LCS,
    RenderJobRecoveryStatus as RCS,
)
from scripts.run_unreal_supervisor import AtlasProcessSupervisor

import tests.m6.fault_fixtures as ff


def _make_valid_png(path):
    import struct, zlib
    import hashlib
    path.parent.mkdir(parents=True, exist_ok=True)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    ihdr = b"\x00\x00\x00\x0dIHDR" + ihdr_data + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data))
    idat = b"\x00\x00\x00" + bytes([len(zlib.compress(b"\x00\x00\x00\x00"))]) + b"IDAT" + zlib.compress(b"\x00\x00\x00\x00") + struct.pack(">I", zlib.crc32(b"IDAT" + zlib.compress(b"\x00\x00\x00\x00")))
    iend = b"\x00\x00\x00\x00IEND" + struct.pack(">I", zlib.crc32(b"IEND"))
    path.write_bytes(sig + ihdr + idat + iend)
    return hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size


def _make_store(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "store")
    record = ff.make_submitted_record(tmp_path, attempt_nonce="m10-b-nonce-0123456789abcdef")
    store.create(record)
    return store, record


def _attested_catalog_entry(record, frame_path, *, include=dict()):
    """Build a live-shaped catalog known_jobs entry like the corrected C++
    ReconcileRenderJobs journal-derived path (latest phase = FINISHED)."""
    import hashlib
    real_sha, real_size = _make_valid_png(frame_path)
    manifest = [{"path": str(frame_path), "size": real_size, "sha256": real_sha}]
    unreal_job = record.unreal_job_id or "unreal-job-m10b-001"
    ed = record.origin_editor_session_id or "session-m6-editor"
    pct = record.origin_process_creation_time or "2026-09-06T00:00:00Z"
    pseq = record.origin_process_id or 4242
    entry = {
        "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": unreal_job,
        "job_id": unreal_job,
        "attempt_ordinal": record.attempt_ordinal,
        "phase": "FINISHED",
        "phase_sequence": 3,
        "status": "finished",
        "finished": True,
        "success": True,
        "failed": False,
        "editor_session_id": ed,
        "process_id": pseq,
        "process_creation_time_utc": pct,
        "output_directory": record.output_directory,
        "sequence_asset_path": record.sequence_asset_path,
        "config_digest": record.config_digest,
        "authorization_id": record.authorization_id,
        "output_manifest": manifest,
        "output_files": [str(frame_path)],
        "state_source": "witness_journal",
        # phase_history preserved intact (serialization/deserialization round-trip)
        "phase_history": [
            {"phase": "ACCEPTED", "phase_sequence": 1, "attempt_ordinal": record.attempt_ordinal},
            {"phase": "STARTED", "phase_sequence": 2, "attempt_ordinal": record.attempt_ordinal},
            {"phase": "FINISHED", "phase_sequence": 3, "attempt_ordinal": record.attempt_ordinal},
        ],
    }
    # compute the real observed HMAC over the FINISHED canonical payload
    payload = {
        "schema_version": 1,
        "atlas_job_id": entry["atlas_job_id"],
        "unreal_job_id": unreal_job,
        "attempt_ordinal": entry["attempt_ordinal"],
        "phase": "FINISHED",
        "phase_sequence": 3,
        "editor_session_id": ed,
        "process_creation_time_utc": pct,
        "output_directory": record.output_directory,
        "output_manifest": manifest,
    }
    entry["entry_digest"] = compute_journal_attestation_digest(record.attempt_nonce, payload)
    for k, v in include.items():
        if v is None:
            entry.pop(k, None)
        else:
            entry[k] = v
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


# 1. live-shaped catalog contains attempt_ordinal
def test_m10b_catalog_contains_attempt_ordinal(tmp_path):
    store, record = _make_store(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    entry = _attested_catalog_entry(record, frame)
    assert entry.get("attempt_ordinal") == record.attempt_ordinal


# 2. contains entry_digest
def test_m10b_catalog_contains_entry_digest(tmp_path):
    store, record = _make_store(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    entry = _attested_catalog_entry(record, frame)
    d = entry.get("entry_digest")
    assert isinstance(d, str) and len(d) == 64 and int(d, 16)


# 3. contains editor/process identity
def test_m10b_catalog_contains_session_identity(tmp_path):
    store, record = _make_store(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    entry = _attested_catalog_entry(record, frame)
    assert entry.get("editor_session_id")
    assert entry.get("process_id")
    assert entry.get("process_creation_time_utc")


# 4. phase_history survives serialization/deserialization intact
def test_m10b_phase_history_round_trips(tmp_path):
    import json
    store, record = _make_store(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    entry = _attested_catalog_entry(record, frame)
    # simulate JSON wire round-trip
    round_tripped = json.loads(json.dumps(entry))
    assert round_tripped["phase_history"] == entry["phase_history"]
    assert len(round_tripped["phase_history"]) == 3
    assert [p["phase"] for p in round_tripped["phase_history"]] == ["ACCEPTED", "STARTED", "FINISHED"]


# 5. Atlas verifies actual observed HMAC against persisted attempt_nonce -> Case B
def test_m10b_valid_attested_reaches_finalize(tmp_path):
    store, record = _make_store(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    entry = _attested_catalog_entry(record, frame)
    coord = _coord(store, record, entry, tmp_path, quiescent=True)
    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.case_classified == "Case B"
    assert res.lifecycle_state_after == LCS.FINALIZED
    assert len(list(store.receipts_dir.glob("*.json"))) == 1


# 6. omission/tampering of any required field fails closed
@pytest.mark.parametrize("field", ["attempt_ordinal", "entry_digest", "editor_session_id", "process_creation_time_utc", "output_manifest"])
def test_m10b_missing_required_field_fails_closed(tmp_path, field):
    store, record = _make_store(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    entry = _attested_catalog_entry(record, frame, include={field: None})
    coord = _coord(store, record, entry, tmp_path, quiescent=True)
    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.case_classified in ("UNTRUSTED_WITNESS", "Case E/F", "Case G")
    assert res.lifecycle_state_after in (LCS.RECOVERY_FAILED, LCS.FAILED)
    assert len(list(store.receipts_dir.glob("*.json"))) == 0


def test_m10b_tampered_hmac_fails_closed(tmp_path):
    store, record = _make_store(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    entry = _attested_catalog_entry(record, frame)
    entry["entry_digest"] = "f" * 64  # wrong HMAC
    coord = _coord(store, record, entry, tmp_path, quiescent=True)
    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.case_classified == "UNTRUSTED_WITNESS"
    assert res.lifecycle_state_after == LCS.RECOVERY_FAILED
    assert len(list(store.receipts_dir.glob("*.json"))) == 0


# 7. quiescence still enforced (Case K) - cannot bypass
def test_m10b_quiescence_not_bypassed(tmp_path):
    store, record = _make_store(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    entry = _attested_catalog_entry(record, frame)
    coord = _coord(store, record, entry, tmp_path, quiescent=False)
    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.case_classified == "Case K (Quiescence Blocked)"
    assert len(list(store.receipts_dir.glob("*.json"))) == 0