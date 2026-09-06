"""M7 hardening deterministic tests.

Covers the three M6-discovered production gaps that are now repaired:

- **A. Framed catalog integrity** (reconcile ``payload_byte_length`` /
  ``payload_sha256`` against canonical ``known_jobs``).
- **C. Execution/submission deadline enforcement** (EXHAUSTED + RECOVERY_FAILED
  transition, no retry, no receipt/finalization after exhaustion).

Test-only additions; no production behavior is weakened. ``now_utc`` is injected
for deterministic deadline evaluation. Live UE 5.6 Scenarios 1-8 are not run.
"""
import json
import datetime

import pytest

from planning.unreal_render_job_states import (
    TERMINAL_LIFECYCLE_STATES,
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
from planning.unreal_render_recovery_coordinator import (
    UnrealRenderRecoveryCoordinator,
    canonical_known_jobs_payload,
)
import tests.m6.fault_fixtures as ff


# ─────────────────────────────────────────────────────────────────────────────
# A. Framed catalog integrity
# ─────────────────────────────────────────────────────────────────────────────

def _framed_response(rec, cands, *, byte_length=None, sha256=None, known=None):
    known = cands if known is None else known
    payload = canonical_known_jobs_payload(known)
    return {
        "journal_status": "COMPLETE",
        "payload_byte_length": byte_length if byte_length is not None else len(payload),
        "payload_sha256": sha256 if sha256 is not None else ff.sha256_of(payload),
        "known_jobs": known,
    }


def test_m7_a_valid_framed_catalog_accepted(tmp_path):
    # A well-formed framed catalog (correct canonical length + SHA-256) is accepted
    # and proceeds through Case B verification -> FINALIZED + one receipt.
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path, data = ff.write_valid_render_artifact(rec)
    manifest = ff.make_manifest_for(rec, [path])
    cand = ff.build_finished_candidate(rec, artifact_paths=[path], artifact_manifest=manifest)
    response = _framed_response(rec, [cand])
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response=response)
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.case_classified == "Case B"
    assert res.lifecycle_state_after == RenderJobLifecycleState.FINALIZED
    assert res.recovery_status_after == RenderJobRecoveryStatus.RESOLVED
    assert len(list(store.receipts_dir.glob("*.json"))) == 1


def test_m7_a_incorrect_payload_length_rejected(tmp_path):
    # Wrong payload_byte_length must fail closed to UNREADABLE (Case J).
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path, data = ff.write_valid_render_artifact(rec)
    manifest = ff.make_manifest_for(rec, [path])
    cand = ff.build_finished_candidate(rec, artifact_paths=[path], artifact_manifest=manifest)
    response = _framed_response(rec, [cand], byte_length=99)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response=response)
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.case_classified == "Case J"
    assert res.recovery_status_after == RenderJobRecoveryStatus.RECOVERY_PENDING
    assert res.lifecycle_state_after != RenderJobLifecycleState.FINALIZED
    assert len(list(store.receipts_dir.glob("*.json"))) == 0


def test_m7_a_incorrect_payload_sha256_rejected(tmp_path):
    # Wrong payload_sha256 must fail closed to UNREADABLE (Case J).
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path, data = ff.write_valid_render_artifact(rec)
    manifest = ff.make_manifest_for(rec, [path])
    cand = ff.build_finished_candidate(rec, artifact_paths=[path], artifact_manifest=manifest)
    response = _framed_response(rec, [cand], sha256="b" * 64)  # wrong hash
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response=response)
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.case_classified == "Case J"
    assert len(list(store.receipts_dir.glob("*.json"))) == 0


def test_m7_a_malformed_incomplete_framing_rejected(tmp_path):
    # Only one framing field, or a missing known_jobs, is malformed/incomplete and
    # must fail closed to UNREADABLE (Case J).
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path, data = ff.write_valid_render_artifact(rec)
    manifest = ff.make_manifest_for(rec, [path])
    cand = ff.build_finished_candidate(rec, artifact_paths=[path], artifact_manifest=manifest)
    payload = canonical_known_jobs_payload([cand])

    # Only length present (missing sha).
    r1 = {"journal_status": "COMPLETE", "payload_byte_length": len(payload), "known_jobs": [cand]}
    # Invalid length type (non-int).
    r2 = {"journal_status": "COMPLETE", "payload_byte_length": "not-int", "payload_sha256": "0" * 64, "known_jobs": [cand]}
    # Invalid sha length.
    r3 = {"journal_status": "COMPLETE", "payload_byte_length": len(payload), "payload_sha256": "short", "known_jobs": [cand]}
    # Non-hex sha.
    r4 = {"journal_status": "COMPLETE", "payload_byte_length": len(payload), "payload_sha256": "g" * 64, "known_jobs": [cand]}
    # known_jobs missing entirely.
    r5 = {"journal_status": "COMPLETE", "payload_byte_length": len(payload), "payload_sha256": "0" * 64}

    for i, response in enumerate([r1, r2, r3, r4, r5]):
        adapter = ff.ScriptedCoordinatorAdapter(reconcile_response=response)
        coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
        res = coord.reconcile_single_job(rec.atlas_job_id)
        assert res.case_classified == "Case J", f"case {i} not Case J"
        assert res.lifecycle_state_after != RenderJobLifecycleState.FINALIZED, f"case {i} finalized"
        assert len(list(store.receipts_dir.glob("*.json"))) == 0, f"case {i} minted receipt"


def test_m7_a_canonical_serialization_is_deterministic():
    # canonical_known_jobs_payload is stable across:
    #   - frozen mappingproxy/tuple wrappers vs plain dicts
    #   - mapping key insertion order
    base = {"atlas_job_id": "a", "job_id": "b", "phase": "FINISHED",
            "manifest": [{"path": "/x", "size": 1, "sha256": "0" * 64}]}
    plain = [base]
    # Rebuild with reversed top-level key insertion to show sort_keys stability.
    reordered = [dict(reversed(list(base.items())))]
    from types import MappingProxyType
    from planning.unreal_render_job_record import _freeze_dict  # reuse deterministic freezer

    frozen = [_freeze_dict(base)]
    assert canonical_known_jobs_payload(plain) == canonical_known_jobs_payload(reordered)
    assert canonical_known_jobs_payload(plain) == canonical_known_jobs_payload(frozen)
    # Determinism across calls.
    assert canonical_known_jobs_payload(plain) == canonical_known_jobs_payload(plain)


def test_m7_a_framing_failure_never_finalizes_no_receipt(tmp_path):
    # Combined guarantee: when framing integrity fails, no finalization and no
    # receipt ever occurs, even if the underlying candidate looks complete.
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path, data = ff.write_valid_render_artifact(rec)
    manifest = ff.make_manifest_for(rec, [path])
    cand = ff.build_finished_candidate(rec, artifact_paths=[path], artifact_manifest=manifest)
    response = _framed_response(rec, [cand], byte_length=42)  # wrong length
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response=response)
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.lifecycle_state_after != RenderJobLifecycleState.FINALIZED
    assert len(list(store.receipts_dir.glob("*.json"))) == 0


# ─────────────────────────────────────────────────────────────────────────────
# C. Execution/submission deadline enforcement
# ─────────────────────────────────────────────────────────────────────────────

def _now():
    return datetime.datetime(2026, 9, 6, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _make_record_with_deadline(
    tmp_path,
    *,
    execution_deadline=None,
    submission_deadline=None,
    lifecycle=None,
    recovery_status=None,
):
    from dataclasses import replace

    rec = ff.make_submitted_record(tmp_path)
    # Deadline fields are operational (not part of the authoritative digest), so
    # dataclasses.replace is safe and deterministic: digest recomputation passes.
    if execution_deadline is not None:
        rec = replace(
            rec,
            execution_deadline=execution_deadline if isinstance(execution_deadline, str) else execution_deadline.isoformat(),
        )
    if submission_deadline is not None:
        rec = replace(
            rec,
            submission_deadline=submission_deadline if isinstance(submission_deadline, str) else submission_deadline.isoformat(),
        )
    # lifecycle / recovery-status advance through the record's transition API.
    trans_kwargs = {}
    if lifecycle is not None:
        trans_kwargs["lifecycle_state"] = lifecycle
    if recovery_status is not None:
        trans_kwargs["recovery_status"] = recovery_status
    if trans_kwargs:
        rec = rec.transition(**trans_kwargs)
    return rec


def test_m7_c_deadline_not_yet_expired(tmp_path):
    # A job whose deadline is in the future is NOT exhausted; it proceeds to
    # normal Case C (no evidence, no artifacts -> ORPHANED).
    store = ff.make_store(tmp_path)
    rec = _make_record_with_deadline(
        tmp_path,
        execution_deadline=datetime.datetime(2026, 9, 6, 13, 0, 0, tzinfo=datetime.timezone.utc),
    )
    store.create(rec)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": []})
    coord = ff.make_coordinator(store, adapter)
    res = coord.reconcile_single_job(rec.atlas_job_id, now_utc=_now())
    assert res.case_classified == "Case C"
    assert res.lifecycle_state_after == RenderJobLifecycleState.ORPHANED
    assert res.recovery_status_after != RenderJobRecoveryStatus.EXHAUSTED


def test_m7_c_deadline_exactly_expired(tmp_path):
    # A deadline exactly equal to `now` (>= at-or-after semantics) triggers
    # exhaustion: EXHAUSTED + RECOVERY_FAILED, never finalized.
    store = ff.make_store(tmp_path)
    rec = _make_record_with_deadline(
        tmp_path,
        execution_deadline=datetime.datetime(2026, 9, 6, 12, 0, 0, tzinfo=datetime.timezone.utc),  # == now
    )
    store.create(rec)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": []})
    coord = ff.make_coordinator(store, adapter)
    res = coord.reconcile_single_job(rec.atlas_job_id, now_utc=_now())
    assert res.case_classified == "DEADLINE_EXHAUSTED"
    assert res.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED
    assert res.recovery_status_after == RenderJobRecoveryStatus.EXHAUSTED
    assert res.lifecycle_state_after in TERMINAL_LIFECYCLE_STATES
    assert len(list(store.receipts_dir.glob("*.json"))) == 0


def test_m7_c_expired_before_reconciliation(tmp_path):
    # Deadline in the past before reconciliation -> exhausted, no evidence adopted.
    store = ff.make_store(tmp_path)
    rec = _make_record_with_deadline(
        tmp_path,
        execution_deadline=datetime.datetime(2020, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
    )
    store.create(rec)
    path, data = ff.write_valid_render_artifact(rec)  # artifacts present but unresolved
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": []})
    coord = ff.make_coordinator(store, adapter)
    res = coord.reconcile_single_job(rec.atlas_job_id, now_utc=_now())
    assert res.case_classified == "DEADLINE_EXHAUSTED"
    assert res.recovery_status_after == RenderJobRecoveryStatus.EXHAUSTED
    assert res.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED
    assert len(list(store.receipts_dir.glob("*.json"))) == 0


def test_m7_c_expired_during_recovery_still_exhausts(tmp_path):
    # Even if reconciliation has artifacts and would otherwise reach Case D/C,
    # an already-expired deadline pre-empts it and fails closed to EXHAUSTED.
    store = ff.make_store(tmp_path)
    rec = _make_record_with_deadline(
        tmp_path,
        execution_deadline=datetime.datetime(2020, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
        recovery_status=RenderJobRecoveryStatus.WAITING_FOR_ENGINE,
    )
    store.create(rec)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": []})
    coord = ff.make_coordinator(store, adapter)
    res = coord.reconcile_single_job(rec.atlas_job_id, now_utc=_now())
    assert res.case_classified == "DEADLINE_EXHAUSTED"
    assert res.recovery_status_after == RenderJobRecoveryStatus.EXHAUSTED
    assert res.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED


def test_m7_c_expired_transport_uncertainty_exhausts(tmp_path):
    # A job left in RECOVERY_PENDING (transport uncertainty) whose deadline has
    # expired is EXHAUSTED, not auto-retried and not minted terminal success.
    from dataclasses import replace

    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path).transition(
        recovery_status=RenderJobRecoveryStatus.RECOVERY_PENDING,
        failure_reason="Transport uncertainty during submission",
        increment_ambiguity=True,
    )
    rec2 = replace(
        rec,
        execution_deadline=datetime.datetime(2020, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc).isoformat(),
    )
    store.create(rec2)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": []})
    coord = ff.make_coordinator(store, adapter)
    res = coord.reconcile_single_job(rec2.atlas_job_id, now_utc=_now())
    assert res.case_classified == "DEADLINE_EXHAUSTED"
    assert res.recovery_status_after == RenderJobRecoveryStatus.EXHAUSTED
    assert res.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED
    assert adapter.reconcile_query_count == 0  # never queried/never retried


def test_m7_c_exhausted_transition_and_status(tmp_path):
    # Assert the persisted record reflects EXHAUSTED / RECOVERY_FAILED with a
    # descriptive failure reason.
    store = ff.make_store(tmp_path)
    rec = _make_record_with_deadline(
        tmp_path,
        submission_deadline=datetime.datetime(2020, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
    )
    store.create(rec)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": []})
    coord = ff.make_coordinator(store, adapter)
    res = coord.reconcile_single_job(rec.atlas_job_id, now_utc=_now())
    assert res.case_classified == "DEADLINE_EXHAUSTED"
    persisted = store.load(rec.atlas_job_id)
    assert persisted.lifecycle_state == RenderJobLifecycleState.RECOVERY_FAILED
    assert persisted.recovery_status == RenderJobRecoveryStatus.EXHAUSTED
    assert "deadline expired" in (persisted.failure_reason or "")


def test_m7_c_no_retry_after_exhaustion(tmp_path):
    # Once exhausted (terminal RECOVERY_FAILED/EXHAUSTED), a subsequent recovery
    # sweep must SKIP the job entirely - no resubmission, no further mutation.
    store = ff.make_store(tmp_path)
    rec = _make_record_with_deadline(
        tmp_path,
        execution_deadline=datetime.datetime(2020, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
    )
    store.create(rec)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": []})
    coord = ff.make_coordinator(store, adapter)

    # First pass: job is exhausted (terminal).
    res1 = coord.reconcile_all_non_terminal_jobs(lease_token=1, now_utc=_now())
    assert len(res1) == 1
    assert res1[0].case_classified == "DEADLINE_EXHAUSTED"
    first_rev = store.load(rec.atlas_job_id).last_observed_revision

    # Second pass: the terminal job is skipped entirely - no mutation, no query.
    adapter.reconcile_query_count = 0
    res2 = coord.reconcile_all_non_terminal_jobs(lease_token=2, now_utc=_now())
    assert res2 == []
    persisted = store.load(rec.atlas_job_id)
    assert persisted.last_observed_revision == first_rev
    assert persisted.lifecycle_state == RenderJobLifecycleState.RECOVERY_FAILED
    assert adapter.reconcile_query_count == 0


def test_m7_c_no_receipt_finalization_after_exhaustion(tmp_path):
    # After exhaustion, no receipt and no FINALIZED state.
    store = ff.make_store(tmp_path)
    rec = _make_record_with_deadline(
        tmp_path,
        execution_deadline=datetime.datetime(2020, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
    )
    store.create(rec)
    path, data = ff.write_valid_render_artifact(rec)
    manifest = ff.make_manifest_for(rec, [path])
    cand = ff.build_finished_candidate(rec, artifact_paths=[path], artifact_manifest=manifest)
    # Even a well-formed finished candidate cannot be adopted after exhaustion.
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [cand]})
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res = coord.reconcile_single_job(rec.atlas_job_id, now_utc=_now())
    assert res.case_classified == "DEADLINE_EXHAUSTED"
    assert res.lifecycle_state_after != RenderJobLifecycleState.FINALIZED
    assert len(list(store.receipts_dir.glob("*.json"))) == 0


def test_m7_c_submission_deadline_also_enforced(tmp_path):
    # A job still in PENDING_SUBMISSION whose submission_deadline expired is
    # exhausted (submission-deadline bound honored).
    from dataclasses import replace

    store = ff.make_store(tmp_path)
    rec = replace(
        ff.make_intent_record(tmp_path),
        submission_deadline=datetime.datetime(2020, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc).isoformat(),
    )
    store.create(rec)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": []})
    coord = ff.make_coordinator(store, adapter)
    res = coord.reconcile_single_job(rec.atlas_job_id, now_utc=_now())
    assert res.case_classified == "DEADLINE_EXHAUSTED"
    assert res.recovery_status_after == RenderJobRecoveryStatus.EXHAUSTED
    assert res.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED


def test_m7_c_reconcile_all_enforces_deadlines(tmp_path):
    # reconcile_all_non_terminal_jobs routes an expired-deadline job to EXHAUSTED.
    store = ff.make_store(tmp_path)
    rec = _make_record_with_deadline(
        tmp_path,
        execution_deadline=datetime.datetime(2020, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
    )
    store.create(rec)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": []})
    coord = ff.make_coordinator(store, adapter)
    results = coord.reconcile_all_non_terminal_jobs(lease_token=1, now_utc=_now())
    assert len(results) == 1
    assert results[0].case_classified == "DEADLINE_EXHAUSTED"
    persisted = store.load(rec.atlas_job_id)
    assert persisted.recovery_status == RenderJobRecoveryStatus.EXHAUSTED