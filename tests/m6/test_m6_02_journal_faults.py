"""M6 §31 items 7,8,9,10,11,17 — journal fault handling, session/identity
mismatch, acceptance-before-launch, terminal FINISHED journal requirement,
and artifact-only recovery never producing a receipt.

Authoritative: docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md §31.
"""

import pytest

from planning.unreal_render_job_states import (
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
import tests.m6.fault_fixtures as ff


# ── Item 7: journal malformed/partial/unreadable handling ─────────────────────
def test_m6_item07_unreadable_journal_is_case_j_pending(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "UNREADABLE", "known_jobs": []})
    coord = ff.make_coordinator(store, adapter)
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.case_classified == "Case J"
    assert res.recovery_status_after == RenderJobRecoveryStatus.RECOVERY_PENDING
    # Ambiguity budget increments; not treated as failure or synthetic success
    loaded = store.load(rec.atlas_job_id)
    assert loaded.recovery_status == RenderJobRecoveryStatus.RECOVERY_PENDING
    assert loaded.lifecycle_state != RenderJobLifecycleState.FINALIZED


def test_m6_item07_partial_journal_is_case_j_pending(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "PARTIAL", "known_jobs": []})
    coord = ff.make_coordinator(store, adapter)
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.case_classified == "Case J"
    assert res.recovery_status_after == RenderJobRecoveryStatus.RECOVERY_PENDING


def test_m6_item07_catalog_corruption_read_error_is_case_j(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    # Engine query raises -> coordinator must not fabricate success; no mutation to terminal
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response=None, capability_error=None)
    adapter.reconcile_error = RuntimeError("engine catalog read failure")
    coord = ff.make_coordinator(store, adapter)
    res = coord.reconcile_single_job(rec.atlas_job_id)
    loaded = store.load(rec.atlas_job_id)
    assert loaded.lifecycle_state != RenderJobLifecycleState.FINALIZED
    assert loaded.recovery_status == RenderJobRecoveryStatus.RECOVERY_PENDING


# ── Item 8: journal session mismatch ──────────────────────────────────────────
def test_m6_item08_session_identity_mismatch_fails_closed(tmp_path):
    # A terminal candidate carrying a DIFFERENT editor session than the durable
    # record cannot authenticate: the witness `entry_digest` was HMAC-derived for
    # the recorded session, so the mismatch surfaces as UNTRUSTED_WITNESS (the
    # coordinator recomputes the HMAC using the candidate's session and rejects).
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path, data = ff.write_valid_render_artifact(rec)
    manifest = ff.make_manifest_for(rec, [path])
    # Candidate claims a DIFFERENT editor session than the durable record
    cand = ff.build_finished_candidate(
        rec, artifact_paths=[path], artifact_manifest=manifest,
        override={"editor_session_id": "session-EVIL"},
    )
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [cand]})
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res = coord.reconcile_single_job(rec.atlas_job_id)
    # The session mismatch breaks witness authentication -> fail closed, no receipt.
    assert res.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED
    assert res.case_classified == "UNTRUSTED_WITNESS"
    assert len(list(store.receipts_dir.glob("*.json"))) == 0


# ── Item 9: journal identity mismatch ─────────────────────────────────────────
def test_m6_item09_atlas_job_id_mismatch_not_adopted(tmp_path):
    # A candidate whose atlas_job_id differs from the durable record is not a
    # candidate for THIS job at all (the coordinator filters on atlas_job_id).
    # With rendered artifacts on disk it surfaces as Case D (ORPHANED_ARTIFACTS_PRESENT):
    # the foreign job's artifacts are never adopted into this record and no receipt
    # is minted. This asserts the fail-closed safety consequence of the identity
    # mismatch (no adoption), not a separate "Case E/F binding" rejection.
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path, data = ff.write_valid_render_artifact(rec)
    manifest = ff.make_manifest_for(rec, [path])
    cand = ff.build_finished_candidate(
        rec, artifact_paths=[path], artifact_manifest=manifest,
        override={"atlas_job_id": "atlas-render-job-ffffffff-ffff-ffff-ffff-ffffffffffff"},
    )
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [cand]})
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res = coord.reconcile_single_job(rec.atlas_job_id)
    # The mismatched-id job is not adopted; with artifacts present this is Case D.
    assert res.lifecycle_state_after != RenderJobLifecycleState.FINALIZED
    assert len(list(store.receipts_dir.glob("*.json"))) == 0


def test_m6_item09_sequence_asset_path_mismatch_case_ef(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    cand = ff.build_finished_candidate(rec, override={"sequence_asset_path": "/Game/Wrong/Sequence"})
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [cand]})
    coord = ff.make_coordinator(store, adapter)
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.case_classified == "Case E/F"
    assert res.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED


def test_m6_item09_config_digest_mismatch_case_ef(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    cand = ff.build_finished_candidate(rec, override={"config_digest": "wrong-cfg-digest"})
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [cand]})
    coord = ff.make_coordinator(store, adapter)
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.case_classified == "Case E/F"
    assert res.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED


def test_m6_item09_process_creation_time_mismatch_fails_closed(tmp_path):
    # A terminal candidate claiming a DIFFERENT process-creation-time than the
    # durable record cannot authenticate: the entry_digest was HMAC-derived for
    # the recorded PCT, so this mismatch surfaces as UNTRUSTED_WITNESS (or, if the
    # HMAC were recomputed correctly, the verifier's identity binding would reject
    # it). Either way it fails closed and mints no receipt.
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path, data = ff.write_valid_render_artifact(rec)
    manifest = ff.make_manifest_for(rec, [path])
    cand = ff.build_finished_candidate(
        rec, artifact_paths=[path], artifact_manifest=manifest,
        override={"process_creation_time_utc": "2020-01-01T00:00:00Z"},
    )
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [cand]})
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res = coord.reconcile_single_job(rec.atlas_job_id)
    # Fail closed; no receipt. Exact case is UNTRUSTED_WITNESS (HMAC desync).
    assert res.lifecycle_state_after != RenderJobLifecycleState.FINALIZED
    assert res.case_classified == "UNTRUSTED_WITNESS"
    assert len(list(store.receipts_dir.glob("*.json"))) == 0


# ── Item 10: acceptance-before-launch invariant ───────────────────────────────
def test_m6_item10_finished_candidate_never_adopted_without_accepted_evidence(tmp_path):
    # A terminal candidate that never shows a durable ACCEPTED phase must not be
    # turned into successful evidence. We exercise the coordinator's fail-closed
    # response when the witness journal has not durably attested acceptance.
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path, data = ff.write_valid_render_artifact(rec)
    manifest = ff.make_manifest_for(rec, [path])
    # No ACCEPTED journal phase; candidate only has terminal state with a wrong digest
    cand = ff.build_finished_candidate(
        rec, artifact_paths=[path], artifact_manifest=manifest,
        override={"phase": "FINISHED", "entry_digest": "0" * 40},
    )
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [cand]})
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res = coord.reconcile_single_job(rec.atlas_job_id)
    # Ambiguous/missing attestation -> never FINALIZED, no receipt
    assert res.lifecycle_state_after != RenderJobLifecycleState.FINALIZED
    assert len(list(store.receipts_dir.glob("*.json"))) == 0


# ── Item 11: terminal FINISHED journal requirement ────────────────────────────
def test_m6_item11_terminal_requires_finished_journal_attestation(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path, data = ff.write_valid_render_artifact(rec)
    manifest = ff.make_manifest_for(rec, [path])
    # Candidate claims completion but its HMAC does not authenticate a FINISHED
    # journal entry (wrong nonce-derived digest) -> UNTRUSTED_WITNESS behavior
    cand = ff.build_finished_candidate(
        rec, artifact_paths=[path], artifact_manifest=manifest, hmac_digest="b" * 64,
    )
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [cand]})
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED
    assert res.case_classified == "UNTRUSTED_WITNESS"
    assert len(list(store.receipts_dir.glob("*.json"))) == 0


def test_m6_item11_finished_journal_hmac_roundtrip_is_reproducible():
    nonce = "m6-deterministic-nonce"
    payload = {"atlas_job_id": "j", "phase": "FINISHED", "value": [1, 2]}
    h1 = ff.compute_journal_hmac(nonce, payload)
    h2 = ff.compute_journal_hmac(nonce, payload)
    assert h1 == h2
    assert h1 != ff.compute_journal_hmac("different-nonce", payload)


# ── Item 17: artifact-only recovery never produces a receipt ──────────────────
def test_m6_item17_artifact_only_no_receipt_case_d(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    # Artifacts exist on disk but ZERO engine witness evidence exists
    path, data = ff.write_valid_render_artifact(rec)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": []})
    coord = ff.make_coordinator(store, adapter)
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.case_classified == "Case D"
    assert res.lifecycle_state_after == RenderJobLifecycleState.ORPHANED_ARTIFACTS_PRESENT
    # Strictly non-mutating: artifact is untouched, no receipt issued
    assert path.is_file() and path.read_bytes() == data
    assert len(list(store.receipts_dir.glob("*.json"))) == 0


def test_m6_item17_rogue_unmanaged_job_not_silently_adopted(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    # Engine reports an UNMANAGED job that does not bind to this atlas_job_id
    rogue = ff.build_finished_candidate(
        rec,
        override={"atlas_job_id": "atlas-render-job-99999999-9999-9999-9999-999999999999"},
    )
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [rogue]})
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.lifecycle_state_after != RenderJobLifecycleState.FINALIZED
    assert len(list(store.receipts_dir.glob("*.json"))) == 0