"""Real-kernel containment evidence (Windows only): the F-DG-1 discriminator, live.

No Unreal, no render, no Blender: a real Windows Job Object with a short-lived Python child
is enough to prove the kernel facts the §9 predicate depends on —

* a fresh, never-used Job Object reports ``ActiveProcesses == 0`` AND ``TotalProcesses == 0``,
  so it is refused as provenance even though it looks quiescent;
* an object that actually contained a process tree reports ``TotalProcesses >= 1`` and can
  satisfy the predicate once it drains;
* ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`` is read back from the object and reaps the tree when
  the last handle closes (the keeper-crash fail-closed semantics);
* ``create-suspended -> assign -> resume`` is the only assignment order Windows accepts here.

Skipped on non-Windows platforms.
"""
from __future__ import annotations

import datetime
import os
import pathlib
import sys
import time

import pytest

import tests.m6.fault_fixtures as ff
from planning.unreal_containment_launch_record import build_launch_record
from planning.unreal_containment_quiescence import evaluate_containment_quiescence
from planning.unreal_render_job_states import RenderJobLifecycleState
from scripts.run_unreal_supervisor import (
    AtlasProcessSupervisor,
    close_handle,
    create_process_suspended,
    resume_process,
    terminate_process,
)

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows Job Objects only")

CHILD_SCRIPT = """\
import pathlib, sys, time
heartbeat = pathlib.Path(sys.argv[1])
deadline = time.time() + 120
while time.time() < deadline:
    heartbeat.write_text(str(time.time()), encoding="utf-8")
    time.sleep(0.2)
"""


def _write_child(tmp_path: pathlib.Path) -> pathlib.Path:
    script = tmp_path / "containment_child.py"
    script.write_text(CHILD_SCRIPT, encoding="utf-8")
    return script


def _spawn_contained(supervisor: AtlasProcessSupervisor, tmp_path: pathlib.Path,
                     heartbeat: pathlib.Path = None, *, command_line: str = None):
    if command_line is None:
        script = _write_child(tmp_path)
        command_line = f'"{sys.executable}" "{script}" "{heartbeat}"'
    suspended = create_process_suspended(
        command_line,
        application_name=sys.executable,
        create_no_window=True,
    )
    supervisor.assign_suspended_process(suspended.process_handle)
    state_at_launch = supervisor.query_containment_state()
    resume_process(suspended.thread_handle)
    close_handle(suspended.thread_handle)
    return suspended, state_at_launch


def _wait_for_drain(supervisor: AtlasProcessSupervisor, timeout: float = 20.0) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if supervisor.query_containment_state().active_processes == 0:
            return 0
        time.sleep(0.25)
    return supervisor.query_containment_state().active_processes


def _project(tmp_path) -> "object":
    from tests.m7.containment_harness import ContainmentProject

    return ContainmentProject(tmp_path)


def test_real_kernel_discriminates_a_fresh_object_from_the_drained_launch_object(tmp_path):
    project = _project(tmp_path)
    # A short-lived child models the engine exiting after its work: the tree drains on its own.
    short_lived = f'"{sys.executable}" -c "import time; time.sleep(3)"'

    launch_job = AtlasProcessSupervisor(job_name="AtlasM7KernelTest")
    launch_job.create_contained_job()
    fresh_job = AtlasProcessSupervisor()
    fresh_job.create_contained_job()

    suspended = None
    try:
        suspended, state_at_launch = _spawn_contained(launch_job, tmp_path, None, command_line=short_lived)

        # §9 kernel conjuncts hold while the tree is alive ...
        assert state_at_launch.active_processes >= 1
        assert state_at_launch.total_processes >= 1
        assert state_at_launch.kill_on_job_close is True
        assert state_at_launch.breakaway_disabled is True

        launch_record = build_launch_record(
            atlas_job_id=project.record.atlas_job_id,
            attempt_ordinal=project.record.attempt_ordinal,
            attempt_nonce=project.record.attempt_nonce,
            engine_pid=suspended.process_id,
            process_creation_time_utc=suspended.process_creation_time_utc,
            launch_composition_processes=int(state_at_launch.total_processes),
            project_identity=project.record.output_directory,
            uproject_digest=ff.TEST_UPROJECT_DIGEST,
            keeper_identity="kernel-test",
            job_identity_descriptor="AtlasM7KernelTest",
        )

        alive = evaluate_containment_quiescence(
            launch_job, "CONTAINED_JOB_OBJECT",
            launch_record=launch_record, job_record=project.record,
        )
        assert alive.is_quiescent is False
        assert alive.active_process_count >= 1

        # ... and once it drains, the attempt's OWN object satisfies the predicate.
        assert _wait_for_drain(launch_job) == 0
        drained = evaluate_containment_quiescence(
            launch_job, "CONTAINED_JOB_OBJECT",
            launch_record=launch_record, job_record=project.record,
        )
        assert drained.is_quiescent is True
        assert drained.provenance_verified is True
        assert drained.total_processes >= launch_record.launch_composition_processes >= 1
        assert drained.kill_on_job_close is True and drained.breakaway_disabled is True

        # DECIDING CONTROL: a fresh never-used object, offered as this attempt's
        # containment, is refused even though ActiveProcesses == 0.
        fresh_state = fresh_job.query_containment_state()
        assert (fresh_state.active_processes, fresh_state.total_processes) == (0, 0)
        refused = evaluate_containment_quiescence(
            fresh_job, "CONTAINED_JOB_OBJECT",
            launch_record=launch_record, job_record=project.record,
        )
        assert refused.is_quiescent is False
        assert "TotalProcesses=0" in refused.reason
    finally:
        for handle in (suspended.process_handle if suspended else None,):
            if handle:
                try:
                    terminate_process(handle)
                except Exception:  # noqa: BLE001
                    pass
                close_handle(handle)
        launch_job.close()
        fresh_job.close()


def test_real_kernel_reaps_the_tree_when_the_last_handle_closes(tmp_path):
    """KILL_ON_JOB_CLOSE: the keeper-crash fail-closed path, observed on the kernel."""
    heartbeat = tmp_path / "hb_reap.txt"
    job = AtlasProcessSupervisor(job_name="AtlasM7KernelReapTest")
    job.create_contained_job()
    suspended = None
    try:
        suspended, _ = _spawn_contained(job, tmp_path, heartbeat)
        deadline = time.time() + 10
        while time.time() < deadline and not heartbeat.exists():
            time.sleep(0.1)
        assert heartbeat.exists()

        # A second process can open the object by name ONLY while a handle is held.
        opened = AtlasProcessSupervisor.open_existing_job("AtlasM7KernelReapTest")
        assert opened.query_containment_state().active_processes >= 1
        opened.close()

        job.close()  # last handle close: the tree is reaped and the object destroyed
        time.sleep(1.5)
        frozen = heartbeat.read_text(encoding="utf-8")
        time.sleep(1.5)
        assert heartbeat.read_text(encoding="utf-8") == frozen, (
            "the contained child kept running after the last Job Object handle closed: "
            "KILL_ON_JOB_CLOSE did not reap the tree"
        )
        with pytest.raises(RuntimeError):
            AtlasProcessSupervisor.open_existing_job("AtlasM7KernelReapTest")
    finally:
        if suspended is not None:
            try:
                terminate_process(suspended.process_handle)
            except Exception:  # noqa: BLE001
                pass
            close_handle(suspended.process_handle)


def test_real_kernel_reports_process_creation_time_used_by_the_launch_record(tmp_path):
    """The launch record's process_creation_time_utc comes from the kernel, not a guess."""
    job = AtlasProcessSupervisor(job_name="AtlasM7KernelCreationTimeTest")
    job.create_contained_job()
    before = datetime.datetime.now(datetime.timezone.utc)
    suspended = None
    try:
        script = _write_child(tmp_path)
        suspended = create_process_suspended(
            f'"{sys.executable}" "{script}" "{tmp_path / "hb_ct.txt"}"',
            application_name=sys.executable,
            create_no_window=True,
        )
        job.assign_suspended_process(suspended.process_handle)
        after = datetime.datetime.now(datetime.timezone.utc)
        reported = datetime.datetime.fromisoformat(suspended.process_creation_time_utc)
        assert reported.tzinfo is not None
        assert before - datetime.timedelta(seconds=5) <= reported <= after + datetime.timedelta(seconds=5)
        assert suspended.process_id >= 1
    finally:
        if suspended is not None:
            try:
                terminate_process(suspended.process_handle)
            except Exception:  # noqa: BLE001
                pass
            close_handle(suspended.process_handle)
        job.close()
