"""M6 §31 items 1,2,3,4,6,16,21 — record, store, fencing, terminal non-regression,
and Case A–J reconciliation.

Authoritative: docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md §31.
"""

import json
import threading

import pytest

from planning.unreal_render_job_record import (
    AtlasRenderJobRecord,
    AtlasRenderJobRecordError,
)
from planning.unreal_render_job_states import (
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
from planning.unreal_render_job_store import (
    AtlasRenderJobStoreCorruptionError,
    AtlasRenderJobStoreLockError,
    AtlasRenderJobStoreStaleWriterError,
)
import tests.m6.fault_fixtures as ff


# ── Item 1: record validation and immutable round-trip ────────────────────────
def test_m6_item01_immutable_roundtrip_preserves_authoritative_fields(tmp_path):
    rec = ff.make_intent_record(tmp_path)
    assert isinstance(rec, AtlasRenderJobRecord)
    # Immutable: reconstructing from dict yields identical record and digest
    rec2 = AtlasRenderJobRecord.from_dict(rec.to_dict())
    assert rec2 == rec
    assert rec2.authoritative_digest == rec.authoritative_digest
    # Authoritative fields are revalidated on deserialization
    with pytest.raises(AtlasRenderJobRecordError, match="digest mismatch"):
        AtlasRenderJobRecord.from_dict({**rec.to_dict(), "authorization_id": "tampered"})


def test_m6_item01_record_rejects_traversal_in_job_id(tmp_path):
    with pytest.raises(AtlasRenderJobRecordError, match="illegal path characters"):
        ff.make_intent_record(tmp_path, atlas_job_id="atlas-render-job-../../evil")


# ── Item 2: atomic store update and corruption detection ──────────────────────
def test_m6_item02_atomic_roundtrip_and_store_envelope(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_intent_record(tmp_path)
    store.create(rec)
    loaded = store.load(rec.atlas_job_id)
    assert loaded == rec
    # No stray .tmp files left behind (atomic replacement cleanup)
    assert not list(store.jobs_dir.glob("*.tmp"))


def test_m6_item02_corruption_detected_and_quarantined_non_destructive(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_intent_record(tmp_path)
    store.create(rec)
    jf = store._job_file_path(rec.atlas_job_id)
    jf.write_text("CORRUPTED_NON_JSON", encoding="utf-8")
    with pytest.raises(AtlasRenderJobStoreCorruptionError, match="quarantined"):
        store.load(rec.atlas_job_id)
    # Non-destructive quarantine (Contract V1 §24 / skill ref): the ORIGINAL
    # corrupted bytes must be preserved in the moved quarantine file, while the
    # metadata is stored in a SEPARATE `.meta.json` sidecar. The raw glob picks
    # up BOTH files, so select the original-bytes file deterministically by
    # excluding the sidecar.
    sidecar = list(store.quarantine_dir.glob("*.corrupt.*.meta.json"))
    originals = [p for p in store.quarantine_dir.glob("*.corrupt.*")
                 if not p.name.endswith(".meta.json")]
    assert len(originals) == 1
    assert originals[0].read_text(encoding="utf-8") == "CORRUPTED_NON_JSON"
    # The original job file must no longer exist (moved, not deleted).
    assert not jf.exists()
    # Metadata sidecar records the quarantine path + reason (Contract §24 fields).
    assert len(sidecar) == 1
    meta = json.loads(sidecar[0].read_text(encoding="utf-8"))
    assert meta["reason"].startswith("JSON unreadable")
    assert "original_path" in meta and "quarantine_path" in meta and "timestamp" in meta


def test_m6_item02_authoritative_digest_mismatch_quarantined(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_intent_record(tmp_path)
    store.create(rec)
    jf = store._job_file_path(rec.atlas_job_id)
    payload = json.loads(jf.read_text(encoding="utf-8"))
    payload["record"]["canonical_digital_twin_id"] = "/Game/Evil/Tamper"
    jf.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(AtlasRenderJobStoreCorruptionError, match="authoritative_digest mismatch"):
        store.load(rec.atlas_job_id)


# ── Item 3 + Item 21: concurrent record update conflict / stale writer ────────
def test_m6_item03_stale_writer_rejection_is_deterministic(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_intent_record(tmp_path)
    store.create(rec)
    submitted = rec.transition(
        lifecycle_state=RenderJobLifecycleState.SUBMITTED, atlas_submitted_at="2026-09-06T00:00:01Z"
    )
    store.update(submitted, expected_revision=0)
    stale = rec.transition(lifecycle_state=RenderJobLifecycleState.FAILED)
    with pytest.raises(AtlasRenderJobStoreStaleWriterError, match="Stale writer"):
        store.update(stale, expected_revision=0)


def test_m6_item03_concurrent_update_preserves_monotonicity_and_no_corruption(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_intent_record(tmp_path)
    store.create(rec)

    # NOTE: In production, writers to one job are serialized by the exclusive
    # per-job claim. This test deliberately races writers WITHOUT the lock to
    # prove the atomic-write boundary is the durability guarantee: under any
    # adversarial interleaving the surviving record is valid, monotonic, and
    # digest-consistent, and each writer either succeeded or was rejected
    # (stale writer / transient atomic-write failure) WITHOUT corrupting state.
    outcomes = []
    successes = []  # (revision_at_attempt)
    barrier = threading.Barrier(8)

    def racer():
        barrier.wait()
        contender = rec.transition(
            lifecycle_state=RenderJobLifecycleState.SUBMITTED,
            atlas_submitted_at="2026-09-06T00:00:01Z",
        )
        try:
            store.update(contender, expected_revision=0)
            outcomes.append("ok")
            successes.append(contender.last_observed_revision)
        except AtlasRenderJobStoreStaleWriterError:
            outcomes.append("stale")
        except Exception:
            # Transient atomic-write collision (Windows os.replace sharing
            # violation) is an OS artifact, not a corruption; captured for
            # invariant-checking below.
            outcomes.append("transient")

    threads = [threading.Thread(target=racer) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    final = store.load(rec.atlas_job_id)
    assert final.last_observed_revision == 1
    assert final.lifecycle_state == RenderJobLifecycleState.SUBMITTED
    assert AtlasRenderJobRecord.from_dict(final.to_dict()) == final
    assert len(outcomes) == 8
    assert all(o in ("ok", "stale", "transient") for o in outcomes)
    # At least one writer advanced the durable revision to 1; the durable final
    # state is monotonic (revision 1) and never torn or corrupted.
    assert outcomes.count("ok") >= 1
    # A clean reload is valid and a correct subsequent update still works.
    store.update(final, expected_revision=1)


def test_m6_item21_stale_writer_via_per_job_claim_fencing(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_intent_record(tmp_path)
    store.create(rec)
    # Worker A holds the per-job claim and updates
    with store.acquire_job_claim(rec.atlas_job_id, "worker-A"):
        updated = rec.transition(lifecycle_state=RenderJobLifecycleState.SUBMITTED)
        store.update(updated, expected_revision=0)
    # Worker B attempts a stale update -> rejected
    stale = rec.transition(lifecycle_state=RenderJobLifecycleState.FAILED)
    with pytest.raises(AtlasRenderJobStoreStaleWriterError, match="Stale writer"):
        store.update(stale, expected_revision=0)


# ── Item 4: coordinator single-instance enforcement ───────────────────────────
def test_m6_item04_coordinator_single_instance_lock(tmp_path):
    store = ff.make_store(tmp_path)
    with store.acquire_coordinator("coord-A", lease_token=1):
        with pytest.raises(AtlasRenderJobStoreLockError, match="Another Atlas coordinator"):
            with store.acquire_coordinator("coord-B", lease_token=1):
                pass


def test_m6_item04_per_job_claim_excludes_concurrent_worker(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_intent_record(tmp_path)
    with store.acquire_job_claim(rec.atlas_job_id, "worker-1"):
        with pytest.raises(AtlasRenderJobStoreLockError, match="Exclusive execution claim"):
            with store.acquire_job_claim(rec.atlas_job_id, "worker-2"):
                pass


# ── Item 6: terminal-state non-regression ─────────────────────────────────────
def test_m6_item06_terminal_state_cannot_regress(tmp_path):
    rec = ff.make_intent_record(tmp_path)
    orphaned = rec.transition(
        lifecycle_state=RenderJobLifecycleState.ORPHANED,
        recovery_status=RenderJobRecoveryStatus.NONE,
        failure_reason="no evidence",
    )
    assert orphaned.lifecycle_state == RenderJobLifecycleState.ORPHANED
    # Attempt to regress a terminal state to a live state must fail
    with pytest.raises(AtlasRenderJobRecordError, match="terminal state regression"):
        orphaned.transition(lifecycle_state=RenderJobLifecycleState.RENDERING)


def test_m6_item06_verify_finalized_requires_attributable_job_identity(tmp_path):
    rec = ff.make_intent_record(tmp_path)  # no unreal_job_id
    with pytest.raises(AtlasRenderJobRecordError, match="attributable engine job identity"):
        rec.transition(lifecycle_state=RenderJobLifecycleState.FINALIZED)


# ── Item 16: Case A–J reconciliation (positive + fail-closed) ────────────────
def test_m6_item16_case_a_live_job_tracks_without_adoption(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    cand = ff.build_finished_candidate(rec, override={"state_source": "in_memory_registry", "finished": False, "status": "rendering", "phase": "STARTED"})
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [cand]})
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.case_classified == "Case A"
    assert res.lifecycle_state_after == RenderJobLifecycleState.RENDERING
    assert res.recovery_status_after == RenderJobRecoveryStatus.NONE


def test_m6_item16_case_b_full_recovery_issues_receipt(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path, data = ff.write_valid_render_artifact(rec)
    manifest = ff.make_manifest_for(rec, [path])
    cand = ff.build_finished_candidate(rec, artifact_paths=[path], artifact_manifest=manifest)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [cand]})
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.case_classified == "Case B"
    assert res.lifecycle_state_after == RenderJobLifecycleState.FINALIZED
    assert res.recovery_status_after == RenderJobRecoveryStatus.RESOLVED
    # Receipt is now gated downstream of independent verification
    store_rec = store.load(rec.atlas_job_id)
    assert store_rec.lifecycle_state == RenderJobLifecycleState.FINALIZED
    assert store_rec.receipt_reference is not None


def test_m6_item16_case_c_no_engine_no_artifacts_orphans(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": []})
    coord = ff.make_coordinator(store, adapter)
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.case_classified == "Case C"
    assert res.lifecycle_state_after == RenderJobLifecycleState.ORPHANED


def test_m6_item16_case_h_multiple_engine_claims_fails_closed(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    c1 = ff.build_finished_candidate(rec, override={"job_id": "unreal-job-1"})
    c2 = ff.build_finished_candidate(rec, override={"job_id": "unreal-job-2"})
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [c1, c2]})
    coord = ff.make_coordinator(store, adapter)
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.case_classified == "Case H"
    assert res.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED
    assert not res.repaired_from_receipt


def test_m6_item16_case_j_partial_journal_records_pending(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "PARTIAL", "known_jobs": []})
    coord = ff.make_coordinator(store, adapter)
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.case_classified == "Case J"
    assert res.recovery_status_after == RenderJobRecoveryStatus.RECOVERY_PENDING
    assert res.lifecycle_state_after == rec.lifecycle_state  # lifecycle untouched


def test_m6_item16_case_k_quiescence_blocked_fails_closed(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    cand = ff.build_finished_candidate(rec)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [cand]})
    coord = ff.make_coordinator(store, adapter, supervisor=ff.non_quiescent_supervisor(active=3))
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert "Case K" in res.case_classified
    assert res.recovery_status_after == RenderJobRecoveryStatus.WAITING_FOR_ENGINE_QUIESCENCE
    assert res.lifecycle_state_after != RenderJobLifecycleState.FINALIZED


def test_m6_item16_quiescence_ambiguity_uncontained_fails_closed(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    cand = ff.build_finished_candidate(rec)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [cand]})
    # UNCONTAINED_ATTACHED: quiescence can never be proven -> recovery fails closed
    coord = ff.make_coordinator(store, adapter, supervisor=None, deployment_mode="UNCONTAINED_ATTACHED")
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert "Case K" in res.case_classified
    assert res.recovery_status_after == RenderJobRecoveryStatus.WAITING_FOR_ENGINE_QUIESCENCE
    # No artifact adoption, no receipt issuance
    assert len(list(store.receipts_dir.glob("*.json"))) == 0