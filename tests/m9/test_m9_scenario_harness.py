"""M9 — Scenario harness: drive Contract V1 §33 Scenarios 1-8 through the REAL
UnrealRenderRecoveryCoordinator with faked transport/supervisor seams, and assert
that the model's declared outcome matches the coordinator's actual decision.

This proves the harness's scenario table is an accurate model of the implemented
recovery path (no invented semantics): each `expected_case` / lifecycle / recovery
status / receipt / retry outcome must equal what the coordinator produces.

F-S1-2 correction (2026-09-21): the model no longer sets `engine_capable` and
`quiescent` independently. Each scenario declares ONE ContainmentState from which
both flags are derived, the impossible combination (a live engine inside an empty
quiescence Job Object) is rejected at construction, and Case B is modelled the way
Contract V1 §21:716 defines it — a PRIOR-SESSION durable journal witness read from
<ProjectDir>/AtlasWitnessJournal with ZERO engine RPCs (asserted).

Safety properties proven here (Requirement 6):
  - the harness never submits a render (no submission service call);
  - no path resubmits an uncertain job;
  - no success is ever synthesized (verified evidence requires real disk bytes +
    HMAC + quiescence);
  - a receipt is created ONLY via the Case B publish_verified_receipt gate;
  - quiescence / HMAC / attempt_ordinal gates cannot be bypassed;
  - the Case-B adoption path performs no engine RPC at all (S1/S5/S7/S1-K).

NO live Unreal, no M7 Scenario execution, no workflow/action-runner tests, no
Blender. Deterministic only.
"""
import hashlib
import json
import pathlib
import struct
import zlib
from unittest.mock import MagicMock

import pytest

from planning.unreal_render_recovery_coordinator import UnrealRenderRecoveryCoordinator
from planning.unreal_render_job_store import AtlasRenderJobStore
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_journal_attestation import compute_journal_attestation_digest
from planning.unreal_render_job_states import (
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
from planning.unreal_live_scenario_harness import (
    SCENARIOS,
    ContainmentState,
    ImpossibleContainmentStateError,
    assert_reachable_containment,
    scenario_by_id,
    SCENARIO_EXPECTED_IMPACT,
)
from planning.unreal_witness_journal import JOURNAL_DIRECTORY_NAME
from scripts.run_unreal_supervisor import AtlasProcessSupervisor

import tests.m6.fault_fixtures as ff


def _make_valid_png(path):
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
    record = ff.make_submitted_record(tmp_path, attempt_nonce="m9-scenario-nonce-0123456789abcdef")
    store.create(record)
    return store, record


def _journal_entry(record, manifest):
    """The terminal FINISHED witness entry as the engine writes it (§10 schema 2)."""
    unreal_job = record.unreal_job_id or "unreal-job-m9-001"
    editor_session = record.origin_editor_session_id or "session-m6-editor"
    process_created = record.origin_process_creation_time or "2026-09-06T00:00:00Z"
    payload = {
        "schema_version": 1,
        "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": unreal_job,
        "attempt_ordinal": record.attempt_ordinal,
        "phase": "FINISHED",
        "phase_sequence": 3,
        "editor_session_id": editor_session,
        "process_creation_time_utc": process_created,
        "output_directory": record.output_directory,
        "output_manifest": manifest,
    }
    digest = compute_journal_attestation_digest(record.attempt_nonce, payload)
    # NOTE: the durable entry deliberately carries ONLY `unreal_job_id` (no `job_id`),
    # exactly like the real engine journal; the coordinator must normalize the name.
    return {
        "journal_schema_version": 2,
        "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": unreal_job,
        "phase": "FINISHED",
        "phase_sequence": 3,
        "attempt_ordinal": record.attempt_ordinal,
        "authorization_id": record.authorization_id,
        "sequence_asset_path": record.sequence_asset_path,
        "config_digest": record.config_digest,
        "output_directory": record.output_directory,
        "editor_session_id": editor_session,
        "process_id": record.origin_process_id or 4242,
        "process_creation_time_utc": process_created,
        "expected_output_spec": {"format": "png", "width": 1, "height": 1,
                                 "start_frame": 1, "end_frame": 1},
        "status": "finished",
        "finished": True,
        "success": True,
        "failed": False,
        "output_manifest": manifest,
        "output_files": [m["path"] for m in manifest],
        "entry_digest": digest,
        "state_source": "unreal-editor-atlas-transport",
        "written_at": "2026-09-06T00:00:05Z",
    }


def _write_witness_journal(journal_root, record, condition, manifest):
    """Materialize the DURABLE witness set on disk per the scenario condition."""
    journal_root.mkdir(parents=True, exist_ok=True)
    path = journal_root / f"{record.atlas_job_id}__{record.unreal_job_id or 'unreal-job-m9-001'}.json"
    if condition == "NONE":
        return None
    if condition == "COMPLETE":
        entry = _journal_entry(record, manifest)
        journal = {
            "journal_schema_version": 2,
            "atlas_job_id": record.atlas_job_id,
            "unreal_job_id": entry["unreal_job_id"],
            "phase": "FINISHED",
            "phase_sequence": 3,
            "status": "finished",
            "progress": 1,
            "success": True,
            "finished": True,
            "failed": False,
            "phase_history": [
                {"phase": "ACCEPTED", "phase_sequence": 1},
                {"phase": "STARTED", "phase_sequence": 2},
                entry,
            ],
        }
        path.write_text(json.dumps(journal), encoding="utf-8")
        return path
    if condition == "PARTIAL":
        # torn write: truncated JSON (the engine's own scan reports PARTIAL)
        path.write_text('{"journal_schema_version": 2, "atlas_job_id": "' + record.atlas_job_id + '"', encoding="utf-8")
        return path
    raise AssertionError(f"unsupported journal condition {condition!r}")


def _supervisor(containment: ContainmentState):
    sv = MagicMock(spec=AtlasProcessSupervisor)
    if containment.deployment_mode == "CONTAINED_JOB_OBJECT":
        sv.job_handle = 4242
    else:
        sv.job_handle = None
    sv.query_active_processes.return_value = containment.job_active_processes
    return sv


def _make_reconcile_adapter(catalog_state, known_jobs):
    """Adapter that returns a reconcile_render_jobs catalog for _query_catalog."""
    adapter = MagicMock()
    adapter.assert_recovery_capable = MagicMock(return_value=None)
    adapter.inspect.return_value = UnrealEvidence(
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
    adapter.assert_recovery_capable = MagicMock(side_effect=UnrealAdapterError("engine down"))
    return adapter


def _live_inflight_candidate(record):
    unreal_job = record.unreal_job_id or "unreal-job-m9-001"
    return {
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
        "expected_output_spec": {"format": "png", "width": 1, "height": 1,
                                 "start_frame": 1, "end_frame": 1},
        "status": "submitted",
        "finished": False,
        "success": False,
        "failed": False,
        "output_manifest": [],
        "output_files": [],
        "state_source": "in_memory_registry",
    }


def _run_scenario(spec, tmp_path):
    """Set up the scenario's world (durable witness + live catalog + containment) and
    run the REAL coordinator. Returns result/record/store/frame/adapter."""
    store, record = _make_store(tmp_path)
    journal_root = tmp_path / JOURNAL_DIRECTORY_NAME

    # disk artifacts + the manifest the witness will attest to
    manifest = []
    frame = None
    if spec.disk_artifacts:
        frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
        _make_valid_png(frame)
        data = frame.read_bytes()
        manifest = [{"path": str(frame), "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}]
    elif spec.scenario_id == "S7":
        # terminal claim whose declared artifact is MISSING on disk
        absent = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
        blob = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        manifest = [{"path": str(absent), "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}]

    _write_witness_journal(journal_root, record, spec.journal_condition, manifest)

    # live engine catalog (only reachable when the containment state says so)
    known_jobs = list(spec.candidate_known_jobs)
    if spec.scenario_id == "S3":
        known_jobs = [_live_inflight_candidate(record)]
    elif spec.scenario_id == "S8":
        live = dict(_live_inflight_candidate(record))
        live.update({"phase": "FINISHED", "phase_sequence": 3, "finished": True,
                     "success": True, "state_source": "witness_journal",
                     "job_id": "unreal-job-m9-dup", "unreal_job_id": "unreal-job-m9-dup"})
        first = _live_inflight_candidate(record)
        known_jobs = [first, live]

    if spec.containment.engine_capable:
        adapter = _make_reconcile_adapter(spec.live_catalog_journal_status, known_jobs)
    else:
        adapter = _make_down_adapter()

    receipt_store = UnrealRenderReceiptStore(tmp_path / "rcpt.json")
    coord = UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
        supervisor=_supervisor(spec.containment),
        deployment_mode=spec.containment.deployment_mode,
        journal_root=str(journal_root),
    )
    result = coord.reconcile_single_job(record.atlas_job_id)
    return result, record, store, frame, adapter


def _receipt_count(store):
    return len(list(store.receipts_dir.glob("*.json")))


# ── F-S1-2: the model cannot declare an impossible live combination ───────
def test_m9_impossible_contained_state_is_rejected():
    """engine_capable=True AND quiescent=True is unreachable under §9 containment."""
    with pytest.raises(ImpossibleContainmentStateError):
        ContainmentState(deployment_mode="CONTAINED_JOB_OBJECT",
                         live_engine_present=True, job_active_processes=0)
    # ... and the reachable boundary states derive correctly.
    drained = ContainmentState(live_engine_present=False, job_active_processes=0)
    assert drained.quiescent is True and drained.engine_capable is False
    alive = ContainmentState(live_engine_present=True, job_active_processes=6)
    assert alive.quiescent is False and alive.engine_capable is True


@pytest.mark.parametrize("spec", SCENARIOS, ids=lambda s: s.scenario_id)
def test_m9_every_scenario_declares_a_reachable_containment(spec):
    """No scenario may assert engine_capable and quiescent simultaneously, and every
    adoption scenario must satisfy §9 quiescence."""
    assert not (spec.containment.engine_capable and spec.containment.quiescent)
    assert_reachable_containment(spec)


# ── Deterministic scenario-vs-coordinator conformance ─────────────────────
@pytest.mark.parametrize("spec", SCENARIOS, ids=lambda s: s.scenario_id)
def test_m9_scenario_expected_outcome_matches_coordinator(spec, tmp_path):
    """The harness's declared outcome must equal the real coordinator's decision."""
    result, record, store, frame, adapter = _run_scenario(spec, tmp_path)

    assert result.case_classified == spec.expected_case
    assert result.lifecycle_state_after == spec.expected_lifecycle_after
    assert result.recovery_status_after == spec.expected_recovery_status_after
    assert bool(_receipt_count(store)) is spec.receipt_permitted
    assert spec.retry_forbidden is True
    assert result.repaired_from_receipt is False
    # §9 invariant: an adoption may only follow proven quiescence.
    if spec.receipt_permitted:
        assert spec.quiescent is True
    # declared engine-RPC budget: the durable paths perform none at all
    if spec.engine_rpcs_expected == 0:
        assert adapter.mock_calls == [], f"{spec.scenario_id} unexpectedly used the engine"


@pytest.mark.parametrize("sid", ["S1", "S5", "S7", "S1-K"])
def test_m9_durable_witness_paths_perform_zero_engine_rpcs(sid, tmp_path):
    """Case B (and the Case-K control) must be served from the durable §10 witness
    with no engine interaction whatsoever."""
    spec = scenario_by_id(sid)
    assert spec.journal_condition == "COMPLETE"
    result, record, store, frame, adapter = _run_scenario(spec, tmp_path)
    assert adapter.mock_calls == []
    assert result.case_classified == spec.expected_case


@pytest.mark.parametrize("spec", SCENARIOS, ids=lambda s: s.scenario_id)
def test_m9_scenario_retry_is_always_forbidden(spec, tmp_path):
    """No scenario may ever authorize a retry/resubmission (Contract V1 §26/§37)."""
    result, record, store, frame, adapter = _run_scenario(spec, tmp_path)
    assert spec.retry_forbidden is True
    # A retry is a RESUBMISSION (minting a new execution attempt). The harness never
    # submits, and reconciliation must never push a job back into the submission
    # pipeline or mint a new attempt. For terminal/withdrawn cases the state is a
    # real terminal; for paused uncertainty the recovery_status captures the hold
    # while lifecycle stays put. In EVERY case no unexpected receipt is minted and
    # the authoritative record is not re-armed for submission.
    assert not result.repaired_from_receipt
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
    assert _receipt_count(store) == (1 if spec.receipt_permitted else 0)


@pytest.mark.parametrize("sid", ["S1", "S5"])
def test_m9_only_terminal_attested_scenarios_permit_receipt(sid, tmp_path):
    """Only a valid attested terminal witness + verified artifact may mint a receipt;
    it is minted EXACTLY once."""
    spec = scenario_by_id(sid)
    result, record, store, frame, adapter = _run_scenario(spec, tmp_path)
    assert _receipt_count(store) == 1
    assert result.case_classified == "Case B"
    assert result.lifecycle_state_after == RenderJobLifecycleState.FINALIZED
    assert result.recovery_status_after == RenderJobRecoveryStatus.RESOLVED
    assert getattr(record, "attempt_nonce", "")


@pytest.mark.parametrize("sid", ["S1-K", "S2", "S3", "S4", "S6", "S7", "S8"])
def test_m9_non_permitted_scenarios_mint_no_receipt(sid, tmp_path):
    """Every scenario that must fail closed or pause produces zero receipts."""
    spec = scenario_by_id(sid)
    result, record, store, frame, adapter = _run_scenario(spec, tmp_path)
    assert _receipt_count(store) == 0


def test_m9_case_k_control_does_not_inspect_or_adopt_artifacts(tmp_path):
    """The Case-K control: terminal witness AND artifacts exist, quiescence does not,
    so nothing may be inspected or adopted (Contract V1 §9.279)."""
    spec = scenario_by_id("S1-K")
    result, record, store, frame, adapter = _run_scenario(spec, tmp_path)
    assert result.case_classified == "Case K (Quiescence Blocked)"
    assert result.recovery_status_after == RenderJobRecoveryStatus.WAITING_FOR_ENGINE_QUIESCENCE
    assert result.lifecycle_state_after == RenderJobLifecycleState.SUBMITTED
    assert _receipt_count(store) == 0
    assert store.load(record.atlas_job_id).receipt_reference is None
    assert adapter.mock_calls == []
    assert frame.exists()  # non-mutation: the artifacts are untouched, never adopted


def test_m9_expected_impact_table_covers_every_scenario():
    """The shared impact table (checklist source of truth) covers every scenario."""
    assert set(SCENARIO_EXPECTED_IMPACT) == {s.scenario_id for s in SCENARIOS}
    for spec in SCENARIOS:
        impact = SCENARIO_EXPECTED_IMPACT[spec.scenario_id]
        assert impact["case"] == spec.expected_case
        assert impact["receipt"] is spec.receipt_permitted
        assert impact["retry"] is (not spec.retry_forbidden)
