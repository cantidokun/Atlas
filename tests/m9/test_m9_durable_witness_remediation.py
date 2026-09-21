"""M9 — REMEDIATION tests for the third-party blockers B1-B4 (M7 Case B durable witness).

B1 unreadable journal must not abort the recovery pass (fail closed, classified).
B2 stray/retained/badly-named journals must be IGNORED, not treated as evidence for this job.
B3 contradictory or absent engine identity must never be adopted (no COMPLETE/adoptable).
B4 a durable TERMINAL FAILED witness must be adjudicated offline (no engine dependency).

Deterministic only: no engine, no live render, no submission, no Blender.
"""
import json
import pathlib

import pytest

from planning.unreal_adapter_production import UnrealAdapterError
from planning.unreal_render_job_states import (
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
from planning.unreal_witness_journal import (
    JOURNAL_DIRECTORY_NAME,
    JOURNAL_STATUS_ABSENT,
    JOURNAL_STATUS_COMPLETE,
    JOURNAL_STATUS_CONFLICT,
    JOURNAL_STATUS_PARTIAL,
    DurableWitnessJournalReader,
    canonical_engine_job_id,
    engine_identity_conflict,
)

# Shared fixtures/helpers (single source of truth across the durable-witness suites).
from tests.m9.test_m9_durable_witness_adoption import (  # noqa: F401
    _ExplodingAdapter,
    _RecordingAdapter,
    _coordinator,
    _entry,
    _make_valid_png,
    _manifest_for,
    _receipts,
    _store_and_record,
    _supervisor,
    _write_journal,
)


def _live_adapter(journal_status="COMPLETE", known_jobs=None):
    return _RecordingAdapter(journal_status=journal_status, known_jobs=known_jobs)


def _inflight_live_candidate(record):
    return {
        "atlas_job_id": record.atlas_job_id,
        "job_id": record.unreal_job_id,
        "unreal_job_id": record.unreal_job_id,
        "sequence_asset_path": record.sequence_asset_path,
        "config_digest": record.config_digest,
        "output_directory": record.output_directory,
        "phase": "STARTED",
        "phase_sequence": 2,
        "attempt_ordinal": record.attempt_ordinal,
        "editor_session_id": record.origin_editor_session_id,
        "process_id": record.origin_process_id,
        "process_creation_time_utc": record.origin_process_creation_time,
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


def _journal_path(root, record):
    return root / f"{record.atlas_job_id}__{record.unreal_job_id}.json"


# ── B1: a bad journal is classified, never fatal ──────────────────────────
def test_b1_unreadable_journal_bytes_are_classified_and_do_not_abort(tmp_path, monkeypatch):
    """A read failure on a RELEVANT journal -> PARTIAL -> Case J; the pass survives."""
    store, record = _store_and_record(tmp_path)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    target = _write_journal(root, record, _entry(record, []))
    real_read_bytes = pathlib.Path.read_bytes

    def _denied(self, *a, **k):
        if self.name == target.name:
            raise PermissionError(13, "Access is denied")
        return real_read_bytes(self, *a, **k)

    monkeypatch.setattr(pathlib.Path, "read_bytes", _denied)

    witness = DurableWitnessJournalReader(root).read(record.atlas_job_id, record.unreal_job_id)
    assert witness.status == JOURNAL_STATUS_PARTIAL
    assert witness.is_adoptable is False
    assert "could not be read" in witness.reason

    result = _coordinator(store, record, tmp_path, adapter=_ExplodingAdapter()) \
        .reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case J"
    assert result.recovery_status_after == RenderJobRecoveryStatus.RECOVERY_PENDING
    assert _receipts(store) == []


def test_b1_unreadable_journal_does_not_abort_a_full_recovery_pass(tmp_path, monkeypatch):
    """reconcile_all_non_terminal_jobs completes even when a journal cannot be read."""
    store, record = _store_and_record(tmp_path)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    target = _write_journal(root, record, _entry(record, []))
    real_read_bytes = pathlib.Path.read_bytes

    def _denied(self, *a, **k):
        if self.name == target.name:
            raise PermissionError(13, "Access is denied")
        return real_read_bytes(self, *a, **k)

    monkeypatch.setattr(pathlib.Path, "read_bytes", _denied)
    results = _coordinator(store, record, tmp_path, adapter=_ExplodingAdapter()) \
        .reconcile_all_non_terminal_jobs()
    assert len(results) == 1
    assert results[0].case_classified == "Case J"


@pytest.mark.parametrize("label,body", [
    ("malformed JSON", b"{not json at all"),
    ("truncated JSON", b'{"journal_schema_version": 2, "atlas_job_id"'),
    ("structurally invalid (JSON array)", b"[1, 2, 3]"),
])
def test_b1_malformed_journal_bodies_are_classified(tmp_path, label, body):
    store, record = _store_and_record(tmp_path)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    root.mkdir(parents=True, exist_ok=True)
    _journal_path(root, record).write_bytes(body)
    witness = DurableWitnessJournalReader(root).read(record.atlas_job_id, record.unreal_job_id)
    assert witness.status == JOURNAL_STATUS_PARTIAL, label
    result = _coordinator(store, record, tmp_path, adapter=_ExplodingAdapter()) \
        .reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case J", label
    assert _receipts(store) == []


def test_b1_journal_without_atlas_identity_is_classified(tmp_path):
    """A §10-named file whose content has no atlas_job_id cannot be attributed to this job."""
    store, record = _store_and_record(tmp_path)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    root.mkdir(parents=True, exist_ok=True)
    _journal_path(root, record).write_text(json.dumps(
        {"journal_schema_version": 2, "phase": "FINISHED", "phase_sequence": 3}),
        encoding="utf-8")
    witness = DurableWitnessJournalReader(root).read(record.atlas_job_id, record.unreal_job_id)
    assert witness.status == JOURNAL_STATUS_PARTIAL
    assert _receipts(store) == []


# ── B2: unrelated material is ignored, never evidence ─────────────────────
@pytest.mark.parametrize("label,make_stray", [
    ("foreign valid journal for another atlas_job_id", lambda root: (root / (
        "atlas-render-job-99999999-0000-0000-0000-000000000000__unreal-other.json")).write_text(
        json.dumps({"journal_schema_version": 2,
                    "atlas_job_id": "atlas-render-job-99999999-0000-0000-0000-000000000000",
                    "unreal_job_id": "unreal-other", "phase": "FINISHED", "phase_sequence": 3}),
        encoding="utf-8")),
    ("retained legacy schema-1 journal for another job", lambda root: (root / (
        "atlas-render-job-88888888-0000-0000-0000-000000000000__unreal-old.json")).write_text(
        json.dumps({"journal_schema_version": 1,
                    "atlas_job_id": "atlas-render-job-88888888-0000-0000-0000-000000000000",
                    "unreal_job_id": "unreal-old", "phase": "FINISHED", "phase_sequence": 3}),
        encoding="utf-8")),
    ("unparseable unrelated JSON", lambda root: (root / "atlas-render-job-77777777-0000-0000-0000-000000000000__unreal-x.json").write_text(
        '{"journal_schema_version": 2, "atlas', encoding="utf-8")),
    ("badly named unrelated JSON", lambda root: (root / "random-notes.json").write_text(
        "{not a journal", encoding="utf-8")),
])
def test_b2_unrelated_material_is_ignored_and_live_path_is_preserved(tmp_path, label, make_stray):
    """A healthy engine-attached job must stay on the live path (Case A) despite junk."""
    store, record = _store_and_record(tmp_path)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    root.mkdir(parents=True, exist_ok=True)
    make_stray(root)

    witness = DurableWitnessJournalReader(root).read(record.atlas_job_id, record.unreal_job_id)
    assert witness.status == JOURNAL_STATUS_ABSENT, label
    assert witness.ignored_files, label

    adapter = _live_adapter(known_jobs=[_inflight_live_candidate(record)])
    result = _coordinator(store, record, tmp_path, adapter=adapter, quiescent=False, active=6) \
        .reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case A", label
    assert result.lifecycle_state_after == RenderJobLifecycleState.RENDERING
    assert _receipts(store) == []
    assert adapter.calls, label  # the live path really was consulted


def test_b2_relevant_witness_wins_over_unrelated_files(tmp_path):
    """A relevant attested witness is still adopted when junk shares the directory."""
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    _write_journal(root, record, _entry(record, _manifest_for(frame)))
    (root / "random-notes.json").write_text("{not a journal", encoding="utf-8")
    (root / "atlas-render-job-66666666-0000-0000-0000-000000000000__unreal-other.json").write_text(
        json.dumps({"journal_schema_version": 1, "atlas_job_id":
                    "atlas-render-job-66666666-0000-0000-0000-000000000000",
                    "unreal_job_id": "unreal-other", "phase": "FINISHED", "phase_sequence": 3}),
        encoding="utf-8")

    witness = DurableWitnessJournalReader(root).read(record.atlas_job_id, record.unreal_job_id)
    assert witness.status == JOURNAL_STATUS_COMPLETE
    assert len(witness.scanned_files) == 1
    assert len(witness.ignored_files) == 2

    result = _coordinator(store, record, tmp_path, adapter=_ExplodingAdapter()) \
        .reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case B"
    assert len(_receipts(store)) == 1


def test_b2_mislabeled_witness_for_this_job_fails_closed(tmp_path):
    """A §10 witness for THIS job that ignores the mandated filename must fail closed."""
    store, record = _store_and_record(tmp_path)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    root.mkdir(parents=True, exist_ok=True)
    (root / "not-a-valid-journal-name.json").write_text(json.dumps(
        {"journal_schema_version": 2, "atlas_job_id": record.atlas_job_id,
         "unreal_job_id": record.unreal_job_id, "phase": "FINISHED", "phase_sequence": 3,
         "phase_history": [_entry(record, [])]}), encoding="utf-8")
    witness = DurableWitnessJournalReader(root).read(record.atlas_job_id, record.unreal_job_id)
    assert witness.status == JOURNAL_STATUS_PARTIAL
    assert witness.is_adoptable is False
    result = _coordinator(store, record, tmp_path, adapter=_ExplodingAdapter()) \
        .reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case J"
    assert _receipts(store) == []


def test_b2_witness_for_a_different_engine_execution_is_case_e_f(tmp_path):
    """Same atlas_job_id, different unreal_job_id: fail closed as an identity disagreement.

    Interpretation recorded for the reviewer: a witness for the SAME Atlas job that names a
    different engine execution is not "unrelated material" (it is scoped to this job), so it
    reaches the durable binding check and fails closed (Contract V1 §21 Case E) rather than
    being ignored. It never adopts and never mints a receipt.
    """
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    _write_journal(root, record, _entry(record, _manifest_for(frame),
                                       unreal_job_id="unreal-job-OTHER"))
    witness = DurableWitnessJournalReader(root).read(record.atlas_job_id, record.unreal_job_id)
    assert witness.status == JOURNAL_STATUS_COMPLETE
    result = _coordinator(store, record, tmp_path, adapter=_ExplodingAdapter()) \
        .reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case E/F"
    assert result.lifecycle_state_after == RenderJobLifecycleState.RECOVERY_FAILED
    assert _receipts(store) == []


def test_b2_non_terminal_witness_uses_live_path_when_engine_is_up(tmp_path):
    """An in-flight durable witness must not preempt a healthy live session (Case A)."""
    store, record = _store_and_record(tmp_path)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    root.mkdir(parents=True, exist_ok=True)
    _journal_path(root, record).write_text(json.dumps({
        "journal_schema_version": 2, "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": record.unreal_job_id, "phase": "STARTED", "phase_sequence": 2,
        "phase_history": [{"phase": "ACCEPTED", "phase_sequence": 1}]}), encoding="utf-8")

    witness = DurableWitnessJournalReader(root).read(record.atlas_job_id, record.unreal_job_id)
    assert witness.status == JOURNAL_STATUS_COMPLETE
    assert witness.is_terminal is False
    assert witness.is_adoptable is False

    adapter = _live_adapter(known_jobs=[_inflight_live_candidate(record)])
    result = _coordinator(store, record, tmp_path, adapter=adapter, quiescent=False, active=6) \
        .reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case A"


def test_b2_non_terminal_witness_with_engine_down_is_case_j(tmp_path):
    """Engine unreachable + non-terminal witness = unresolved execution (Case J).

    The live transport probe is expected here (that is how reachability is learned); the
    classification itself comes from the durable witness, and no adoption/receipt occurs.
    """
    store, record = _store_and_record(tmp_path)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    root.mkdir(parents=True, exist_ok=True)
    _journal_path(root, record).write_text(json.dumps({
        "journal_schema_version": 2, "atlas_job_id": record.atlas_job_id,
        "unreal_job_id": record.unreal_job_id, "phase": "STARTED", "phase_sequence": 2,
        "phase_history": [{"phase": "ACCEPTED", "phase_sequence": 1}]}), encoding="utf-8")
    adapter = _RecordingAdapter(capable=False)
    result = _coordinator(store, record, tmp_path, adapter=adapter) \
        .reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case J"
    assert result.recovery_status_after == RenderJobRecoveryStatus.RECOVERY_PENDING
    assert _receipts(store) == []
    assert [c[0] for c in adapter.calls] == ["assert_recovery_capable"]  # probe only


# ── B3: identity must be single, present and consistent ───────────────────
def test_b3_resolver_never_resolves_a_contradiction():
    assert canonical_engine_job_id({"unreal_job_id": "U-1"}) == "U-1"
    assert canonical_engine_job_id({"job_id": "U-1"}) == "U-1"
    assert canonical_engine_job_id({"job_id": "U-1", "unreal_job_id": "U-1"}) == "U-1"
    assert canonical_engine_job_id({"job_id": "U-1", "unreal_job_id": "U-2"}) is None
    assert canonical_engine_job_id({}) is None
    assert engine_identity_conflict({"job_id": "U-1", "unreal_job_id": "U-2"}) is True
    assert engine_identity_conflict({"job_id": "U-1", "unreal_job_id": "U-1"}) is False


@pytest.mark.parametrize("label,overrides", [
    ("unreal_job_id only", {}),
    ("job_id only", {"drop": ("unreal_job_id",), "job_id": "unreal-job-m6-001"}),
    ("both matching", {"job_id": "unreal-job-m6-001"}),
])
def test_b3_consistent_identities_still_adopt(tmp_path, label, overrides):
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    # The witness HMAC signs the engine identity; the values used here are identical under
    # both names, so the helper's digest remains the correct signature.
    entry = _entry(record, _manifest_for(frame))
    if overrides.get("job_id"):
        entry["job_id"] = overrides["job_id"]
    for field in overrides.get("drop", ()):
        entry.pop(field, None)
    _write_journal(root, record, entry)

    witness = DurableWitnessJournalReader(root).read(record.atlas_job_id, record.unreal_job_id)
    assert witness.status == JOURNAL_STATUS_COMPLETE, label
    assert witness.is_adoptable is True, label
    result = _coordinator(store, record, tmp_path, adapter=_ExplodingAdapter()) \
        .reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case B", label
    assert len(_receipts(store)) == 1, label


@pytest.mark.parametrize("label,overrides", [
    ("both conflicting", {"job_id": "unreal-job-WRONG-IN-ENTRY"}),
    ("neither present", {"drop": ("unreal_job_id",)}),
])
def test_b3_contradictory_or_absent_identity_is_never_adoptable(tmp_path, label, overrides):
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    entry = _entry(record, _manifest_for(frame))
    if overrides.get("job_id"):
        entry["job_id"] = overrides["job_id"]
    for field in overrides.get("drop", ()):
        entry.pop(field, None)
    _write_journal(root, record, entry)

    witness = DurableWitnessJournalReader(root).read(record.atlas_job_id, record.unreal_job_id)
    assert witness.status == JOURNAL_STATUS_PARTIAL, label
    assert witness.is_adoptable is False, label
    assert witness.candidate is None, label

    result = _coordinator(store, record, tmp_path, adapter=_ExplodingAdapter()) \
        .reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case J", label
    assert _receipts(store) == [], label


# ── B4: durable terminal FAILED witness is adjudicated offline ────────────
@pytest.mark.parametrize("engine", ["down", "raising"])
def test_b4_durable_failed_witness_is_adjudicated_without_the_engine(tmp_path, engine):
    """A terminal FAILED witness -> Case G FAILED offline; no engine RPC, no receipt."""
    store, record = _store_and_record(tmp_path)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    _write_journal(root, record, _entry(record, [], phase="FAILED", finished=True,
                                       success=False, failed=True))
    adapter = _ExplodingAdapter() if engine == "raising" else _RecordingAdapter(capable=False)

    witness = DurableWitnessJournalReader(root).read(record.atlas_job_id, record.unreal_job_id)
    assert witness.status == JOURNAL_STATUS_COMPLETE
    assert witness.is_terminal is True
    assert witness.is_terminal_finished is False
    assert witness.is_adoptable is False

    result = _coordinator(store, record, tmp_path, adapter=adapter) \
        .reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case G"
    assert result.lifecycle_state_after == RenderJobLifecycleState.FAILED
    assert _receipts(store) == []
    if isinstance(adapter, _RecordingAdapter):
        assert adapter.calls == []


def test_b4_durable_failed_witness_with_declared_outputs_is_still_case_g(tmp_path):
    """A FAILED claim with a valid manifest/artifacts still fails closed (never adopts)."""
    store, record = _store_and_record(tmp_path)
    frame = pathlib.Path(record.output_directory) / "AtlasRender_0001.png"
    _make_valid_png(frame)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    _write_journal(root, record, _entry(record, _manifest_for(frame), phase="FAILED",
                                       finished=True, success=False, failed=True))
    result = _coordinator(store, record, tmp_path, adapter=_ExplodingAdapter()) \
        .reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case G"
    assert result.lifecycle_state_after == RenderJobLifecycleState.FAILED
    assert _receipts(store) == []


def test_b4_durable_failed_witness_still_requires_quiescence(tmp_path):
    """A terminal FAILED witness with a non-quiescent job is Case K, not an adoption."""
    store, record = _store_and_record(tmp_path)
    root = tmp_path / JOURNAL_DIRECTORY_NAME
    _write_journal(root, record, _entry(record, [], phase="FAILED", finished=True,
                                       success=False, failed=True))
    result = _coordinator(store, record, tmp_path, adapter=_ExplodingAdapter(),
                          quiescent=False, active=6).reconcile_single_job(record.atlas_job_id)
    assert result.case_classified == "Case K (Quiescence Blocked)"
    assert result.recovery_status_after == RenderJobRecoveryStatus.WAITING_FOR_ENGINE_QUIESCENCE
    assert _receipts(store) == []
