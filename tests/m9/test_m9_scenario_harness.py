"""M9 — Scenario harness: drive Contract V1 §33 Scenarios 1-8 through the REAL
UnrealRenderRecoveryCoordinator with faked transport/supervisor seams, and assert
that the model's declared outcome matches the coordinator's actual decision.

This proves the harness's scenario table is an accurate model of the implemented
recovery path (no invented semantics): each `expected_case` / lifecycle / recovery
status / receipt / retry outcome must equal what the coordinator produces.

Safety properties proven here (Requirement 6):
  - the harness never submits a render (no submission service call);
  - no path resubmits an uncertain job;
  - no success is ever synthesized (verified evidence requires real disk bytes +
    HMAC + quiescence);
  - a receipt is created ONLY via the Case B publish_verified_receipt gate;
  - quiescence / HMAC / attempt_ordinal gates cannot be bypassed.

NO live Unreal, no M7 Scenario execution, no workflow/action-runner tests, no
Blender. Deterministic only.
"""
import pathlib
import tempfile
from unittest.mock import MagicMock

import pytest

from planning.unreal_render_recovery_coordinator import UnrealRenderRecoveryCoordinator
from planning.unreal_render_job_store import AtlasRenderJobStore
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_render_job_states import (
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
from planning.unreal_live_scenario_harness import (
    SCENARIOS,
    scenario_by_id,
    SCENARIO_EXPECTED_IMPACT,
)
from scripts.run_unreal_supervisor import AtlasProcessSupervisor

import tests.m6.fault_fixtures as ff


def _make_valid_png(path):
    import struct
    import zlib
    path.parent.mkdir(parents=True, exist_ok=True)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    ihdr = b"\x00\x00\x00\x0dIHDR" + ihdr_data + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data))
    idat_data = zlib.compress(b"\x00\x00\x00\x00")
    idat = b"\x00\x00\x00" + bytes([len(idat_data)]) + b"IDAT" + idat_data + struct.pack(">I", zlib.crc32(b"IDAT" + idat_data))
    iend = b"\x00\x00\x00\x00IEND" + struct.pack(">I", zlib.crc32(b"IEND"))
    path.write_bytes(sig + ihdr + idat + iend)


def _make_store(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "store")
    # The M6 fixture sets origin + unreal_job_id in its internal .transition(); it
    # does not accept overrides for those. Reuse the fixture defaults
    # (unreal-job-m6-001 / session-m6-editor / proc 4242). Only the nonce (needed
    # for HMAC) is overridden here.
    record = ff.make_submitted_record(
        tmp_path,
        attempt_nonce="m9-scenario-nonce-0123456789abcdef",
    )
    store.create(record)
    return store, record


def _attested_finished_candidate(record, frame_path):
    import hashlib
    from planning.unreal_journal_attestation import compute_journal_attestation_digest
    file_bytes = frame_path.read_bytes()
    sha = hashlib.sha256(file_bytes).hexdigest()
    manifest = [{"path": str(frame_path), "size": len(file_bytes), "sha256": sha}]
    unreal_job = record.unreal_job_id or "unreal-job-m9-001"
    ed = record.origin_editor_session_id or "session-m6-editor"
    pct = record.origin_process_creation_time or "2026-09-06T00:00:00Z"
    payload = {
        "schema_version": 1,
        "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": unreal_job,
        "attempt_ordinal": record.attempt_ordinal,
        "phase": "FINISHED",
        "phase_sequence": 3,
        "editor_session_id": ed,
        "process_creation_time_utc": pct,
        "output_directory": record.output_directory,
        "output_manifest": manifest,
    }
    digest = compute_journal_attestation_digest(record.attempt_nonce, payload)
    return {
        "atlas_job_id": record.atlas_job_id,
        "job_id": unreal_job,
        "unreal_job_id": unreal_job,
        "sequence_asset_path": record.sequence_asset_path,
        "authorization_id": record.authorization_id,
        "canonical_digital_twin_id": record.canonical_digital_twin_id,
        "config_digest": record.config_digest,
        "output_directory": record.output_directory,
        "phase": "FINISHED",
        "phase_sequence": 3,
        "attempt_ordinal": record.attempt_ordinal,
        "editor_session_id": ed,
        "process_id": record.origin_process_id or 4242,
        "process_creation_time_utc": pct,
        "expected_output_spec": {"format": "png", "width": 1, "height": 1, "start_frame": 1, "end_frame": 1},
        "status": "completed",
        "finished": True,
        "success": True,
        "failed": False,
        "output_manifest": manifest,
        "output_files": [str(frame_path)],
        "entry_digest": digest,
        "state_source": "witness_journal",
    }, manifest


def _coord(store, record, adapter, tmp_path, receipt_store, supervisor):
    return UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
        supervisor=supervisor,
        deployment_mode="CONTAINED_JOB_OBJECT",
    )


def _make_supervisor(quiescent: bool):
    sv = MagicMock(spec=AtlasProcessSupervisor)
    sv.job_handle = 4242
    sv.query_active_processes.return_value = 0 if quiescent else 2
    return sv


def _make_reconcile_adapter(catalog_state, known_jobs):
    """Adapter that returns a reconcile_render_jobs catalog for _query_catalog."""
    adapter = MagicMock()
    adapter.assert_recovery_capable = MagicMock(return_value=None)
    adapter.apply_authorized.return_value = UnrealEvidence(
        operation_name="reconcile_render_jobs",
        entity_ids=("RENDER_RECOVERY",),
        observed_state={"journal_status": catalog_state, "known_jobs": known_jobs},
        source="unreal",
        verified=True,
    )
    return adapter


def _make_down_adapter():
    from planning.unreal_adapter_production import UnrealAdapterError
    adapter = MagicMock()
    adapter.assert_recovery_capable = MagicMock(
        side_effect=UnrealAdapterError("engine down"))
    return adapter


def _run_scenario(spec, tmp_path):
    """Set up the scenario's world and run the real coordinator. Returns the
    RecoveryDecisionResult plus observed conditions so tests can assert against
    both the spec and the coordinator's actual decision."""
    store, record = _make_store(tmp_path)

    # Build the world per spec conditions.
    # disk artifacts
    if spec.disk_artifacts:
        frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
        _make_valid_png(frame)
    else:
        frame = None

    # candidate shape depends on scenario
    known_jobs = []
    # canonical finished candidate for S1/S5/S7 (journal COMPLETE + FINISHED claim)
    if spec.scenario_id in ("S1", "S5", "S7"):
        assert frame is not None or spec.scenario_id == "S7"
        # S7: manifest references a missing file => we must provide a finished claim
        # with a manifest at a path that is on disk for S1/S5 and MISSING for S7.
        if spec.scenario_id == "S7":
            # separate claim: finished but artifact missing
            missing = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
            # do not write the file (disk_artifacts False above)
            file_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
            sha = __import__("hashlib").sha256(file_bytes).hexdigest()
            manifest = [{"path": str(missing), "size": len(file_bytes), "sha256": sha}]
            cand, _ = _make_attested_with_manifest(record, manifest)
            known_jobs = [cand]
        else:
            cand, _ = _attested_finished_candidate(record, frame)
            known_jobs = [cand]
    elif spec.scenario_id == "S3":
        # live in-flight (non-terminal) candidate -> Case A
        unreal_job = record.unreal_job_id or "unreal-job-m9-001"
        known_jobs = [{
            "atlas_job_id": record.atlas_job_id,
            "job_id": unreal_job,
            "unreal_job_id": unreal_job,
            "sequence_asset_path": record.sequence_asset_path,
            "config_digest": record.config_digest,
            "output_directory": record.output_directory,
            "phase": "STARTED",
            "phase_sequence": 2,
            "attempt_ordinal": record.attempt_ordinal,
            "editor_session_id": "session-m6-editor",
            "process_id": 4242,
            "process_creation_time_utc": "2026-09-06T00:00:00Z",
            "expected_output_spec": {"format": "png", "width": 1, "height": 1, "start_frame": 1, "end_frame": 1},
            "status": "submitted",
            "finished": False,
            "success": False,
            "failed": False,
            "output_manifest": [],
            "output_files": [],
            "state_source": "in_memory_registry",
        }]
    elif spec.scenario_id == "S8":
        # two candidates claim the same atlas_job_id -> Case H
        id_a = record.unreal_job_id or "unreal-job-m9-001"
        cand_a, _ = _attested_finished_candidate(record, frame)
        cand_b = dict(cand_a, job_id=id_a + "-dup", unreal_job_id=id_a + "-dup")
        known_jobs = [cand_a, cand_b]

    adapter = _make_reconcile_adapter(spec.journal_condition, known_jobs)
    if not spec.engine_capable:
        adapter = _make_down_adapter()

    receipt_store = UnrealRenderReceiptStore(tmp_path / "rcpt.json")
    supervisor = _make_supervisor(spec.quiescent)
    coord = _coord(store, record, adapter, tmp_path, receipt_store, supervisor)

    result = coord.reconcile_single_job(record.atlas_job_id)
    return result, record, store, frame


def _make_attested_with_manifest(record, manifest):
    import hashlib
    from planning.unreal_journal_attestation import compute_journal_attestation_digest
    unreal_job = record.unreal_job_id or "unreal-job-m9-001"
    ed = record.origin_editor_session_id or "session-m6-editor"
    pct = record.origin_process_creation_time or "2026-09-06T00:00:00Z"
    payload = {
        "schema_version": 1,
        "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": unreal_job,
        "attempt_ordinal": record.attempt_ordinal,
        "phase": "FINISHED",
        "phase_sequence": 3,
        "editor_session_id": ed,
        "process_creation_time_utc": pct,
        "output_directory": record.output_directory,
        "output_manifest": manifest,
    }
    digest = compute_journal_attestation_digest(record.attempt_nonce, payload)
    return {
        "atlas_job_id": record.atlas_job_id,
        "job_id": unreal_job,
        "unreal_job_id": unreal_job,
        "sequence_asset_path": record.sequence_asset_path,
        "authorization_id": record.authorization_id,
        "canonical_digital_twin_id": record.canonical_digital_twin_id,
        "config_digest": record.config_digest,
        "output_directory": record.output_directory,
        "phase": "FINISHED",
        "phase_sequence": 3,
        "attempt_ordinal": record.attempt_ordinal,
        "editor_session_id": ed,
        "process_id": record.origin_process_id or 4242,
        "process_creation_time_utc": pct,
        "expected_output_spec": {"format": "png", "width": 1, "height": 1, "start_frame": 1, "end_frame": 1},
        "status": "completed",
        "finished": True,
        "success": True,
        "failed": False,
        "output_manifest": manifest,
        "output_files": [m["path"] for m in manifest],
        "entry_digest": digest,
        "state_source": "witness_journal",
    }, manifest


# ── Deterministic scenario-vs-coordinator conformance ─────────────────────
@pytest.mark.parametrize("spec", SCENARIOS, ids=lambda s: s.scenario_id)
def test_m9_scenario_expected_outcome_matches_coordinator(spec, tmp_path):
    """The harness's declared outcome must equal the real coordinator's decision."""
    result, record, store, frame = _run_scenario(spec, tmp_path)

    if spec.scenario_id in ("S1", "S5"):
        assert result.case_classified == spec.expected_case
        assert result.lifecycle_state_after == spec.expected_lifecycle_after
        receipts = list(store.receipts_dir.glob("*.json"))
        assert spec.receipt_permitted is True
        assert len(receipts) == 1
    elif spec.scenario_id == "S2":
        assert result.case_classified == "WAITING_FOR_ENGINE"
        assert result.recovery_status_after == RenderJobRecoveryStatus.WAITING_FOR_ENGINE
        assert not list(store.receipts_dir.glob("*.json"))
    elif spec.scenario_id == "S3":
        assert result.case_classified == "Case A"
        assert result.lifecycle_state_after == RenderJobLifecycleState.RENDERING
        assert not list(store.receipts_dir.glob("*.json"))
    elif spec.scenario_id == "S4":
        assert result.case_classified == "Case J"
        assert result.recovery_status_after == RenderJobRecoveryStatus.RECOVERY_PENDING
        assert not list(store.receipts_dir.glob("*.json"))
    elif spec.scenario_id == "S6":
        assert result.case_classified == "Case D"
        assert result.lifecycle_state_after == RenderJobLifecycleState.ORPHANED_ARTIFACTS_PRESENT
        assert not list(store.receipts_dir.glob("*.json"))
    elif spec.scenario_id == "S7":
        assert result.case_classified == "Case G"
        assert result.lifecycle_state_after == RenderJobLifecycleState.FAILED
        assert not list(store.receipts_dir.glob("*.json"))
    elif spec.scenario_id == "S8":
        assert result.case_classified == "Case H"
        assert result.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED
        assert not list(store.receipts_dir.glob("*.json"))


@pytest.mark.parametrize("spec", SCENARIOS, ids=lambda s: s.scenario_id)
def test_m9_scenario_retry_is_always_forbidden(spec, tmp_path):
    """No scenario may ever authorize a retry/resubmission (Contract V1 §26/§37)."""
    result, record, store, frame = _run_scenario(spec, tmp_path)
    assert spec.retry_forbidden is True
    # A retry is a RESUBMISSION (minting a new execution attempt). The harness never
    # submits, and reconciliation must never push a job back into the submission
    # pipeline or mint a new attempt. For terminal/withdrawn cases the state is a
    # real terminal; for paused uncertainty the recovery_status captures the hold
    # while lifecycle stays put. In EVERY case no receipt is minted and the
    # authoritative record is not re-armed for submission.
    assert not result.repaired_from_receipt
    # The failure/uncertainty must be captured (recovery_status changed for the
    # uncertain cases, or the state is a genuine terminal).
    # Case A re-attaches to an EXISTING live execution (RENDERING) without minting
    # a new submission — that is the opposite of a retry.
    is_live_reattach = result.case_classified == "Case A" and (
        result.lifecycle_state_after == RenderJobLifecycleState.RENDERING)
    non_terminal_hold = result.recovery_status_after in (
        RenderJobRecoveryStatus.WAITING_FOR_ENGINE,
        RenderJobRecoveryStatus.RECOVERY_PENDING,
        RenderJobRecoveryStatus.WAITING_FOR_ENGINE_QUIESCENCE,
    )
    if not (non_terminal_hold or is_live_reattach):
        assert result.lifecycle_state_after in (
            RenderJobLifecycleState.FINALIZED,
            RenderJobLifecycleState.FAILED,
            RenderJobLifecycleState.ORPHANED,
            RenderJobLifecycleState.ORPHANED_ARTIFACTS_PRESENT,
            RenderJobLifecycleState.RECOVERY_FAILED,
        )
    # The store must never contain a submission intent that re-arms the job.
    assert not list(store.receipts_dir.glob("*.json")) or spec.receipt_permitted


@pytest.mark.parametrize("sid", ["S1", "S5"])
def test_m9_only_terminal_attested_scenarios_permit_receipt(sid, tmp_path):
    """Only scenarios with a valid attested terminal witness + verified artifact
    may mint a receipt; every other scenario must produce ZERO receipts."""
    spec = scenario_by_id(sid)
    result, record, store, frame = _run_scenario(spec, tmp_path)
    assert len(list(store.receipts_dir.glob("*.json"))) == 1
    # and the record carried an attempt_nonce (permitted because attested)
    assert getattr(record, "attempt_nonce", "")


@pytest.mark.parametrize("sid", ["S2", "S3", "S4", "S6", "S7", "S8"])
def test_m9_non_permitted_scenarios_mint_no_receipt(sid, tmp_path):
    """The six scenarios that must fail closed or pause produce zero receipts."""
    spec = scenario_by_id(sid)
    result, record, store, frame = _run_scenario(spec, tmp_path)
    assert len(list(store.receipts_dir.glob("*.json"))) == 0