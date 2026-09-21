"""M7 Case B — deterministic acceptance tests for DURABLE-WITNESS (prior-session) adoption.

Contract basis: `docs/design/M7_S1_ADOPTION_CASE_B_DESIGN.md` (Option B), Contract V1 §9
(quiescence), §10 (durable journal + nonce-keyed witness HMAC), §20 Steps 2-10,
§21 Case B/C/D/E-F/G/H/J/K.

The two DECISIVE tests are:
  * `test_case_b_positive_adoption_from_durable_witness` — quiescence established, durable
    witness present, transport attempts == 0, attestation valid, artifacts valid, adoption
    succeeds and the receipt is published EXACTLY once.
  * `test_case_k_negative_control_blocks_adoption_before_any_engine_call` — non-quiescent
    containment with terminal artifacts present: nothing is inspected or adopted, no
    receipt, and no engine RPC happens.

Everything here is deterministic: no engine, no live render, no submission, no network.
"""
import hashlib
import json
import pathlib
import struct
import zlib

import pytest

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_journal_attestation import compute_journal_attestation_digest
from planning.unreal_render_job_states import (
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
from planning.unreal_render_receipt import UnrealRenderReceipt
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_recovery_coordinator import UnrealRenderRecoveryCoordinator
from planning.unreal_render_job_store import AtlasRenderJobStore
from planning.unreal_witness_journal import (
    JOURNAL_DIRECTORY_NAME,
    JOURNAL_STATUS_ABSENT,
    JOURNAL_STATUS_COMPLETE,
    JOURNAL_STATUS_CONFLICT,
    JOURNAL_STATUS_PARTIAL,
    DurableWitnessJournalReader,
    canonical_engine_job_id,
)

import tests.m6.fault_fixtures as ff


# ── fixtures ──────────────────────────────────────────────────────────────
def _make_valid_png(path: pathlib.Path) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    ihdr = b"\x00\x00\x00\x0dIHDR" + ihdr_data + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data))
    idat_data = zlib.compress(b"\x00\x00\x00\x00")
    idat = b"\x00\x00\x00" + bytes([len(idat_data)]) + b"IDAT" + idat_data + struct.pack(">I", zlib.crc32(b"IDAT" + idat_data))
    iend = b"\x00\x00\x00\x00IEND" + struct.pack(">I", zlib.crc32(b"IEND"))
    path.write_bytes(sig + ihdr + idat + iend)
    return path.read_bytes()


def _store_and_record(tmp_path, **overrides):
    store = AtlasRenderJobStore(tmp_path / "store")
    record = ff.make_submitted_record(
        tmp_path, attempt_nonce="m7-caseb-nonce-0123456789abcdef", **overrides)
    store.create(record)
    return store, record


def _manifest_for(frame: pathlib.Path):
    data = frame.read_bytes()
    return [{"path": str(frame), "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}]


def _entry(
    record,
    manifest,
    *,
    phase="FINISHED",
    finished=True,
    success=None,
    failed=False,
    status=None,
    attempt_ordinal=None,
    unreal_job_id=None,
    authorization_id=None,
    digest_nonce=None,
    entry_digest=None,
):
    """Build a terminal witness entry exactly as the engine writes it (§10 schema 2).

    The entry deliberately carries ONLY `unreal_job_id` (never `job_id`), matching the
    real engine journal, so the coordinator's name normalization is exercised.
    """
    unreal_job = unreal_job_id or record.unreal_job_id or "unreal-job-m6-001"
    editor_session = record.origin_editor_session_id or "session-m6-editor"
    process_created = record.origin_process_creation_time or "2026-09-06T00:00:00Z"
    ordinal = record.attempt_ordinal if attempt_ordinal is None else attempt_ordinal
    payload = {
        "schema_version": 1,
        "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": unreal_job,
        "attempt_ordinal": ordinal,
        "phase": phase,
        "phase_sequence": 3,
        "editor_session_id": editor_session,
        "process_creation_time_utc": process_created,
        "output_directory": record.output_directory,
        "output_manifest": manifest,
    }
    computed = compute_journal_attestation_digest(
        digest_nonce if digest_nonce is not None else record.attempt_nonce, payload)
    return {
        "journal_schema_version": 2,
        "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": unreal_job,
        "phase": phase,
        "phase_sequence": 3,
        "attempt_ordinal": ordinal,
        "authorization_id": authorization_id if authorization_id is not None else record.authorization_id,
        "sequence_asset_path": record.sequence_asset_path,
        "config_digest": record.config_digest,
        "output_directory": record.output_directory,
        "editor_session_id": editor_session,
        "process_id": record.origin_process_id or 4242,
        "process_creation_time_utc": process_created,
        "expected_output_spec": {"format": "png", "width": 1, "height": 1,
                                 "start_frame": 1, "end_frame": 1},
        "status": status if status is not None else ("finished" if finished else "submitted"),
        "finished": finished,
        "success": finished if success is None else success,
        "failed": failed,
        "output_manifest": manifest,
        "output_files": [m["path"] for m in manifest],
        "entry_digest": entry_digest if entry_digest is not None else computed,
        "state_source": "unreal-editor-atlas-transport",
        "written_at": "2026-09-06T00:00:05Z",
    }


def _write_journal(root: pathlib.Path, record, entry, *, filename=None) -> pathlib.Path:
    root.mkdir(parents=True, exist_ok=True)
    # The top-level engine identity may legitimately be absent from the ENTRY (B3 tests
    # cover "no identity" and "job_id only" witnesses); the file still lives under the
    # record's §10 logical key.
    engine_id = entry.get("unreal_job_id") or entry.get("job_id") or record.unreal_job_id
    name = filename or f"{record.atlas_job_id}__{engine_id}.json"
    path = root / name
    journal = {
        "journal_schema_version": 2,
        "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": engine_id,
        "phase": entry["phase"],
        "phase_sequence": entry["phase_sequence"],
        "status": entry["status"],
        "progress": 1,
        "success": entry["success"],
        "finished": entry["finished"],
        "failed": False,
        "phase_history": [
            {"phase": "ACCEPTED", "phase_sequence": 1},
            {"phase": "STARTED", "phase_sequence": 2},
            entry,
        ],
    }
    path.write_text(json.dumps(journal), encoding="utf-8")
    return path


class _RecordingAdapter:
    """Transport double that records every call; never reachable on the durable path."""

    def __init__(self, journal_status="COMPLETE", known_jobs=None, capable=True):
        self.calls = []
        self._status = journal_status
        self._known_jobs = known_jobs or []
        self._capable = capable

    def assert_recovery_capable(self, authorization_id):
        self.calls.append(("assert_recovery_capable", authorization_id))
        if not self._capable:
            from planning.unreal_adapter_production import UnrealAdapterError
            raise UnrealAdapterError("engine down")

    def inspect(self, operation, authorization_id):
        self.calls.append(("inspect", operation.name))
        return UnrealEvidence(
            operation_name=operation.name,
            entity_ids=tuple(operation.entity_ids),
            observed_state={"journal_status": self._status, "known_jobs": self._known_jobs},
            source="unreal",
            verified=True,
        )


class _ExplodingAdapter:
    """Every attribute access raises: proves a path never touched the engine."""

    def __getattr__(self, item):  # pragma: no cover - only fires on a violation
        raise AssertionError(f"engine transport was touched (attribute {item!r})")


def _supervisor(quiescent: bool, active: int = 0, job_handle=4242):
    sv = ff.quiescent_supervisor() if quiescent else ff.non_quiescent_supervisor(active)
    sv.job_handle = job_handle
    return sv


def _coordinator(store, record, tmp_path, adapter=None, *, quiescent=True, mode="CONTAINED_JOB_OBJECT",
                 journal_root=None, receipt_store=None, job_handle=4242, active=0):
    root = journal_root if journal_root is not None else (tmp_path / JOURNAL_DIRECTORY_NAME)
    return UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter if adapter is not None else _RecordingAdapter(),
        receipt_store=receipt_store or UnrealRenderReceiptStore(tmp_path / "rcpt.json"),
        supervisor=_supervisor(quiescent, active=active, job_handle=job_handle),
        deployment_mode=mode,
        journal_root=str(root),
    )


def _receipts(store):
    return sorted(store.receipts_dir.glob("*.json"))


# ── DECISIVE TEST A: durable-witness Case B positive ──────────────────────
def test_case_b_positive_adoption_from_durable_witness(tmp_path):
    """Quiescence + durable terminal witness + valid artifacts -> Case B, ONE receipt,
    zero transport attempts."""
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    manifest = _manifest_for(frame)
    _write_journal(tmp_path / JOURNAL_DIRECTORY_NAME, record, _entry(record, manifest))
    adapter = _RecordingAdapter(capable=False)  # engine DOWN: must not matter

    coord = _coordinator(store, record, tmp_path, adapter=adapter)
    result = coord.reconcile_single_job(record.atlas_job_id)

    assert result.case_classified == "Case B"
    assert result.lifecycle_state_after == RenderJobLifecycleState.FINALIZED
    assert result.recovery_status_after == RenderJobRecoveryStatus.RESOLVED
    assert adapter.calls == []                      # transport attempts == 0
    receipts = _receipts(store)
    assert len(receipts) == 1                       # published EXACTLY once
    receipt = UnrealRenderReceiptStore(receipts[0]).load()
    assert receipt.atlas_job_id == record.atlas_job_id
    assert receipt.attempt_ordinal == record.attempt_ordinal
    assert receipt.authorization_id == record.authorization_id
    assert receipt.canonical_digital_twin_id == record.canonical_digital_twin_id
    assert receipt.config_digest == record.config_digest
    assert receipt.output_directory == record.output_directory
    assert receipt.sequence_asset_path == record.sequence_asset_path
    final = store.load(record.atlas_job_id)
    assert pathlib.Path(final.receipt_reference) == receipts[0]
    assert final.failure_reason is None


def test_case_b_adoption_succeeds_with_an_unreachable_transport(tmp_path):
    """Non-vacuity: the adoption path never touches the transport at all."""
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    _write_journal(tmp_path / JOURNAL_DIRECTORY_NAME, record, _entry(record, _manifest_for(frame)))

    coord = _coordinator(store, record, tmp_path, adapter=_ExplodingAdapter())
    result = coord.reconcile_single_job(record.atlas_job_id)

    assert result.case_classified == "Case B"
    assert len(_receipts(store)) == 1


# ── DECISIVE TEST B: Case-K negative control ──────────────────────────────
def test_case_k_negative_control_blocks_adoption_before_any_engine_call(tmp_path):
    """Non-quiescent containment with a terminal witness and artifacts on disk:
    nothing may be inspected or adopted, no receipt, no engine RPC."""
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    before = frame.read_bytes()
    _write_journal(tmp_path / JOURNAL_DIRECTORY_NAME, record, _entry(record, _manifest_for(frame)))

    coord = _coordinator(store, record, tmp_path, adapter=_ExplodingAdapter(),
                         quiescent=False, active=6)
    result = coord.reconcile_single_job(record.atlas_job_id)

    assert result.case_classified == "Case K (Quiescence Blocked)"
    assert result.recovery_status_after == RenderJobRecoveryStatus.WAITING_FOR_ENGINE_QUIESCENCE
    assert result.lifecycle_state_after == RenderJobLifecycleState.SUBMITTED
    assert _receipts(store) == []
    assert store.load(record.atlas_job_id).receipt_reference is None
    assert frame.read_bytes() == before            # artifacts untouched


# ── attestation / identity binding ────────────────────────────────────────
def test_ordinal_mismatch_fails_closed(tmp_path):
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    _write_journal(tmp_path / JOURNAL_DIRECTORY_NAME, record,
                   _entry(record, _manifest_for(frame), attempt_ordinal=record.attempt_ordinal + 1))
    result = _coordinator(store, record, tmp_path).reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "UNTRUSTED_WITNESS"
    assert result.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED
    assert _receipts(store) == []


def test_hmac_tamper_fails_closed(tmp_path):
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    _write_journal(tmp_path / JOURNAL_DIRECTORY_NAME, record,
                   _entry(record, _manifest_for(frame), entry_digest="ab" * 32))
    result = _coordinator(store, record, tmp_path).reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "UNTRUSTED_WITNESS"
    assert _receipts(store) == []


def test_hmac_wrong_nonce_fails_closed(tmp_path):
    """A witness HMAC computed with any other attempt nonce is rejected (anti-replay)."""
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    _write_journal(tmp_path / JOURNAL_DIRECTORY_NAME, record,
                   _entry(record, _manifest_for(frame), digest_nonce="some-other-attempt-nonce"))
    result = _coordinator(store, record, tmp_path).reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "UNTRUSTED_WITNESS"
    assert _receipts(store) == []


def test_missing_attestation_fails_closed(tmp_path):
    """A legacy/unattested witness (no entry_digest) must fail closed."""
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    entry = _entry(record, _manifest_for(frame))
    entry.pop("entry_digest")
    _write_journal(tmp_path / JOURNAL_DIRECTORY_NAME, record, entry)
    result = _coordinator(store, record, tmp_path).reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "UNTRUSTED_WITNESS"
    assert _receipts(store) == []


def test_identity_normalization_handles_unreal_job_id_only():
    """The journal names the engine job `unreal_job_id`; the live catalog names it
    `job_id`. Both normalize to one canonical identity."""
    assert canonical_engine_job_id({"unreal_job_id": "U-1"}) == "U-1"
    assert canonical_engine_job_id({"job_id": "U-1"}) == "U-1"
    assert canonical_engine_job_id({"job_id": "U-1", "unreal_job_id": "U-1"}) == "U-1"
    assert canonical_engine_job_id({}) is None


def test_engine_job_id_mismatch_is_case_e_f(tmp_path):
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    _write_journal(tmp_path / JOURNAL_DIRECTORY_NAME, record,
                   _entry(record, _manifest_for(frame), unreal_job_id="unreal-job-OTHER"))
    result = _coordinator(store, record, tmp_path).reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case E/F"
    assert result.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED
    assert _receipts(store) == []


def test_authorization_mismatch_is_case_e_f(tmp_path):
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    _write_journal(tmp_path / JOURNAL_DIRECTORY_NAME, record,
                   _entry(record, _manifest_for(frame), authorization_id="auth-someone-else"))
    result = _coordinator(store, record, tmp_path).reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case E/F"
    assert _receipts(store) == []


# ── artifact validation ───────────────────────────────────────────────────
def test_artifact_hash_mismatch_is_case_g(tmp_path):
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    manifest = _manifest_for(frame)
    manifest[0]["sha256"] = "cd" * 32
    _write_journal(tmp_path / JOURNAL_DIRECTORY_NAME, record, _entry(record, manifest))
    result = _coordinator(store, record, tmp_path).reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case G"
    assert result.lifecycle_state_after == RenderJobLifecycleState.FAILED
    assert _receipts(store) == []


def test_missing_artifact_is_case_g(tmp_path):
    store, record = _store_and_record(tmp_path)
    absent = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    blob = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    manifest = [{"path": str(absent), "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}]
    _write_journal(tmp_path / JOURNAL_DIRECTORY_NAME, record, _entry(record, manifest))
    result = _coordinator(store, record, tmp_path).reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case G"
    assert _receipts(store) == []


def test_terminal_witness_with_empty_manifest_is_case_g(tmp_path):
    store, record = _store_and_record(tmp_path)
    _write_journal(tmp_path / JOURNAL_DIRECTORY_NAME, record, _entry(record, []))
    result = _coordinator(store, record, tmp_path).reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case G"
    assert _receipts(store) == []


# ── ambiguity: conflict / partial / absent ────────────────────────────────
def test_conflicting_durable_journals_are_case_h(tmp_path):
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    _write_journal(root, record, _entry(record, _manifest_for(frame)))
    _write_journal(root, record, _entry(record, _manifest_for(frame), unreal_job_id="unreal-job-DUP"))
    adapter = _RecordingAdapter()
    result = _coordinator(store, record, tmp_path, adapter=adapter).reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case H"
    assert result.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED
    assert _receipts(store) == []
    assert adapter.calls == []                     # decided from the durable set alone


def test_partial_durable_journal_is_case_j(tmp_path):
    store, record = _store_and_record(tmp_path)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{record.atlas_job_id}__{record.unreal_job_id}.json").write_text(
        '{"journal_schema_version": 2, "atlas_job_id": "' + record.atlas_job_id + '"', encoding="utf-8")
    adapter = _RecordingAdapter()
    result = _coordinator(store, record, tmp_path, adapter=adapter).reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case J"
    assert result.recovery_status_after == RenderJobRecoveryStatus.RECOVERY_PENDING
    assert _receipts(store) == []
    assert adapter.calls == []


def test_absent_durable_journal_falls_through_to_the_live_path(tmp_path):
    """No durable witness: the LIVE path keeps its existing behaviour (Case C/D and the
    engine-unreachable hold), unchanged by this rung."""
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    reader = DurableWitnessJournalReader(tmp_path / JOURNAL_DIRECTORY_NAME)
    assert reader.read(record.atlas_job_id, record.unreal_job_id).status == JOURNAL_STATUS_ABSENT

    # engine reachable, catalog shows no candidate, artifacts present -> Case D (no adoption)
    up = _RecordingAdapter(journal_status="COMPLETE", known_jobs=[])
    result = _coordinator(store, record, tmp_path, adapter=up).reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case D"
    assert result.lifecycle_state_after == RenderJobLifecycleState.ORPHANED_ARTIFACTS_PRESENT
    assert _receipts(store) == []
    assert frame.exists()                          # non-mutating invariant


def test_absent_durable_journal_with_engine_down_holds(tmp_path):
    store, record = _store_and_record(tmp_path)
    down = _RecordingAdapter(capable=False)
    result = _coordinator(store, record, tmp_path, adapter=down).reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "WAITING_FOR_ENGINE"
    assert result.recovery_status_after == RenderJobRecoveryStatus.WAITING_FOR_ENGINE
    assert _receipts(store) == []


# ── ordering / mode table / stability / publication ───────────────────────
def test_uncontained_mode_never_adopts(tmp_path):
    """Contract V1 §9.281-284: UNCONTAINED_ATTACHED fails closed for adoption."""
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    _write_journal(tmp_path / JOURNAL_DIRECTORY_NAME, record, _entry(record, _manifest_for(frame)))
    coord = _coordinator(store, record, tmp_path, quiescent=True, mode="UNCONTAINED_ATTACHED",
                         job_handle=None)
    result = coord.reconcile_single_job(record.atlas_job_id)
    assert result.case_classified != "Case B"
    assert result.recovery_status_after == RenderJobRecoveryStatus.WAITING_FOR_ENGINE_QUIESCENCE
    assert _receipts(store) == []


def test_witness_snapshot_instability_invalidates_the_pass(tmp_path, monkeypatch):
    """Contract V1 §20 Step 7 without a live engine: a material change to the witness
    between acquisition and verification abandons the pass."""
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    journal_path = _write_journal(root, record, _entry(record, _manifest_for(frame)))

    real_snapshot = DurableWitnessJournalReader.snapshot
    calls = {"n": 0}

    def _flaky(self, path):
        calls["n"] += 1
        if calls["n"] == 2:
            # simulate a concurrent engine rewrite of the same journal
            entry = _entry(record, _manifest_for(frame))
            entry["written_at"] = "2026-09-06T00:00:09Z"
            _write_journal(root, record, entry)
        return real_snapshot(self, path)

    monkeypatch.setattr(DurableWitnessJournalReader, "snapshot", _flaky)
    result = _coordinator(store, record, tmp_path).reconcile_single_job(record.atlas_job_id)
    assert calls["n"] >= 2
    assert result.case_classified == "Case J"
    assert result.recovery_status_after == RenderJobRecoveryStatus.RECOVERY_PENDING
    assert _receipts(store) == []


def test_single_publication_and_receipt_first_repair(tmp_path):
    """Reconciling twice must produce exactly ONE receipt: the second pass repairs from
    the receipt instead of re-executing or re-publishing."""
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    _write_journal(tmp_path / JOURNAL_DIRECTORY_NAME, record, _entry(record, _manifest_for(frame)))
    coord = _coordinator(store, record, tmp_path)

    first = coord.reconcile_single_job(record.atlas_job_id)
    assert first.case_classified == "Case B"
    assert len(_receipts(store)) == 1

    second = coord.reconcile_single_job(record.atlas_job_id)
    assert second.case_classified == "RECEIPT_FIRST"
    assert second.repaired_from_receipt is True
    assert len(_receipts(store)) == 1                      # still exactly one
    final = store.load(record.atlas_job_id)
    assert final.lifecycle_state == RenderJobLifecycleState.FINALIZED
    assert final.recovery_status == RenderJobRecoveryStatus.RESOLVED


def test_deadline_exhaustion_precedes_durable_adoption(tmp_path):
    """An expired execution deadline is terminal: the durable path must not resurrect it."""
    store = AtlasRenderJobStore(tmp_path / "store")
    record = ff.make_submitted_record(
        tmp_path, attempt_nonce="m7-caseb-nonce-0123456789abcdef",
        execution_deadline="2020-01-01T00:00:00Z")
    store.create(record)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    _write_journal(tmp_path / JOURNAL_DIRECTORY_NAME, record, _entry(record, _manifest_for(frame)))

    result = _coordinator(store, record, tmp_path).reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "DEADLINE_EXHAUSTED"
    assert result.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED
    assert result.recovery_status_after == RenderJobRecoveryStatus.EXHAUSTED
    assert _receipts(store) == []


# ── reader contract: classification, canonical paths, read-only ───────────
def test_reader_classifies_the_durable_set(tmp_path):
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    reader = DurableWitnessJournalReader(root)

    assert reader.read(record.atlas_job_id, record.unreal_job_id).status == JOURNAL_STATUS_ABSENT

    _write_journal(root, record, _entry(record, _manifest_for(frame)))
    complete = reader.read(record.atlas_job_id, record.unreal_job_id)
    assert complete.status == JOURNAL_STATUS_COMPLETE
    assert complete.is_adoptable is True
    assert complete.candidate["job_id"] == complete.candidate["unreal_job_id"]  # normalized

    _write_journal(root, record, _entry(record, _manifest_for(frame), unreal_job_id="unreal-job-2"))
    assert reader.read(record.atlas_job_id, record.unreal_job_id).status == JOURNAL_STATUS_CONFLICT


def test_reader_rejects_journals_outside_the_designated_root(tmp_path):
    """Canonical-path validation: a hand-placed file outside the §10 root is not a
    witness, and a filename that ignores the §10 logical key is not trusted."""
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    other = tmp_path / "somewhere-else"
    other.mkdir(parents=True, exist_ok=True)
    entry = _entry(record, _manifest_for(frame))
    (other / f"{record.atlas_job_id}__{record.unreal_job_id}.json").write_text(
        json.dumps(entry), encoding="utf-8")

    reader = DurableWitnessJournalReader(other)
    # the file exists in ITS OWN root, so this is a valid read there (control) ...
    assert reader.read(record.atlas_job_id).status == JOURNAL_STATUS_COMPLETE
    # ... but a reader configured for the §10 root must not see it at all
    assert DurableWitnessJournalReader(tmp_path / JOURNAL_DIRECTORY_NAME).read(
        record.atlas_job_id).status == JOURNAL_STATUS_ABSENT

    # bad logical key (no `<atlas>__<unreal>.json`) is rejected as PARTIAL, not trusted
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    root.mkdir(parents=True, exist_ok=True)
    (root / "not-a-valid-journal-name.json").write_text(
        json.dumps({"journal_schema_version": 2, "atlas_job_id": record.atlas_job_id,
                    "phase": "FINISHED", "phase_sequence": 3}), encoding="utf-8")
    assert DurableWitnessJournalReader(root).read(record.atlas_job_id).status == JOURNAL_STATUS_PARTIAL


def test_reader_is_read_only(tmp_path):
    """The reader never mutates the journal set (no writes, no new files)."""
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    path = _write_journal(root, record, _entry(record, _manifest_for(frame)))
    before_bytes = path.read_bytes()
    before_stat = (path.stat().st_size, path.stat().st_mtime_ns)
    listing_before = sorted(p.name for p in root.iterdir())

    reader = DurableWitnessJournalReader(root)
    for _ in range(3):
        result = reader.read(record.atlas_job_id, record.unreal_job_id)
        assert result.status == JOURNAL_STATUS_COMPLETE
        reader.snapshot(path)

    assert path.read_bytes() == before_bytes
    assert (path.stat().st_size, path.stat().st_mtime_ns) == before_stat
    assert sorted(p.name for p in root.iterdir()) == listing_before


def test_reader_rejects_unsupported_schema(tmp_path):
    """The schema version is validated at the journal top level (as the engine's own
    directory scan does); an unsupported version is PARTIAL, never adopted."""
    store, record = _store_and_record(tmp_path)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    root.mkdir(parents=True, exist_ok=True)
    entry = _entry(record, [])
    entry.pop("journal_schema_version", None)
    (root / f"{record.atlas_job_id}__{record.unreal_job_id}.json").write_text(json.dumps({
        "journal_schema_version": 1,          # unsupported legacy schema
        "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": record.unreal_job_id,
        "phase": "FINISHED",
        "phase_sequence": 3,
        "phase_history": [entry],
    }), encoding="utf-8")
    witness = DurableWitnessJournalReader(root).read(record.atlas_job_id, record.unreal_job_id)
    assert witness.status == JOURNAL_STATUS_PARTIAL
    assert witness.is_adoptable is False


def test_reader_treats_non_terminal_journal_as_not_adoptable(tmp_path):
    """A bound journal with no terminal phase is in flight: never adoptable, and never a
    rejection either - an unfinished witness must not preempt a healthy live session."""
    store, record = _store_and_record(tmp_path)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{record.atlas_job_id}__{record.unreal_job_id}.json").write_text(json.dumps({
        "journal_schema_version": 2,
        "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": record.unreal_job_id,
        "phase": "STARTED",
        "phase_sequence": 2,
        "phase_history": [{"phase": "ACCEPTED", "phase_sequence": 1}],
    }), encoding="utf-8")
    witness = DurableWitnessJournalReader(root).read(record.atlas_job_id, record.unreal_job_id)
    assert witness.status == JOURNAL_STATUS_COMPLETE
    assert witness.is_terminal is False
    assert witness.is_adoptable is False
    assert witness.candidate is None
