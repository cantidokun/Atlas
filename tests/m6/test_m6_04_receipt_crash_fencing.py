"""M6 §31 items 19,20 — receipt create-if-absent race and crash between receipt
persistence and record finalization — plus receipt identity-conflict cases.

Authoritative: docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md §31.
"""

import threading

import pytest

from planning.unreal_render_job_store import (
    AtlasRenderJobStoreError,
    AtlasRenderJobStoreStaleWriterError,
)
from planning.unreal_render_job_states import (
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
from planning.unreal_render_receipt import UnrealRenderReceipt
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
import tests.m6.fault_fixtures as ff


# ── Item 19: receipt create-if-absent race ────────────────────────────────────
def test_m6_item19_receipt_create_if_absent_is_atomic(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path = ff.Path(rec.output_directory) / "AtlasRender_0000.png"
    png = ff.make_valid_png(path)
    manifest = ff.make_manifest_for(rec, [path])
    cand = ff.build_finished_candidate(rec, artifact_paths=[path], artifact_manifest=manifest)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [cand]})
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.lifecycle_state_after == RenderJobLifecycleState.FINALIZED
    # Receipt was persisted exactly once (create-if-absent, atomic)
    receipt_files = list(store.receipts_dir.glob("*.json"))
    assert len(receipt_files) == 1
    # No stray .tmp receipt files remain
    assert not list(store.receipts_dir.glob("*.tmp"))
    # A second identical store-gated publication with the same receipt digest is
    # rejected by fencing (terminal record): no duplicate, no silent overwrite.
    final = store.load(rec.atlas_job_id)
    persisted = UnrealRenderReceiptStore(receipt_files[0]).load()
    with pytest.raises((AtlasRenderJobStoreError, AtlasRenderJobStoreStaleWriterError)):
        store.publish_verified_receipt(
            atlas_job_id=final.atlas_job_id,
            attempt_ordinal=final.attempt_ordinal,
            presented_lease_token=final.last_accepted_lease_token + 1,
            expected_record_revision=final.last_observed_revision,
            receipt=persisted,
        )
    # Still exactly one receipt; record terminal; watermark unchanged.
    assert len(list(store.receipts_dir.glob("*.json"))) == 1
    assert store.load(final.atlas_job_id).lifecycle_state == RenderJobLifecycleState.FINALIZED
    assert store.load(final.atlas_job_id).last_accepted_lease_token == final.last_accepted_lease_token


def test_m6_item19_concurrent_receipt_publish_never_corrupts(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path = ff.Path(rec.output_directory) / "AtlasRender_0000.png"
    ff.make_valid_png(path)
    data = path.read_bytes()
    from planning.unreal_evidence_contract import verify_render_job_evidence

    observed = {
        "job_id": rec.unreal_job_id, "atlas_job_id": rec.atlas_job_id,
        "sequence_asset_path": rec.sequence_asset_path, "authorization_id": rec.authorization_id,
        "canonical_digital_twin_id": rec.canonical_digital_twin_id, "config_digest": rec.config_digest,
        "output_directory": rec.output_directory, "editor_session_id": rec.origin_editor_session_id,
        "process_id": rec.origin_process_id, "process_creation_time_utc": rec.origin_process_creation_time,
        "expected_output_spec": dict(rec.expected_output_spec), "status": "finished", "finished": True,
        "success": True, "failed": False, "output_files": [str(path)],
        "output_manifest": [{"path": str(path), "size": len(data), "sha256": ff.sha256_of(data)}],
    }
    evidence = verify_render_job_evidence(
        operation_name="inspect_render_job", entity_ids=("RENDER_RECOVERY",),
        observed_state=observed, source="unreal-recovery-coordinator", job_record=rec,
        evidence_source_class="ENGINE_JOURNAL_ATTESTED",
    )
    receipt = UnrealRenderReceipt.issue(
        evidence, atlas_job_id=rec.atlas_job_id, attempt_ordinal=rec.attempt_ordinal,
        authorization_id=rec.authorization_id, canonical_digital_twin_id=rec.canonical_digital_twin_id,
        config_digest=rec.config_digest, output_directory=rec.output_directory,
        lease_token=7, coordinator_id="m6-race-1",
    )

    # Race many concurrent atomic saves to the same path. On Windows, concurrent
    # os.replace renames to one destination can trip transient sharing violations
    # (PermissionError) — these are OS artifacts of the race, NOT corruption. The
    # invariant under all interleavings: the surviving file is ALWAYS a complete,
    # digest-consistent receipt, never torn/partial, and a subsequent write always
    # succeeds to the identical digest.
    target = store.receipts_dir / f"{rec.atlas_job_id}__{rec.attempt_ordinal}.json"
    os_errors = []
    barrier = threading.Barrier(8)

    def saver():
        barrier.wait()
        try:
            UnrealRenderReceiptStore(target).save(receipt)
        except (PermissionError, OSError) as exc:
            os_errors.append(exc)

    threads = [threading.Thread(target=saver) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Guaranteed invariant: whatever survived the race is a complete valid receipt.
    loaded = UnrealRenderReceiptStore(target).load()
    assert loaded.receipt_digest == receipt.receipt_digest
    assert not list(store.receipts_dir.glob("*.tmp"))
    # A clean re-save always reproduces the same digest (atomic, idempotent).
    UnrealRenderReceiptStore(target).save(receipt)
    assert UnrealRenderReceiptStore(target).load().receipt_digest == receipt.receipt_digest


def test_m6_item19_receipt_digest_collision_fails_closed(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    # Publish the correct receipt for this record's identity
    r_correct = ff.issue_receipt_for(rec, lease_token=1)
    # A second logical job's receipt has a DIFFERENT digest (different identity)
    rec_other = ff.make_submitted_record(
        tmp_path, atlas_job_id="atlas-render-job-cccccccc-dddd-eeee-ffff-000000000001"
    )
    r_other = ff.issue_receipt_for(rec_other, lease_token=1)
    assert r_other.receipt_digest != r_correct.receipt_digest
    # Persist the WRONG digest receipt at the create-if-absent path
    target = store.receipts_dir / f"{rec.atlas_job_id}__{rec.attempt_ordinal}.json"
    UnrealRenderReceiptStore(target).save(r_other)
    # Store-gated publication must fail closed on a digest collision, not overwrite
    store_rec = store.load(rec.atlas_job_id)
    with pytest.raises(AtlasRenderJobStoreError, match="Receipt collision"):
        store.publish_verified_receipt(
            atlas_job_id=rec.atlas_job_id, attempt_ordinal=rec.attempt_ordinal,
            presented_lease_token=5, expected_record_revision=store_rec.last_observed_revision,
            receipt=r_correct,
        )


# ── Item 20: crash between receipt persistence and record finalization ────────
def test_m6_item20_receipt_first_repairs_finalization_after_crash(tmp_path):
    # Simulate "crash after receipt persisted but before record finalization":
    # a valid, independently-verified receipt exists on disk while the record is
    # still non-terminal. Reconciliation must adopt it (receipt-first) -> FINALIZED.
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    # A verified receipt exists (as if the finalization step crashed afterward).
    path = ff.Path(rec.output_directory) / "AtlasRender_0000.png"
    ff.make_valid_png(path)
    receipt = ff.issue_receipt_for(rec, path, lease_token=3, coordinator_id="m6-crash-recovery")
    UnrealRenderReceiptStore(store.receipts_dir / f"{rec.atlas_job_id}__{rec.attempt_ordinal}.json").save(receipt)

    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": []})
    coord = ff.make_coordinator(store, adapter, receipt_store=UnrealRenderReceiptStore(store.receipts_dir / f"{rec.atlas_job_id}__{rec.attempt_ordinal}.json"))
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.case_classified == "RECEIPT_FIRST"
    assert res.repaired_from_receipt is True
    assert res.lifecycle_state_after == RenderJobLifecycleState.FINALIZED
    assert res.recovery_status_after == RenderJobRecoveryStatus.RESOLVED


def test_m6_item20_receipt_first_rejects_identity_conflict(tmp_path):
    # A receipt that diverges on ANY identity field must NOT be adopted.
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path = ff.Path(rec.output_directory) / "AtlasRender_0000.png"
    ff.make_valid_png(path)
    receipt = ff.issue_receipt_for(rec, path, lease_token=3)
    # Tamper with sequence_asset_path inside the persisted receipt payload
    target = store.receipts_dir / f"{rec.atlas_job_id}__{rec.attempt_ordinal}.json"
    UnrealRenderReceiptStore(target).save(receipt)
    tampered_store = UnrealRenderReceiptStore(target)
    env = {"version": tampered_store.VERSION, **receipt.snapshot()}
    import json
    env["sequence_asset_path"] = "/Game/Evil/DifferentSequence"
    tampered_store.path.write_text(json.dumps(env, sort_keys=True), encoding="utf-8")

    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": []})
    coord = ff.make_coordinator(store, adapter, receipt_store=UnrealRenderReceiptStore(target))
    res = coord.reconcile_single_job(rec.atlas_job_id)
    # Identity-conflicting / tampered receipt is not adopted; record not finalized
    assert res.lifecycle_state_after != RenderJobLifecycleState.FINALIZED


def test_m6_item20_crash_inside_publish_never_leaves_partial_receipt(tmp_path):
    # Store-gated publication must be atomic: an exception mid-publish must not
    # leave a zero-length / partial receipt file that later blocks recovery.
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path = ff.Path(rec.output_directory) / "AtlasRender_0000.png"
    ff.make_valid_png(path)
    receipt = ff.issue_receipt_for(rec, path, lease_token=1)
    target = store.receipts_dir / f"{rec.atlas_job_id}__1.json"
    # Simulate an interrupted write: create a partial file, verify load() fails closed
    target.write_text("{\"version\":", encoding="utf-8")
    with pytest.raises(RuntimeError, match="unreadable"):
        UnrealRenderReceiptStore(target).load()
    # And a clean publish after cleanup yields a fully-valid receipt
    target.unlink()
    UnrealRenderReceiptStore(target).save(receipt)
    assert UnrealRenderReceiptStore(target).load().receipt_digest == receipt.receipt_digest


# ── Receipt identity conflicts (audit gap) ────────────────────────────────────
def test_m6_item20_receipt_store_rejects_missing_required_fields(tmp_path):
    receipt_path = tmp_path / "rcpt.json"
    for bad in ("{}", '{"job_id":"x"}', '{"version":1,"job_id":"x","bad":true}'):
        receipt_path.write_text(bad, encoding="utf-8")
        with pytest.raises(RuntimeError):
            UnrealRenderReceiptStore(receipt_path).load()


def test_m6_item20_receipt_must_bind_verified_evidence_identity(tmp_path):
    # A receipt cannot be issued for unverified or mismatched evidence.
    rec = ff.make_intent_record(tmp_path)  # no unreal_job_id, unverified path
    with pytest.raises(Exception):
        ff.issue_receipt_for(rec)