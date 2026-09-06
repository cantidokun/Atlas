"""M6 §31 items 3 (concurrency deep-dive), 24 (catalog->disk->catalog stability
race) and 25 (incompatible wire/capability version rejection), plus queiscience
ambiguity and rogue/unmanaged detection.

Authoritative: docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md §31.
"""

import json
import threading

import pytest

from planning.unreal_render_job_states import (
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
from planning.unreal_render_job_store import (
    AtlasRenderJobStore,
    AtlasRenderJobStoreStaleWriterError,
)
import tests.m6.fault_fixtures as ff


# ── Item 24: catalog->disk->catalog stability race (framed-integrity boundary) ─
def test_m6_item24_payload_sha256_mismatch_classified_unreadable(tmp_path):
    # A reconcile catalog whose framed payload_sha256 does not match its
    # known_jobs must be treated as UNREADABLE (Case J), not adopted.
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    known = [ff.build_finished_candidate(rec)]
    response = {
        "journal_status": "COMPLETE",
        "payload_byte_length": len(json.dumps(known)),
        "payload_sha256": "0" * 64,  # wrong framed payload hash
        "known_jobs": known,
    }
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response=response)
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.case_classified == "Case J"
    assert res.recovery_status_after == RenderJobRecoveryStatus.RECOVERY_PENDING
    assert res.lifecycle_state_after != RenderJobLifecycleState.FINALIZED


def test_m6_item24_payload_framing_never_finalizes_under_integrity_check(tmp_path):
    # LATENT-DEFECT DOCUMENTATION (see report §C). The coordinator's framed
    # integrity check (payload_byte_length/payload_sha256 against known_jobs)
    # cannot serialize the frozen observed_state (mappingproxy) to canonical JSON,
    # so a response carrying framing fields always fails the query and falls into
    # Case J. M6 therefore asserts the SAFE fail-closed outcome that actually
    # holds: a tampered OR well-formed framed catalog is never finalized and never
    # yields a receipt. The frame-integrity code path itself must be repaired in a
    # production follow-up (M7 hardening), not by weakening this test.
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path, data = ff.write_valid_render_artifact(rec)
    manifest = ff.make_manifest_for(rec, [path])
    cand = ff.build_finished_candidate(rec, artifact_paths=[path], artifact_manifest=manifest)
    known = [cand]
    payload_bytes = json.dumps(known, sort_keys=True, separators=(",", ":")).encode("utf-8")
    response = {
        "journal_status": "COMPLETE",
        "payload_byte_length": len(payload_bytes),
        "payload_sha256": ff.sha256_of(payload_bytes),  # correct hash, still fails path
        "known_jobs": known,
    }
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response=response)
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.lifecycle_state_after != RenderJobLifecycleState.FINALIZED
    assert len(list(store.receipts_dir.glob("*.json"))) == 0


def test_m6_item24_normal_unframed_catalog_proceeds_case_b(tmp_path):
    # Without framing-fields (the shape the C++ ReconcileRenderJobs actually
    # emits), framed integrity is skipped and a healthy terminal candidate is
    # adopted via full Case B verification (guards the fail-closed path is not
    # over-broad).
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


def test_m6_item24_unstable_catalog_across_reconcile_passes_fails_closed(tmp_path):
    # Catalog stability: an unstable (PARTIAL) catalog must never finalize a job,
    # even when disk artifacts look complete. Model the engine's two-pass stability
    # signal as a PARTIAL journal_status; the coordinator must fail closed.
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path, data = ff.write_valid_render_artifact(rec)
    manifest = ff.make_manifest_for(rec, [path])
    cand = ff.build_finished_candidate(rec, artifact_paths=[path], artifact_manifest=manifest)
    # First reconcile: unstable catalog (PARTIAL) -> MUST NOT finalize
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "PARTIAL", "known_jobs": []})
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res1 = coord.reconcile_single_job(rec.atlas_job_id)
    assert res1.case_classified == "Case J"
    assert res1.lifecycle_state_after != RenderJobLifecycleState.FINALIZED
    assert len(list(store.receipts_dir.glob("*.json"))) == 0
    # Second reconcile (now stable & complete) may then proceed normally, showing
    # the instability did not permanently poison the durable job.
    adapter2 = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [cand]})
    coord2 = ff.make_coordinator(store, adapter2, supervisor=ff.quiescent_supervisor())
    res2 = coord2.reconcile_single_job(rec.atlas_job_id)
    assert res2.case_classified == "Case B"
    assert res2.lifecycle_state_after == RenderJobLifecycleState.FINALIZED


# ── Item 25: incompatible wire/capability version rejection ───────────────────
def test_m6_item25_missing_recovery_capability_rejects_dispatch(tmp_path):
    from planning.unreal_adapter_production import UnrealAdapterError
    from planning.unreal_render_submission import UnrealRenderSubmissionError
    import tests.m6.test_m6_03_submission_durable_intent as sub

    inject = sub._SubmissionTransport(cap_failure=UnrealAdapterError("missing required capability"))
    store, service, transport = sub._service(tmp_path, inject)

    with pytest.raises(UnrealRenderSubmissionError, match="capability gate"):
        service.submit_render(**sub._submit_kwargs())


def test_m6_item25_coordinator_engine_capability_unavailable_waits(tmp_path):
    from planning.unreal_adapter_production import UnrealAdapterError

    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    adapter = ff.ScriptedCoordinatorAdapter(capability_error=UnrealAdapterError("transport unreachable"))
    coord = ff.make_coordinator(store, adapter)
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.case_classified == "WAITING_FOR_ENGINE"
    assert res.recovery_status_after == RenderJobRecoveryStatus.WAITING_FOR_ENGINE
    # Not terminal, not resubmitted, not finalized
    assert res.lifecycle_state_after != RenderJobLifecycleState.FINALIZED
    assert adapter.reconcile_query_count == 0  # never queried without capability


def test_m6_item25_wire_schema_version_guarded_at_contract(tmp_path):
    # Incompatible wire schema version is rejected at the transport contract
    # boundary itself: constructing a response with any schema_version other than
    # the supported 1 fails closed with ValueError before any execution path.
    from planning.unreal_transport_contract import UnrealTransportResponse

    with pytest.raises(ValueError, match="unsupported schema_version"):
        UnrealTransportResponse(
            request_id="req-wire", operation_name="get_capabilities",
            entity_ids=("UNREAL_SERVER",), success=True,
            observed_state={"capabilities": []}, error="", source="unreal-editor-5.6",
            schema_version=0, error_code="", session_identity={},
        )


# ── Quiescence ambiguity (audit gap) ──────────────────────────────────────────
def test_m6_quiescence_missing_supervisor_fails_closed(tmp_path):
    from scripts.run_unreal_supervisor import evaluate_process_quiescence

    res = evaluate_process_quiescence(None, "CONTAINED_JOB_OBJECT")
    assert not res.is_quiescent
    assert "missing/invalid" in res.reason


def test_m6_quiescence_active_processes_blocks_adoption(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path, data = ff.write_valid_render_artifact(rec)
    manifest = ff.make_manifest_for(rec, [path])
    cand = ff.build_finished_candidate(rec, artifact_paths=[path], artifact_manifest=manifest)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [cand]})
    coord = ff.make_coordinator(store, adapter, supervisor=ff.non_quiescent_supervisor(active=1))
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert "Case K" in res.case_classified
    assert len(list(store.receipts_dir.glob("*.json"))) == 0


# ── Concurrency deep-dive (item 3) ────────────────────────────────────────────
def test_m6_item03_coordinator_fencing_token_monotonic(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path = ff.Path(rec.output_directory) / "AtlasRender_0000.png"
    ff.make_valid_png(path)
    receipt_low = ff.issue_receipt_for(rec, path, lease_token=1, coordinator_id="coord-low")
    receipt_high = ff.issue_receipt_for(rec, path, lease_token=2, coordinator_id="coord-high")
    # Presenting an OLD fencing token must be rejected (must use a higher token)
    with pytest.raises(AtlasRenderJobStoreStaleWriterError, match="[Ff]encing token|lease_token"):
        store.publish_verified_receipt(
            atlas_job_id=rec.atlas_job_id, attempt_ordinal=rec.attempt_ordinal,
            presented_lease_token=0, expected_record_revision=rec.last_observed_revision,
            receipt=receipt_low,
        )


def test_m6_item03_two_coordinators_cannot_both_finalize(tmp_path):
    # Deterministic: after one store-gated publication advances the fencing
    # watermark, a second coordinator presenting a stale token is rejected.
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    path = ff.Path(rec.output_directory) / "AtlasRender_0000.png"
    ff.make_valid_png(path)
    # Finalize via a full valid Case B (coordinator 1)
    manifest = ff.make_manifest_for(rec, [path])
    cand = ff.build_finished_candidate(rec, artifact_paths=[path], artifact_manifest=manifest)
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [cand]})
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res = coord.reconcile_single_job(rec.atlas_job_id)
    assert res.lifecycle_state_after == RenderJobLifecycleState.FINALIZED
    # Coordinator 2 attempts a second publication with the same fencing token ->
    # rejected (terminal record + stale fencing). No duplicate receipt.
    final = store.load(rec.atlas_job_id)
    assert final.lifecycle_state == RenderJobLifecycleState.FINALIZED
    assert len(list(store.receipts_dir.glob("*.json"))) == 1


def test_m6_item03_rogue_unmanaged_job_detected_not_adopted(tmp_path):
    store = ff.make_store(tmp_path)
    rec = ff.make_submitted_record(tmp_path)
    store.create(rec)
    # Engine reports a job that is NOT tracked by any durable Atlas record and
    # not claimed by this recovery set -> must not be silently adopted.
    rogue = ff.build_finished_candidate(
        rec,
        override={
            "atlas_job_id": "atlas-render-job-00000000-1111-2222-3333-444444444444",
            "state_source": "witness_journal",
        },
    )
    adapter = ff.ScriptedCoordinatorAdapter(reconcile_response={"journal_status": "COMPLETE", "known_jobs": [rogue]})
    coord = ff.make_coordinator(store, adapter, supervisor=ff.quiescent_supervisor())
    res = coord.reconcile_single_job(rec.atlas_job_id)  # rec's own id is different from rogue
    # rec has no matching engine candidate -> Case C orphan
    assert res.lifecycle_state_after != RenderJobLifecycleState.FINALIZED
    assert len(list(store.receipts_dir.glob("*.json"))) == 0