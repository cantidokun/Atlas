"""Containment keeper — launch boundary, retention, drain-edge trigger, failure semantics.

Drives the REAL keeper (``scripts/run_unreal_containment_keeper.py``) with faked Win32
process primitives only (no engine, no Unreal, no render, no Blender). The recovery pass at
the drain edge uses the REAL composition root and the REAL coordinator against a real
durable store, a real HMAC-attested witness journal and real PNG bytes on disk.

MF-4 controls covered here: duplicate keeper authority, stale keeper identity, mismatched
keeper -> Atlas job, missing launch record, keeper crash, handle loss, Atlas restart while
the keeper survives, engine crash, exactly-once Case-B receipt, zero-RPC adoption.
"""
from __future__ import annotations

import json
import pathlib

import pytest

import scripts.run_unreal_recovery as recovery_module

import scripts.run_unreal_containment_keeper as keeper_module
import tests.m6.fault_fixtures as ff
import tests.m9.test_m9_durable_witness_adoption as m9
from planning.unreal_containment_launch_record import (
    ContainmentLaunchRecordError,
    ContainmentNonceCustodyError,
    containment_dir_for_store,
    load_launch_record,
    verify_launch_record_for_job,
)
from planning.unreal_render_job_states import (
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
from scripts.run_unreal_containment_keeper import (
    KEEPER_SOURCE_IDENTITY,
    ContainmentKeeper,
    ContainmentKeeperRefusedError,
)
from scripts.run_unreal_supervisor import JobObjectContainmentState, SuspendedProcess

NONCE = "m7-keeper-nonce-0123456789abcdef0123456789abcdef"
JOURNAL_DIR = "AtlasWitnessJournal"


class _Events(list):
    def add(self, item):
        self.append(item)
        return item


class _FakeSupervisor:
    """Supervisor double exposing the kernel surface the keeper actually reads."""

    def __init__(self, *, active=1, total=1, kill_on_job_close=True, breakaway_disabled=True,
                 events=None):
        self.job_handle = None
        self.job_name = "AtlasTestContainmentJob"
        self.active = active
        self.total = total
        self.kill_on_job_close = kill_on_job_close
        self.silent_breakaway_ok = not breakaway_disabled
        self.events = events if events is not None else _Events()
        self.closed = False

    def create_contained_job(self):
        self.job_handle = 0x1234
        self.events.add("create_job")
        return self.job_handle

    def assign_suspended_process(self, process_handle):
        self.events.add(("assign", process_handle))

    def query_containment_state(self):
        self.events.add("query_state")
        return JobObjectContainmentState(
            active_processes=self.active,
            total_processes=self.total,
            total_terminated_processes=0,
            limit_flags=(0x00002000 if self.kill_on_job_close else 0)
            | (0 if not self.silent_breakaway_ok else 0x00001000),
            kill_on_job_close=self.kill_on_job_close,
            silent_breakaway_ok=self.silent_breakaway_ok,
            breakaway_ok=False,
        )

    def query_active_processes(self):
        return self.active

    def close(self):
        self.events.add("close_job")
        self.closed = True
        self.job_handle = None


class _Harness:
    """A realistic project + store + record triple, plus faked process primitives."""

    def __init__(self, tmp_path, *, attempt_ordinal=1, atlas_job_id=None, nonce=NONCE):
        self.project_dir = tmp_path / "proj"
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.uproject = self.project_dir / "Atlas.uproject"
        self.uproject.write_text('{"FileVersion": 3}', encoding="utf-8")
        self.store_root = tmp_path / "store"
        self.journal_root = self.project_dir / JOURNAL_DIR
        # The submission renders inside the project's Saved/ tree; the atlas_job_id must be
        # part of the output directory (the record enforces output isolation).
        self.job_id = atlas_job_id or ff.canonical_intent_kwargs(tmp_path)["atlas_job_id"]
        renders_parent = self.project_dir / "Saved" / "MovieRenders"
        overrides = {
            "atlas_job_id": self.job_id,
            "output_parent_directory": str(renders_parent),
            "output_directory": str(renders_parent / self.job_id),
        }
        self.store = ff.make_store(tmp_path)
        self.record = ff.make_submitted_record(
            tmp_path, attempt_ordinal=attempt_ordinal, attempt_nonce=nonce, **overrides
        )
        self.store.create(self.record)
        pathlib.Path(self.record.output_directory).mkdir(parents=True, exist_ok=True)
        self.events = _Events()
        self.resume_observations = []

    def keeper(self, **kwargs):
        return ContainmentKeeper(
            store_root=str(self.store_root),
            uproject=str(self.uproject),
            atlas_job_id=self.record.atlas_job_id,
            attempt_ordinal=self.record.attempt_ordinal,
            supervisor=kwargs.pop("supervisor", None) or _FakeSupervisor(events=self.events),
            recovery_trigger=kwargs.pop("recovery_trigger", None),
            **kwargs,
        )

    def install_process_fakes(self, monkeypatch, *, fail_record_write=False):
        harness = self

        class _Boom(RuntimeError):
            pass

        def fake_create(command_line, *, application_name=None, working_directory=None,
                        create_new_console=False, create_no_window=False):
            harness.events.add("create_process_suspended")
            # The kernel-reported incarnation must be the one the durable record already
            # names (same engine process); the coordinator refuses a provable disagreement.
            return SuspendedProcess(
                process_handle=0xABC,
                thread_handle=0xDEF,
                process_id=harness.record.origin_process_id,
                thread_id=1,
                process_creation_time_utc=harness.record.origin_process_creation_time,
                command_line=command_line,
            )

        def fake_resume(thread_handle):
            # The launch identity MUST already be durable at this instant.
            resolved, reason = verify_launch_record_for_job(
                containment_dir_for_store(harness.store_root), harness.record
            )
            harness.resume_observations.append((resolved is not None, reason))
            harness.events.add(("resume", thread_handle))

        monkeypatch.setattr(keeper_module, "create_process_suspended", fake_create)
        monkeypatch.setattr(keeper_module, "resume_process", fake_resume)
        monkeypatch.setattr(
            keeper_module, "terminate_process",
            lambda handle, exit_code=1: harness.events.add(("terminate", handle)),
        )
        monkeypatch.setattr(keeper_module, "close_handle", lambda handle: None)
        if fail_record_write:
            def boom(*args, **kwargs):
                harness.events.add("write_records_failed")
                raise _Boom("disk full")
            monkeypatch.setattr(keeper_module, "write_launch_record", boom)


# ── launch boundary ──────────────────────────────────────────────────────
def test_launch_writes_the_identity_durably_before_resume_in_the_mandated_order(tmp_path, monkeypatch):
    h = _Harness(tmp_path)
    h.install_process_fakes(monkeypatch)
    keeper = h.keeper()

    launch = keeper.launch(attempt_nonce=NONCE, command_line="UnrealEditor-Cmd.exe Atlas.uproject")

    assert h.events == [
        "create_job",
        "create_process_suspended",
        ("assign", 0xABC),
        "query_state",
        ("resume", 0xDEF),
    ]
    assert h.resume_observations == [(True, "")]  # verified BEFORE the engine ran
    assert launch.engine_pid == h.record.origin_process_id
    assert launch.process_creation_time_utc == h.record.origin_process_creation_time
    assert launch.launch_composition_processes == 1  # measured from the kernel, not assumed
    assert launch.job_identity_descriptor == keeper.job_name
    assert launch.keeper_identity.startswith(KEEPER_SOURCE_IDENTITY)
    assert launch.editor_session_id is None  # never fabricated before resume
    assert launch.project_identity == str(pathlib.Path(h.project_dir).resolve())
    durable = load_launch_record(
        containment_dir_for_store(h.store_root), h.record.atlas_job_id, h.record.attempt_ordinal
    )
    assert durable.launch_record_digest == launch.launch_record_digest
    assert NONCE.encode() not in (
        containment_dir_for_store(h.store_root) / f"{h.record.atlas_job_id}__1.json"
    ).read_bytes()


def test_launch_refuses_missing_or_invented_nonce_before_creating_the_job(tmp_path, monkeypatch):
    h = _Harness(tmp_path)
    h.install_process_fakes(monkeypatch)
    keeper = h.keeper()

    with pytest.raises(ContainmentNonceCustodyError):
        keeper.launch(attempt_nonce="", command_line="engine")
    with pytest.raises(ContainmentNonceCustodyError):
        keeper.launch(attempt_nonce="keeper-invented-nonce", command_line="engine")

    assert h.events == []
    assert not containment_dir_for_store(h.store_root).exists()
    assert keeper.launch_record is None


def test_launch_failure_after_assign_reaps_the_suspended_engine(tmp_path, monkeypatch):
    h = _Harness(tmp_path)
    h.install_process_fakes(monkeypatch, fail_record_write=True)
    keeper = h.keeper()

    with pytest.raises(RuntimeError):
        keeper.launch(attempt_nonce=NONCE, command_line="engine")

    assert ("terminate", 0xABC) in h.events
    assert "close_job" in h.events
    assert not any(isinstance(e, tuple) and e[0] == "resume" for e in h.events)
    assert keeper.launch_record is None


# ── MF-4: duplicate / stale / mismatched keeper identity ─────────────────
def test_duplicate_keeper_authority_for_one_attempt_fails_closed(tmp_path, monkeypatch):
    h = _Harness(tmp_path)
    h.install_process_fakes(monkeypatch)
    first = h.keeper(keeper_instance_id="keeper-A")
    launch = first.launch(attempt_nonce=NONCE, command_line="engine")

    second_events = _Events()
    second = ContainmentKeeper(
        store_root=str(h.store_root),
        uproject=str(h.uproject),
        atlas_job_id=h.record.atlas_job_id,
        attempt_ordinal=h.record.attempt_ordinal,
        supervisor=_FakeSupervisor(events=second_events),
        keeper_instance_id="keeper-B",
    )
    with pytest.raises(ContainmentLaunchRecordError):
        second.launch(attempt_nonce=NONCE, command_line="engine")

    # The usurper's suspended engine is terminated by the fail-closed cleanup (process
    # handling is shared across keepers in this harness), and it never resumes anything.
    assert h.events.count(("terminate", 0xABC)) == 1
    assert "close_job" in second_events
    assert not any(isinstance(e, tuple) and e[0] == "resume" for e in second_events)
    durable = load_launch_record(
        containment_dir_for_store(h.store_root), h.record.atlas_job_id, h.record.attempt_ordinal
    )
    assert durable.launch_record_digest == launch.launch_record_digest  # first identity intact
    assert "keeper-A" in durable.keeper_identity


def test_keeper_bound_to_a_stale_attempt_ordinal_or_unknown_job_is_refused(tmp_path, monkeypatch):
    h = _Harness(tmp_path)
    h.install_process_fakes(monkeypatch)

    stale = ContainmentKeeper(
        store_root=str(h.store_root),
        uproject=str(h.uproject),
        atlas_job_id=h.record.atlas_job_id,
        attempt_ordinal=2,
        supervisor=_FakeSupervisor(events=h.events),
    )
    with pytest.raises(ContainmentKeeperRefusedError):
        stale.launch(attempt_nonce=NONCE, command_line="engine")

    foreign = ContainmentKeeper(
        store_root=str(h.store_root),
        uproject=str(h.uproject),
        atlas_job_id="atlas-render-job-99999999-9999-9999-9999-999999999999",
        attempt_ordinal=1,
        supervisor=_FakeSupervisor(events=h.events),
    )
    with pytest.raises(ContainmentKeeperRefusedError):
        foreign.launch(attempt_nonce=NONCE, command_line="engine")

    assert h.events == []  # no Job Object was created for either refusal


def test_keeper_refuses_uncontained_deployment_mode(tmp_path):
    h = _Harness(tmp_path)
    with pytest.raises(ContainmentKeeperRefusedError):
        ContainmentKeeper(
            store_root=str(h.store_root),
            uproject=str(h.uproject),
            atlas_job_id=h.record.atlas_job_id,
            attempt_ordinal=1,
            deployment_mode="UNCONTAINED_ATTACHED",
        )


# ── drain observation & trigger ──────────────────────────────────────────
def test_trigger_requires_an_observed_drain_on_the_retained_handle(tmp_path, monkeypatch):
    h = _Harness(tmp_path)
    h.install_process_fakes(monkeypatch)
    supervisor = _FakeSupervisor(active=3, events=h.events)
    keeper = h.keeper(supervisor=supervisor)
    keeper.launch(attempt_nonce=NONCE, command_line="engine")

    with pytest.raises(ContainmentKeeperRefusedError):
        keeper.trigger_recovery()  # never drained

    ticks = iter([0.0, 10.0, 20.0, 30.0])
    keeper._clock = lambda: next(ticks)
    assert keeper.wait_for_drain(timeout_seconds=5) is False  # still 3 active at the deadline
    with pytest.raises(ContainmentKeeperRefusedError):
        keeper.trigger_recovery()


def test_handle_loss_fails_closed_and_recovers_nothing(tmp_path, monkeypatch):
    h = _Harness(tmp_path)
    h.install_process_fakes(monkeypatch)
    supervisor = _FakeSupervisor(active=0, events=h.events)
    keeper = h.keeper(supervisor=supervisor)
    keeper.launch(attempt_nonce=NONCE, command_line="engine")
    assert keeper.wait_for_drain(timeout_seconds=1) is True

    supervisor.job_handle = None  # handle lost / closed by accident
    with pytest.raises(ContainmentKeeperRefusedError):
        keeper.trigger_recovery()
    assert keeper.recovery_evidence is None


def test_keeper_crash_before_drain_leaves_the_attempt_unadoptable(tmp_path, monkeypatch):
    """KILL_ON_JOB_CLOSE reaps the tree; a substituted fresh object cannot recover it."""
    h = _Harness(tmp_path)
    h.install_process_fakes(monkeypatch)
    supervisor = _FakeSupervisor(active=4, events=h.events)
    keeper = h.keeper(supervisor=supervisor)
    keeper.launch(attempt_nonce=NONCE, command_line="engine")

    # keeper crashes: its last handle close destroys the object (and reaps the tree).
    supervisor.close()
    assert supervisor.closed is True and supervisor.job_handle is None

    frame = pathlib.Path(h.record.output_directory) / "AtlasRender_0001.png"
    m9._make_valid_png(frame)
    m9._write_journal(h.journal_root, h.record, m9._entry(h.record, m9._manifest_for(frame)))

    # A later recovery attempt has no launch object. The composition root refuses to
    # compose at all without a retained handle, and a direct coordinator evaluation of the
    # same conditions holds closed: the terminal witness and artifacts are never adopted.
    from scripts.run_unreal_recovery import CompositionRefusedError, build_recovery_runtime

    with pytest.raises(CompositionRefusedError):
        build_recovery_runtime(
            store_root=str(h.store_root), uproject=str(h.uproject),
            supervisor=ff.contained_supervisor(job_handle=None),
            launch_record=ff.make_launch_record(h.record), adapter=m9._RecordingAdapter(capable=False),
        )

    result = _direct_coordinator(h, ff.contained_supervisor(job_handle=None)).reconcile_single_job(
        h.record.atlas_job_id
    )
    assert result.case_classified == "Case K (Quiescence Blocked)"
    assert result.recovery_status_after == RenderJobRecoveryStatus.WAITING_FOR_ENGINE_QUIESCENCE
    assert list(h.store.receipts_dir.glob("*.json")) == []


# ── drain-edge adoption (real composition root + real coordinator) ───────
def _direct_coordinator(h, supervisor, adapter=None):
    """Coordinator built directly (no composition root) for predicate-level controls."""
    from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
    from planning.unreal_render_recovery_coordinator import UnrealRenderRecoveryCoordinator

    return UnrealRenderRecoveryCoordinator(
        store=h.store,
        adapter=adapter or m9._RecordingAdapter(capable=False),
        receipt_store=UnrealRenderReceiptStore(h.store_root / "rcpt.json"),
        supervisor=supervisor,
        deployment_mode="CONTAINED_JOB_OBJECT",
        journal_root=str(h.journal_root),
    )


def _run_recovery(h, *, supervisor, adapter, keeper=None, atlas_job_id=None,
                  coordinator_id="keeper-test"):
    from scripts.run_unreal_recovery import build_recovery_runtime, run_recovery_pass

    if keeper is None:
        keeper = h.keeper(supervisor=supervisor)
        keeper.launch_record = ff.make_launch_record(h.record)
    runtime = build_recovery_runtime(
        store_root=str(h.store_root),
        uproject=str(h.uproject),
        supervisor=supervisor,
        launch_record=keeper.launch_record,
        adapter=adapter,
        coordinator_id=coordinator_id,
    )
    evidence = run_recovery_pass(
        runtime, atlas_job_id=atlas_job_id or h.record.atlas_job_id, job_records=[h.record]
    )
    return runtime.coordinator, evidence


def _full_drain_setup(h):
    frame = pathlib.Path(h.record.output_directory) / "AtlasRender_0001.png"
    m9._make_valid_png(frame)
    m9._write_journal(h.journal_root, h.record, m9._entry(h.record, m9._manifest_for(frame)))
    return frame


def test_keeper_drain_edge_adoption_is_case_b_with_one_receipt_and_zero_rpc(tmp_path, monkeypatch):
    h = _Harness(tmp_path)
    h.install_process_fakes(monkeypatch)
    supervisor = _FakeSupervisor(active=1, events=h.events)
    keeper = h.keeper(supervisor=supervisor)
    keeper.launch(attempt_nonce=NONCE, command_line="engine")
    _full_drain_setup(h)
    supervisor.active = 0
    assert keeper.wait_for_drain(timeout_seconds=1) is True

    exploding = m9._ExplodingAdapter()
    coordinator, evidence = _run_recovery(h, supervisor=supervisor, adapter=exploding, keeper=keeper)

    decisions = evidence["decisions"]
    assert decisions[0]["case_classified"] == "Case B"
    assert decisions[0]["lifecycle_state_after"] == "FINALIZED"
    receipts = sorted(h.store.receipts_dir.glob("*.json"))
    assert len(receipts) == 1
    assert evidence["launch_record_digest"] == keeper.launch_record.launch_record_digest
    assert evidence["uproject_digest"] and evidence["journal_root_canonical"].endswith(JOURNAL_DIR)
    assert evidence["job_bindings"][0]["launch_record_binding"] == "BOUND"
    assert evidence["job_bindings"][0]["project_association"] == "BOUND"
    assert evidence["job_bindings"][0]["project_association_corroboration"] == "WITHIN_PROJECT_DIR"


def test_keeper_second_pass_after_publication_repairs_from_the_receipt(tmp_path, monkeypatch):
    h = _Harness(tmp_path)
    h.install_process_fakes(monkeypatch)
    supervisor = _FakeSupervisor(active=1, events=h.events)
    keeper = h.keeper(supervisor=supervisor)
    keeper.launch(attempt_nonce=NONCE, command_line="engine")
    _full_drain_setup(h)
    supervisor.active = 0
    keeper.wait_for_drain(timeout_seconds=1)

    _, first = _run_recovery(h, supervisor=supervisor, adapter=m9._ExplodingAdapter(), keeper=keeper)
    _, second = _run_recovery(h, supervisor=supervisor, adapter=m9._ExplodingAdapter(),
                              keeper=keeper, coordinator_id="keeper-test-second")

    assert first["decisions"][0]["case_classified"] == "Case B"
    assert second["decisions"][0]["case_classified"] == "RECEIPT_FIRST"
    assert second["decisions"][0]["repaired_from_receipt"] is True
    assert len(list(h.store.receipts_dir.glob("*.json"))) == 1


def test_atlas_restart_while_the_keeper_survives_still_adopts(tmp_path, monkeypatch):
    """Quiescence ownership lives in the keeper process, not in Atlas' memory."""
    h = _Harness(tmp_path)
    h.install_process_fakes(monkeypatch)
    supervisor = _FakeSupervisor(active=1, events=h.events)
    keeper = h.keeper(supervisor=supervisor)
    keeper.launch(attempt_nonce=NONCE, command_line="engine")
    _full_drain_setup(h)

    # "Atlas restart": the first runtime is assembled and thrown away, then a second,
    # independent invocation adopts using the SAME retained handle and launch record.
    from scripts.run_unreal_recovery import build_recovery_runtime
    _discarded = build_recovery_runtime(
        store_root=str(h.store_root), uproject=str(h.uproject), supervisor=supervisor,
        launch_record=keeper.launch_record, adapter=m9._ExplodingAdapter(),
    )
    supervisor.active = 0
    assert keeper.wait_for_drain(timeout_seconds=1) is True

    _, evidence = _run_recovery(h, supervisor=supervisor, adapter=m9._ExplodingAdapter(),
                                keeper=keeper, coordinator_id="post-restart")
    assert evidence["decisions"][0]["case_classified"] == "Case B"
    assert len(list(h.store.receipts_dir.glob("*.json"))) == 1


def test_engine_crash_mid_render_is_case_j_with_no_receipt(tmp_path, monkeypatch):
    h = _Harness(tmp_path)
    h.install_process_fakes(monkeypatch)
    supervisor = _FakeSupervisor(active=1, events=h.events)
    keeper = h.keeper(supervisor=supervisor)
    keeper.launch(attempt_nonce=NONCE, command_line="engine")

    # A torn, non-terminal journal: the engine died mid-render after ACCEPTED/STARTED.
    journal = {
        "journal_schema_version": 2,
        "atlas_job_id": h.record.atlas_job_id,
        "unreal_job_id": h.record.unreal_job_id,
        "phase": "STARTED",
        "phase_sequence": 2,
        "status": "rendering",
        "success": False,
        "finished": False,
        "phase_history": [
            {"phase": "ACCEPTED", "phase_sequence": 1},
            {"phase": "STARTED", "phase_sequence": 2},
        ],
    }
    h.journal_root.mkdir(parents=True, exist_ok=True)
    (h.journal_root / f"{h.record.atlas_job_id}__{h.record.unreal_job_id}.json").write_text(
        json.dumps(journal), encoding="utf-8"
    )
    supervisor.active = 0
    assert keeper.wait_for_drain(timeout_seconds=1) is True

    _, evidence = _run_recovery(h, supervisor=supervisor,
                                adapter=m9._RecordingAdapter(capable=False), keeper=keeper)
    assert evidence["decisions"][0]["case_classified"] == "Case J"
    assert evidence["decisions"][0]["recovery_status_after"] == "RECOVERY_PENDING"
    assert list(h.store.receipts_dir.glob("*.json")) == []


def test_keeper_run_releases_the_handle_only_after_the_pass(tmp_path, monkeypatch):
    h = _Harness(tmp_path)
    h.install_process_fakes(monkeypatch)
    supervisor = _FakeSupervisor(active=1, events=h.events)
    observed = {}

    def trigger(keeper):
        observed["handle_at_trigger"] = keeper.supervisor.job_handle
        observed["drain_observed"] = keeper.drain_observed
        return {"decisions": [{"case_classified": "Case B"}]}

    supervisor.active = 0  # the engine has already exited when the keeper starts watching
    keeper = h.keeper(supervisor=supervisor, recovery_trigger=trigger)
    outcome = keeper.run(attempt_nonce=NONCE, command_line="engine", drain_timeout_seconds=1)

    assert observed == {"handle_at_trigger": 0x1234, "drain_observed": True}
    assert outcome["drain_observed"] is True
    assert h.events[-1] == "close_job"  # released only after the pass returned


def test_keeper_run_fails_closed_when_the_tree_never_drains(tmp_path, monkeypatch):
    h = _Harness(tmp_path)
    h.install_process_fakes(monkeypatch)
    supervisor = _FakeSupervisor(active=2, events=h.events)
    keeper = h.keeper(supervisor=supervisor, drain_timeout_seconds=0)
    keeper._clock = lambda: 0.0

    with pytest.raises(ContainmentKeeperRefusedError):
        keeper.run(attempt_nonce=NONCE, command_line="engine", drain_timeout_seconds=0)
    assert keeper.recovery_evidence is None
    # No trigger and no explicit release: containment stays intact and the tree is only
    # reaped by KILL_ON_JOB_CLOSE when the keeper process ends (fail closed).
    assert "close_job" not in h.events
    assert ("resume", 0xDEF) in h.events

# ── red-team cleanup item 1: durable invocation evidence at the drain edge ──
def _drained_keeper_with_default_trigger(h, monkeypatch, supervisor):
    """Keeper whose recovery trigger is the PRODUCTION default (no injection)."""
    keeper = h.keeper(supervisor=supervisor)
    keeper.launch(attempt_nonce=NONCE, command_line="engine")
    _full_drain_setup(h)
    supervisor.active = 0
    assert keeper.wait_for_drain(timeout_seconds=1) is True
    # Only the engine transport is faked; the composition root, coordinator, store, journal,
    # artifacts and the evidence writer are the production ones.
    monkeypatch.setattr(
        recovery_module, "create_production_adapter",
        lambda *args, **kwargs: m9._RecordingAdapter(capable=False),
    )
    return keeper


def test_default_trigger_persists_invocation_evidence_durably(tmp_path, monkeypatch):
    h = _Harness(tmp_path)
    h.install_process_fakes(monkeypatch)
    supervisor = _FakeSupervisor(active=1, events=h.events)
    keeper = _drained_keeper_with_default_trigger(h, monkeypatch, supervisor)

    outcome = keeper.trigger_recovery()

    assert outcome["decisions"][0]["case_classified"] == "Case B"
    assert len(list(h.store.receipts_dir.glob("*.json"))) == 1
    evidence_files = sorted((h.store_root / "containment").glob("recovery_invocation_*.json"))
    assert len(evidence_files) == 1, "the default drain-edge trigger left no durable evidence"
    assert outcome["invocation_evidence_path"] == str(evidence_files[0])
    persisted = json.loads(evidence_files[0].read_text(encoding="utf-8"))
    assert persisted["journal_root_canonical"] == str(h.journal_root.resolve())
    assert persisted["launch_record_digest"] == keeper.launch_record.launch_record_digest
    assert persisted["decisions"][0]["case_classified"] == "Case B"
    assert NONCE not in json.dumps(persisted)          # the nonce is never persisted
    # and the artifact lives beside the containment provenance, never in the witness root
    assert h.journal_root not in evidence_files[0].parents


def test_keeper_run_reports_the_durable_evidence_path(tmp_path, monkeypatch):
    h = _Harness(tmp_path)
    h.install_process_fakes(monkeypatch)
    supervisor = _FakeSupervisor(active=0, total=1, events=h.events)
    monkeypatch.setattr(
        recovery_module, "create_production_adapter",
        lambda *args, **kwargs: m9._RecordingAdapter(capable=False),
    )

    outcome = keeper = None
    keeper = h.keeper(supervisor=supervisor)
    _full_drain_setup(h)
    outcome = keeper.run(attempt_nonce=NONCE, command_line="engine", drain_timeout_seconds=1)

    assert outcome["invocation_evidence_path"] is not None
    assert pathlib.Path(outcome["invocation_evidence_path"]).is_file()


def test_default_trigger_does_not_report_success_when_evidence_cannot_be_persisted(tmp_path, monkeypatch):
    """Fail closed: an unrecorded invocation is never reported as a success."""
    h = _Harness(tmp_path)
    h.install_process_fakes(monkeypatch)
    supervisor = _FakeSupervisor(active=1, events=h.events)
    keeper = _drained_keeper_with_default_trigger(h, monkeypatch, supervisor)

    def _boom(runtime, evidence):
        raise OSError("containment directory is not writable")

    monkeypatch.setattr(recovery_module, "write_invocation_evidence", _boom)

    with pytest.raises(OSError):
        keeper.trigger_recovery()          # no success is reported for this invocation

    # No invocation-evidence artifact exists ...
    assert list((h.store_root / "containment").glob("recovery_invocation_*.json")) == []
    # ... and the receipt, which is published by the store-gated path BEFORE the evidence is
    # written, is still exactly one: the pass itself is not rolled back by a failed evidence
    # write (it is durable in the store), but the caller never sees a successful outcome.
    assert len(list(h.store.receipts_dir.glob("*.json"))) == 1
    assert keeper.recovery_evidence is None or "invocation_evidence_path" not in keeper.recovery_evidence
