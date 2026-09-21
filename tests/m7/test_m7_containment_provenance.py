"""F-DG-1 — §9 quiescence with launch-object provenance (and MF-4 negative controls).

The decisive evidence in this file is a *failing control*: a fresh, never-used Job Object
reports ``ActiveProcesses == 0`` and therefore satisfies the attempt-UNBOUND predicate
(``scripts/run_unreal_supervisor.py::evaluate_process_quiescence``) — while it has no
relationship to the render. The provenance-bound predicate must refuse it, so a terminal
journal plus verified artifacts can never be adopted on the strength of an object that
contained nothing.

No Unreal, no render, no Blender: deterministic fakes plus one real-kernel file
(``test_m7_win32_containment_kernel.py``).
"""
from __future__ import annotations

import pathlib

from unittest.mock import MagicMock

import tests.m6.fault_fixtures as ff
from planning.unreal_containment_launch_record import (
    build_launch_record,
    containment_dir_for_store,
)
from planning.unreal_containment_quiescence import (
    KERNEL_EVIDENCE_PREFIX,
    NO_LAUNCH_PROVENANCE_PREFIX,
    evaluate_containment_quiescence,
)
from planning.unreal_render_job_states import (
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_recovery_coordinator import UnrealRenderRecoveryCoordinator
from scripts.run_unreal_supervisor import (
    AtlasProcessSupervisor,
    JobObjectContainmentState,
    evaluate_process_quiescence,
)

import tests.m9.test_m9_durable_witness_adoption as m9

JOURNAL_DIRECTORY_NAME = m9.JOURNAL_DIRECTORY_NAME


def _store_and_record(tmp_path):
    store = ff.make_store(tmp_path)
    record = ff.make_submitted_record(tmp_path)
    store.create(record)
    ff.write_launch_record_for(store, record)
    return store, record


def _launch_record(record, **overrides):
    return ff.make_launch_record(record, **overrides)


# ── positive case: the attempt's OWN drained launch object ────────────────
def test_attempts_own_drained_launch_object_satisfies_the_predicate(tmp_path):
    _, record = _store_and_record(tmp_path)
    result = evaluate_containment_quiescence(
        ff.contained_supervisor(active=0),
        "CONTAINED_JOB_OBJECT",
        launch_record=_launch_record(record),
        job_record=record,
    )
    assert result.is_quiescent is True
    assert result.provenance_verified is True
    assert result.active_process_count == 0
    assert result.total_processes >= 1
    assert result.kill_on_job_close is True
    assert result.breakaway_disabled is True
    assert result.launch_record_digest == _launch_record(record).launch_record_digest
    # the evidence surface carries the §9 kernel facts
    assert result.evidence()["kernel_total_processes"] >= 1


# ── MF-4 control 1 (MANDATORY, must FAIL): fresh empty Job Object ─────────
def test_control_1_fresh_empty_job_object_is_refused_at_zero_active(tmp_path):
    """DECIDING CONTROL: ActiveProcesses == 0 is NOT sufficient without provenance."""
    _, record = _store_and_record(tmp_path)
    fresh_object = ff.contained_supervisor(active=0, total_processes=0)

    bound = evaluate_containment_quiescence(
        fresh_object,
        "CONTAINED_JOB_OBJECT",
        launch_record=_launch_record(record),
        job_record=record,
    )
    assert bound.is_quiescent is False
    assert bound.provenance_verified is False
    assert bound.reason.startswith(KERNEL_EVIDENCE_PREFIX)
    assert "TotalProcesses=0" in bound.reason

    # ... and the legacy attempt-unbound predicate ACCEPTS the same object, which is
    # exactly the F-DG-1 vacuity hole this rung closes.
    legacy = evaluate_process_quiescence(fresh_object, "CONTAINED_JOB_OBJECT")
    assert legacy.is_quiescent is True
    assert legacy.active_process_count == 0


def test_control_1b_fresh_empty_job_object_without_any_launch_record_is_refused(tmp_path):
    _, record = _store_and_record(tmp_path)
    result = evaluate_containment_quiescence(
        ff.contained_supervisor(active=0, total_processes=0),
        "CONTAINED_JOB_OBJECT",
        job_record=record,
    )
    assert result.is_quiescent is False
    assert result.reason.startswith(NO_LAUNCH_PROVENANCE_PREFIX)


# ── MF-4 control 2: wrong Job Object (someone else's launch record) ────────
def test_control_2_wrong_job_object_provenance_is_refused(tmp_path):
    store, record = _store_and_record(tmp_path)
    other = ff.make_submitted_record(tmp_path / "other", atlas_job_id="atlas-render-job-11111111-2222-3333-4444-555555555555")
    forged = build_launch_record(
        atlas_job_id=other.atlas_job_id,
        attempt_ordinal=other.attempt_ordinal,
        attempt_nonce=record.attempt_nonce,
        engine_pid=1,
        process_creation_time_utc="2026-09-06T00:00:00+00:00",
        launch_composition_processes=1,
        project_identity=ff.TEST_PROJECT_IDENTITY,
        uproject_digest=ff.TEST_UPROJECT_DIGEST,
        keeper_identity="forged",
        job_identity_descriptor="OtherJob",
    )
    result = evaluate_containment_quiescence(
        ff.contained_supervisor(active=0),
        "CONTAINED_JOB_OBJECT",
        launch_record=forged,
        job_record=record,
    )
    assert result.is_quiescent is False
    assert "atlas_job_id" in result.reason


# ── MF-4 control 3: stale/duplicate provenance (wrong attempt ordinal) ────
def test_control_3_stale_launch_record_ordinal_is_refused(tmp_path):
    store, record = _store_and_record(tmp_path)
    stale = build_launch_record(
        atlas_job_id=record.atlas_job_id,
        attempt_ordinal=record.attempt_ordinal + 1,
        attempt_nonce=record.attempt_nonce,
        engine_pid=4242,
        process_creation_time_utc="2026-09-06T00:00:00+00:00",
        launch_composition_processes=1,
        project_identity=ff.TEST_PROJECT_IDENTITY,
        uproject_digest=ff.TEST_UPROJECT_DIGEST,
        keeper_identity="stale-keeper",
        job_identity_descriptor="StaleJob",
    )
    result = evaluate_containment_quiescence(
        ff.contained_supervisor(active=0),
        "CONTAINED_JOB_OBJECT",
        launch_record=stale,
        job_record=record,
    )
    assert result.is_quiescent is False
    assert "attempt_ordinal" in result.reason


# ── MF-4 control 10: tampered launch record ───────────────────────────────
def test_control_10_tampered_launch_record_is_refused(tmp_path):
    _, record = _store_and_record(tmp_path)
    good = _launch_record(record)
    tampered = build_launch_record(
        atlas_job_id=record.atlas_job_id,
        attempt_ordinal=record.attempt_ordinal,
        attempt_nonce="a-different-nonce-entirely",
        engine_pid=4242,
        process_creation_time_utc="2026-09-06T00:00:00+00:00",
        launch_composition_processes=1,
        project_identity=ff.TEST_PROJECT_IDENTITY,
        uproject_digest=ff.TEST_UPROJECT_DIGEST,
        keeper_identity="attacker",
        job_identity_descriptor="AttackerJob",
    )
    assert good.launch_record_digest != tampered.launch_record_digest

    result = evaluate_containment_quiescence(
        ff.contained_supervisor(active=0),
        "CONTAINED_JOB_OBJECT",
        launch_record=tampered,
        job_record=record,
    )
    assert result.is_quiescent is False
    assert "HMAC authentication failed" in result.reason


# ── MF-4 control 11: invalid nonce provenance ────────────────────────────
def test_control_11_invalid_nonce_provenance_is_refused(tmp_path):
    _, record = _store_and_record(tmp_path)
    # A durable record whose attempt has no persisted nonce cannot authenticate anything.
    record_without_nonce = ff.make_submitted_record(tmp_path / "no_nonce", attempt_nonce=None)
    assert record_without_nonce.attempt_nonce is None
    result = evaluate_containment_quiescence(
        ff.contained_supervisor(active=0),
        "CONTAINED_JOB_OBJECT",
        launch_record=_launch_record(record),
        job_record=record_without_nonce,
    )
    assert result.is_quiescent is False
    assert "attempt_nonce" in result.reason


# ── MF-4 control 12 / 13: ActiveProcesses > 0 vs == 0 ────────────────────
def test_control_12_positive_active_processes_is_not_quiescent(tmp_path):
    _, record = _store_and_record(tmp_path)
    result = evaluate_containment_quiescence(
        ff.contained_supervisor(active=6),
        "CONTAINED_JOB_OBJECT",
        launch_record=_launch_record(record),
        job_record=record,
    )
    assert result.is_quiescent is False
    assert result.active_process_count == 6
    assert "6 active processes" in result.reason


def test_control_13_zero_active_processes_is_quiescent(tmp_path):
    _, record = _store_and_record(tmp_path)
    result = evaluate_containment_quiescence(
        ff.contained_supervisor(active=0, total_processes=9),
        "CONTAINED_JOB_OBJECT",
        launch_record=_launch_record(record, launch_composition_processes=9),
        job_record=record,
    )
    assert result.is_quiescent is True
    assert result.total_processes == 9


# ── MF-4 control 14: KILL_ON_JOB_CLOSE / breakaway configuration ──────────
def test_control_14_missing_kill_on_job_close_is_refused(tmp_path):
    _, record = _store_and_record(tmp_path)
    result = evaluate_containment_quiescence(
        ff.contained_supervisor(active=0, kill_on_job_close=False),
        "CONTAINED_JOB_OBJECT",
        launch_record=_launch_record(record),
        job_record=record,
    )
    assert result.is_quiescent is False
    assert "KILL_ON_JOB_CLOSE is not configured" in result.reason


def test_control_14b_enabled_breakaway_is_refused(tmp_path):
    _, record = _store_and_record(tmp_path)
    result = evaluate_containment_quiescence(
        ff.contained_supervisor(active=0, breakaway_disabled=False),
        "CONTAINED_JOB_OBJECT",
        launch_record=_launch_record(record),
        job_record=record,
    )
    assert result.is_quiescent is False
    assert "breakaway is enabled" in result.reason


def test_control_14c_kernel_total_below_recorded_composition_is_refused(tmp_path):
    _, record = _store_and_record(tmp_path)
    result = evaluate_containment_quiescence(
        ff.contained_supervisor(active=0, total_processes=1),
        "CONTAINED_JOB_OBJECT",
        launch_record=_launch_record(record, launch_composition_processes=5),
        job_record=record,
    )
    assert result.is_quiescent is False
    assert "below the recorded" in result.reason


# ── MF-4 control 16: handle loss / no real kernel surface ────────────────
def test_control_16_missing_handle_is_not_quiescent(tmp_path):
    _, record = _store_and_record(tmp_path)
    result = evaluate_containment_quiescence(
        ff.contained_supervisor(active=0, job_handle=None),
        "CONTAINED_JOB_OBJECT",
        launch_record=_launch_record(record),
        job_record=record,
    )
    assert result.is_quiescent is False
    assert "missing/invalid" in result.reason


def test_control_16b_supervisor_without_a_real_kernel_surface_is_refused(tmp_path):
    """A bare mock that only fakes ``ActiveProcesses == 0`` cannot satisfy §9."""
    _, record = _store_and_record(tmp_path)
    bare = MagicMock(spec=AtlasProcessSupervisor)
    bare.job_handle = 4321
    bare.query_active_processes.return_value = 0
    result = evaluate_containment_quiescence(
        bare,
        "CONTAINED_JOB_OBJECT",
        launch_record=_launch_record(record),
        job_record=record,
    )
    assert result.is_quiescent is False
    assert result.reason.startswith(KERNEL_EVIDENCE_PREFIX)


def test_kernel_query_failure_fails_closed(tmp_path):
    _, record = _store_and_record(tmp_path)
    broken = MagicMock(spec=AtlasProcessSupervisor)
    broken.job_handle = 4321
    broken.query_containment_state.side_effect = RuntimeError("handle closed")
    result = evaluate_containment_quiescence(
        broken,
        "CONTAINED_JOB_OBJECT",
        launch_record=_launch_record(record),
        job_record=record,
    )
    assert result.is_quiescent is False
    assert "query failed" in result.reason


# ── mode table (unchanged fail-closed semantics) ─────────────────────────
def test_uncontained_attached_never_quiescent_and_reason_matches_legacy(tmp_path):
    _, record = _store_and_record(tmp_path)
    bound = evaluate_containment_quiescence(
        None,
        "UNCONTAINED_ATTACHED",
        launch_record=_launch_record(record),
        job_record=record,
    )
    legacy = evaluate_process_quiescence(None, "UNCONTAINED_ATTACHED")
    assert bound.is_quiescent is False
    assert bound.reason == legacy.reason
    assert bound.deployment_mode == "UNCONTAINED_ATTACHED"


def test_unknown_deployment_mode_is_refused(tmp_path):
    _, record = _store_and_record(tmp_path)
    result = evaluate_containment_quiescence(
        ff.contained_supervisor(active=0), "SOMETHING_ELSE", job_record=record
    )
    assert result.is_quiescent is False
    assert "Unknown deployment mode" in result.reason


def test_durable_resolution_path_matches_in_process_supply(tmp_path):
    """Resolving the record from the store must give the same verdict as supplying it."""
    store, record = _store_and_record(tmp_path)
    from_store = evaluate_containment_quiescence(
        ff.contained_supervisor(active=0),
        "CONTAINED_JOB_OBJECT",
        job_record=record,
        containment_dir=str(containment_dir_for_store(store.root)),
    )
    in_process = evaluate_containment_quiescence(
        ff.contained_supervisor(active=0),
        "CONTAINED_JOB_OBJECT",
        launch_record=_launch_record(record),
        job_record=record,
    )
    assert from_store.is_quiescent is True
    assert in_process.is_quiescent is True
    assert from_store.launch_record_digest == in_process.launch_record_digest


def test_absent_launch_record_in_the_store_is_refused_not_ignored(tmp_path):
    store = ff.make_store(tmp_path)
    record = ff.make_submitted_record(tmp_path)
    store.create(record)  # record exists, but no launch record was ever written
    result = evaluate_containment_quiescence(
        ff.contained_supervisor(active=0),
        "CONTAINED_JOB_OBJECT",
        job_record=record,
        containment_dir=str(containment_dir_for_store(store.root)),
    )
    assert result.is_quiescent is False
    assert result.reason.startswith(NO_LAUNCH_PROVENANCE_PREFIX)
    assert "no containment launch record exists" in result.reason


# ── coordinator level: the task's mandated control ───────────────────────
def _durable_witness_setup(tmp_path):
    """Store + submitted record + terminal attested journal + valid artifacts on disk."""
    store = ff.make_store(tmp_path)
    record = ff.make_submitted_record(tmp_path)
    store.create(record)
    ff.write_launch_record_for(store, record)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    m9._make_valid_png(frame)
    manifest = m9._manifest_for(frame)
    journal_root = tmp_path / JOURNAL_DIRECTORY_NAME
    m9._write_journal(journal_root, record, m9._entry(record, manifest))
    return store, record, frame, journal_root


def _coordinator(store, record, tmp_path, journal_root, supervisor):
    return UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=m9._RecordingAdapter(capable=False),  # engine DOWN: must not matter
        receipt_store=UnrealRenderReceiptStore(tmp_path / "rcpt.json"),
        supervisor=supervisor,
        deployment_mode="CONTAINED_JOB_OBJECT",
        journal_root=str(journal_root),
    )


def test_mandated_control_fresh_empty_object_with_existing_render_record_is_not_quiescent(tmp_path):
    """fresh empty Job Object + existing render record -> NOT QUIESCENT FOR THIS EXECUTION.

    A terminal attested witness and byte-valid artifacts are on disk; the only thing wrong
    is that the offered Job Object never contained this attempt's tree. Recovery MUST hold
    (Case K), inspect nothing further, mint no receipt, and leave artifacts untouched.
    """
    store, record, frame, journal_root = _durable_witness_setup(tmp_path)
    before = frame.read_bytes()
    fresh_object = ff.contained_supervisor(active=0, total_processes=0)

    result = _coordinator(store, record, tmp_path, journal_root, fresh_object).reconcile_single_job(
        record.atlas_job_id
    )

    assert result.case_classified == "Case K (Quiescence Blocked)"
    assert result.recovery_status_after == RenderJobRecoveryStatus.WAITING_FOR_ENGINE_QUIESCENCE
    assert result.lifecycle_state_after == RenderJobLifecycleState.SUBMITTED
    assert list(store.receipts_dir.glob("*.json")) == []
    assert store.load(record.atlas_job_id).receipt_reference is None
    assert frame.read_bytes() == before  # artifacts untouched


def test_twin_positive_attempts_own_launch_object_adopts_case_b(tmp_path):
    """The ONLY difference from the control above is whose Job Object is offered."""
    store, record, frame, journal_root = _durable_witness_setup(tmp_path)
    launch = ff.make_launch_record(record)
    own_object = ff.contained_supervisor(
        active=0, total_processes=launch.launch_composition_processes
    )

    result = _coordinator(store, record, tmp_path, journal_root, own_object).reconcile_single_job(
        record.atlas_job_id
    )

    assert result.case_classified == "Case B"
    assert result.lifecycle_state_after == RenderJobLifecycleState.FINALIZED
    receipts = sorted(store.receipts_dir.glob("*.json"))
    assert len(receipts) == 1
    assert UnrealRenderReceiptStore(receipts[0]).load().atlas_job_id == record.atlas_job_id


# ── MF-4 controls 6 & 7: mismatched keeper -> Unreal job / wrong incarnation ─
def _incarnation_candidate(record, frame, *, process_id=None, creation_time=None):
    """An AUTHENTICATED terminal witness naming a chosen engine incarnation."""
    from planning.unreal_journal_attestation import compute_journal_attestation_digest

    manifest = m9._manifest_for(frame)
    payload = {
        "schema_version": 1,
        "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": record.unreal_job_id,
        "attempt_ordinal": record.attempt_ordinal,
        "phase": "FINISHED",
        "phase_sequence": 3,
        "editor_session_id": record.origin_editor_session_id,
        "process_creation_time_utc": creation_time or record.origin_process_creation_time,
        "output_directory": record.output_directory,
        "output_manifest": manifest,
    }
    entry = dict(m9._entry(record, manifest))
    # This candidate models a LIVE catalog entry (the engine names the field `job_id`),
    # unlike a durable journal entry which carries `unreal_job_id`.
    entry["job_id"] = record.unreal_job_id
    entry["process_creation_time_utc"] = payload["process_creation_time_utc"]
    entry["process_id"] = process_id if process_id is not None else record.origin_process_id
    entry["entry_digest"] = compute_journal_attestation_digest(record.attempt_nonce, payload)
    return entry


def _incarnation_setup(tmp_path):
    store = ff.make_store(tmp_path)
    record = ff.make_submitted_record(tmp_path)
    store.create(record)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    m9._make_valid_png(frame)
    return store, record, frame


def _reconcile_with_candidate(store, record, frame, candidate, tmp_path):
    launch = ff.make_launch_record(record)
    adapter = m9._RecordingAdapter(journal_status="COMPLETE", known_jobs=[candidate])
    coord = UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter,
        receipt_store=UnrealRenderReceiptStore(tmp_path / "rcpt.json"),
        supervisor=ff.contained_supervisor(active=0),
        deployment_mode="CONTAINED_JOB_OBJECT",
        containment_launch_record=launch,
    )
    before = frame.read_bytes()
    return coord.reconcile_single_job(record.atlas_job_id), before


def test_control_6_mismatched_keeper_to_unreal_job_is_refused(tmp_path):
    """The launch object contained engine pid A; the witness names engine pid B."""
    store, record, frame = _incarnation_setup(tmp_path)
    candidate = _incarnation_candidate(record, frame, process_id=record.origin_process_id + 77)

    result, before = _reconcile_with_candidate(store, record, frame, candidate, tmp_path)

    assert result.case_classified != "Case B"
    assert result.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED
    assert "did not contain this execution" in (result.failure_reason or "")
    assert list(store.receipts_dir.glob("*.json")) == []
    assert frame.read_bytes() == before


def test_control_7_wrong_process_creation_time_is_refused(tmp_path):
    store, record, frame = _incarnation_setup(tmp_path)
    candidate = _incarnation_candidate(record, frame, creation_time="2020-01-01T00:00:00+00:00")

    result, before = _reconcile_with_candidate(store, record, frame, candidate, tmp_path)

    assert result.case_classified != "Case B"
    assert result.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED
    assert "different process incarnation" in (result.failure_reason or "")
    assert list(store.receipts_dir.glob("*.json")) == []


def test_matching_engine_incarnation_still_adopts(tmp_path):
    """Positive control for controls 6/7: agreement cannot block a sound adoption."""
    store, record, frame = _incarnation_setup(tmp_path)
    candidate = _incarnation_candidate(record, frame)

    result, _ = _reconcile_with_candidate(store, record, frame, candidate, tmp_path)

    assert result.case_classified == "Case B"
    assert result.lifecycle_state_after == RenderJobLifecycleState.FINALIZED
    assert len(list(store.receipts_dir.glob("*.json"))) == 1


# ── fail-closed semantics that must never be converted to success ─────────
def test_no_durable_attestation_can_substitute_for_the_live_object(tmp_path):
    """OS reboot / handle loss: a stored claim is never a quiescence proof.

    The predicate accepts no attestation, no persisted counter and no recorded verdict —
    only the live retained handle's kernel state plus the attempt's launch record.
    """
    import inspect

    from planning.unreal_containment_quiescence import evaluate_containment_quiescence as predicate

    parameters = set(inspect.signature(predicate).parameters)
    assert parameters == {
        "supervisor",
        "deployment_mode",
        "launch_record",
        "job_record",
        "containment_dir",
    }
    for forbidden in ("attestation", "attest", "quiescence_record", "recorded_state", "evidence"):
        assert forbidden not in parameters

    # And a plausible-looking stored claim changes nothing for a handle-less source.
    store, record = _store_and_record(tmp_path)
    claim = containment_dir_for_store(store.root) / "quiescence_claim.json"
    claim.parent.mkdir(parents=True, exist_ok=True)
    claim.write_text('{"active_processes": 0, "proven": true}', encoding="utf-8")
    result = evaluate_containment_quiescence(
        ff.contained_supervisor(job_handle=None), "CONTAINED_JOB_OBJECT", job_record=record
    )
    assert result.is_quiescent is False

# ── red-team cleanup item 2: the containment_dir construction path ────────
def _write_witness_with_incarnation(journal_root, record, frame, *, process_id=None,
                                    creation_time=None):
    """Terminal attested journal naming a CHOSEN engine incarnation (re-signed payload)."""
    from planning.unreal_journal_attestation import compute_journal_attestation_digest

    manifest = m9._manifest_for(frame)
    payload = {
        "schema_version": 1,
        "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": record.unreal_job_id,
        "attempt_ordinal": record.attempt_ordinal,
        "phase": "FINISHED",
        "phase_sequence": 3,
        "editor_session_id": record.origin_editor_session_id,
        "process_creation_time_utc": creation_time or record.origin_process_creation_time,
        "output_directory": record.output_directory,
        "output_manifest": manifest,
    }
    entry = dict(m9._entry(record, manifest))
    entry["process_creation_time_utc"] = payload["process_creation_time_utc"]
    entry["process_id"] = process_id if process_id is not None else record.origin_process_id
    entry["entry_digest"] = compute_journal_attestation_digest(record.attempt_nonce, payload)
    return m9._write_journal(journal_root, record, entry)


def _containment_dir_coordinator(store, tmp_path, journal_root):
    """Built the review's other way: launch record NOT supplied, containment_dir is."""
    return UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=m9._RecordingAdapter(capable=False),
        receipt_store=UnrealRenderReceiptStore(tmp_path / "rcpt.json"),
        supervisor=ff.contained_supervisor(active=0),
        deployment_mode="CONTAINED_JOB_OBJECT",
        journal_root=str(journal_root),
        containment_dir=str(containment_dir_for_store(store.root)),
    )


def _durable_setup(tmp_path, frame, journal_root):
    store = ff.make_store(tmp_path)
    record = ff.make_submitted_record(tmp_path)
    store.create(record)
    ff.write_launch_record_for(store, record)
    if frame is True:
        frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
        m9._make_valid_png(frame)
    return store, record, frame, journal_root


def test_containment_dir_path_resolves_the_record_and_adopts_case_b(tmp_path):
    journal_root = tmp_path / JOURNAL_DIRECTORY_NAME
    store = ff.make_store(tmp_path)
    record = ff.make_submitted_record(tmp_path)
    store.create(record)
    ff.write_launch_record_for(store, record)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    m9._make_valid_png(frame)
    m9._write_journal(journal_root, record, m9._entry(record, m9._manifest_for(frame)))

    coord = _containment_dir_coordinator(store, tmp_path, journal_root)
    result = coord.reconcile_single_job(record.atlas_job_id)

    assert result.case_classified == "Case B"
    assert len(list(store.receipts_dir.glob("*.json"))) == 1


def test_containment_dir_path_refuses_a_mismatched_engine_pid(tmp_path):
    """Regression: the check must RUN on this path, not be skipped for lack of an object."""
    journal_root = tmp_path / JOURNAL_DIRECTORY_NAME
    store = ff.make_store(tmp_path)
    record = ff.make_submitted_record(tmp_path)
    store.create(record)
    ff.write_launch_record_for(store, record)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    m9._make_valid_png(frame)
    _write_witness_with_incarnation(
        journal_root, record, frame, process_id=record.origin_process_id + 99
    )
    before = frame.read_bytes()

    coord = _containment_dir_coordinator(store, tmp_path, journal_root)
    result = coord.reconcile_single_job(record.atlas_job_id)

    assert result.case_classified == "Case E/F"
    assert result.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED
    assert "did not contain this execution" in (result.failure_reason or "")
    assert list(store.receipts_dir.glob("*.json")) == []
    assert frame.read_bytes() == before


def test_containment_dir_path_refuses_a_mismatched_process_creation_time(tmp_path):
    journal_root = tmp_path / JOURNAL_DIRECTORY_NAME
    store = ff.make_store(tmp_path)
    record = ff.make_submitted_record(tmp_path)
    store.create(record)
    ff.write_launch_record_for(store, record)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    m9._make_valid_png(frame)
    _write_witness_with_incarnation(
        journal_root, record, frame, creation_time="2019-01-01T00:00:00+00:00"
    )

    coord = _containment_dir_coordinator(store, tmp_path, journal_root)
    result = coord.reconcile_single_job(record.atlas_job_id)

    assert result.case_classified == "Case E/F"
    assert result.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED
    assert "different process incarnation" in (result.failure_reason or "")
    assert list(store.receipts_dir.glob("*.json")) == []


def test_containment_dir_path_without_a_launch_record_still_fails_closed(tmp_path):
    """No launch record on disk => no provenance => Case K hold, never adoption."""
    journal_root = tmp_path / JOURNAL_DIRECTORY_NAME
    store = ff.make_store(tmp_path)
    record = ff.make_submitted_record(tmp_path)
    store.create(record)                       # record only: no launch record written
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    m9._make_valid_png(frame)
    m9._write_journal(journal_root, record, m9._entry(record, m9._manifest_for(frame)))

    coord = _containment_dir_coordinator(store, tmp_path, journal_root)
    result = coord.reconcile_single_job(record.atlas_job_id)

    assert result.case_classified == "Case K (Quiescence Blocked)"
    assert result.recovery_status_after == RenderJobRecoveryStatus.WAITING_FOR_ENGINE_QUIESCENCE
    assert list(store.receipts_dir.glob("*.json")) == []

def test_containment_dir_path_refuses_a_launch_record_from_another_engine_incarnation(tmp_path):
    """DECIDING REGRESSION for the containment_dir construction path.

    The durable launch record names a different engine incarnation than the durable render
    record and the witness (the "mismatched keeper -> Unreal job" shape). The witness itself
    agrees with the durable record, so the older record-identity binding is satisfied and
    ONLY the containment check can refuse it. Verified discriminating: with the
    launch-record resolution forced back to the pre-fix shape, this same scenario ADOPTS
    (Case B with one receipt).
    """
    journal_root = tmp_path / JOURNAL_DIRECTORY_NAME
    store = ff.make_store(tmp_path)
    record = ff.make_submitted_record(tmp_path)
    store.create(record)
    ff.write_launch_record_for(store, record, engine_pid=record.origin_process_id + 5)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    m9._make_valid_png(frame)
    # The witness agrees with the durable record (process_id == origin_process_id).
    m9._write_journal(journal_root, record, m9._entry(record, m9._manifest_for(frame)))
    before = frame.read_bytes()

    coord = _containment_dir_coordinator(store, tmp_path, journal_root)
    result = coord.reconcile_single_job(record.atlas_job_id)

    assert result.case_classified == "Case E/F"
    assert result.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED
    assert "does not match the engine-witnessed process_id" in (result.failure_reason or "")
    assert list(store.receipts_dir.glob("*.json")) == []
    assert frame.read_bytes() == before
