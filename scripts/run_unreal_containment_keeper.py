"""Atlas containment keeper — repository-owned executable containment authority (Option 4).

The keeper is the ONLY component that holds a Job Object handle, and therefore the only
component whose §9 quiescence observation is attempt-attributable. Its intrinsic authority
(Contract V1 §9/§10, M7 containment-provenance rung; MF-1) is exactly:

* launch Unreal (create-suspended -> assign to the Job Object -> resume);
* create and manage the Job Object, retaining its handle for the whole execution;
* assign the engine process tree to that object;
* record the launch identity durably, BEFORE the engine is resumed;
* observe ``ActiveProcesses`` on the retained handle;
* trigger recovery when ``ActiveProcesses == 0`` is observed, then release the handle.

The keeper MUST NOT own, and does not reference: submission authority, receipt publication,
authorization decisions, evidence-verification authority, Atlas job-state policy, or any
case classification. The recovery pass itself is the composition root's / coordinator's
(``scripts/run_unreal_recovery.py``), invoked at the drain edge with the keeper's own live
handle. The keeper may invoke the composition root; it never decides what recovery means.

Fail-closed semantics (never a synthetic success)
------------------------------------------------
* keeper crash before quiescence -> last handle close -> ``KILL_ON_JOB_CLOSE`` reaps the
  tree and destroys the object -> the attempt's containment provenance is gone -> recovery
  cannot prove §9 -> the job holds and eventually exhausts its deadline;
* missing/invalid/replaced attempt nonce -> no authenticated launch record is produced and
  the suspended engine is terminated before it can run;
* handle lost / accidentally closed -> same fail-closed behaviour;
* a second keeper claiming the same attempt -> the launch record already exists and is never
  overwritten: the second launch fails closed;
* a fresh, foreign, or re-created Job Object -> the §9 provenance conjuncts reject it, so
  no adoption can follow.
"""
from __future__ import annotations

import argparse
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from planning.unreal_containment_launch_record import (
    DEPLOYMENT_MODE_CONTAINED_JOB_OBJECT,
    ContainmentLaunchRecord,
    assert_nonce_belongs_to_record,
    build_launch_record,
    write_launch_record,
)
from planning.unreal_containment_project import (
    ProjectBindingError,
    ProjectContainmentContext,
    resolve_project_containment_context,
)
from planning.unreal_render_job_store import AtlasRenderJobStore, AtlasRenderJobStoreError
from scripts.run_unreal_supervisor import (
    AtlasProcessSupervisor,
    JobObjectContainmentState,
    close_handle,
    create_process_suspended,
    resume_process,
    terminate_process,
)

logger = logging.getLogger(__name__)

#: Source identity of this containment authority (recorded in every launch record).
KEEPER_SOURCE_IDENTITY = "scripts/run_unreal_containment_keeper.py"

DEFAULT_DRAIN_POLL_SECONDS = 0.25
DEFAULT_DRAIN_TIMEOUT_SECONDS = 24 * 60 * 60


class ContainmentKeeperRefusedError(RuntimeError):
    """Raised whenever the keeper must fail closed instead of proceeding."""


class ContainmentKeeper:
    """Repository-owned containment keeper: launch contained, retain, observe, trigger.

    The recovery trigger is injected so the keeper can be driven deterministically without
    launching an engine; the default trigger invokes the recovery composition root
    (``scripts/run_unreal_recovery.py``) with the keeper's retained handle.
    """

    def __init__(
        self,
        *,
        store_root: str,
        uproject: str,
        atlas_job_id: str,
        attempt_ordinal: int,
        job_name: Optional[str] = None,
        keeper_instance_id: Optional[str] = None,
        supervisor: Optional[AtlasProcessSupervisor] = None,
        recovery_trigger: Optional[Callable[["ContainmentKeeper"], dict]] = None,
        poll_interval_seconds: float = DEFAULT_DRAIN_POLL_SECONDS,
        drain_timeout_seconds: float = DEFAULT_DRAIN_TIMEOUT_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        deployment_mode: str = DEPLOYMENT_MODE_CONTAINED_JOB_OBJECT,
    ) -> None:
        if deployment_mode != DEPLOYMENT_MODE_CONTAINED_JOB_OBJECT:
            raise ContainmentKeeperRefusedError(
                f"the keeper only exists for {DEPLOYMENT_MODE_CONTAINED_JOB_OBJECT}; "
                f"{deployment_mode!r} has no containment to retain (fail closed)"
            )
        if not isinstance(attempt_ordinal, int) or isinstance(attempt_ordinal, bool) \
                or attempt_ordinal < 1:
            raise ContainmentKeeperRefusedError("attempt_ordinal must be a positive integer >= 1")

        self.context: ProjectContainmentContext = resolve_project_containment_context(
            uproject, store_root
        )
        self.store_root = self.context.store_root
        self.store = AtlasRenderJobStore(self.context.store_root)
        self.atlas_job_id = atlas_job_id
        self.attempt_ordinal = attempt_ordinal
        self.deployment_mode = deployment_mode
        self.poll_interval_seconds = float(poll_interval_seconds)
        self.drain_timeout_seconds = float(drain_timeout_seconds)
        self._clock = clock
        self._sleep = sleep
        self._recovery_trigger = recovery_trigger
        self.job_name = job_name or f"AtlasContainment-{atlas_job_id}-attempt{attempt_ordinal}"
        self.keeper_identity = (
            f"{KEEPER_SOURCE_IDENTITY}#{keeper_instance_id or uuid.uuid4().hex[:12]}"
        )
        self.supervisor = supervisor or AtlasProcessSupervisor(job_name=self.job_name)
        self.launch_record: Optional[ContainmentLaunchRecord] = None
        self.engine_pid: Optional[int] = None
        self.drain_observed = False
        self.recovery_evidence: Optional[dict] = None

    # -- authority: launch -------------------------------------------------
    def job_record(self) -> Any:
        """Load the durable Atlas render record for this attempt (read-only)."""
        try:
            record = self.store.load(self.atlas_job_id)
        except (AtlasRenderJobStoreError, OSError) as exc:
            raise ContainmentKeeperRefusedError(
                f"durable render record for {self.atlas_job_id!r} is unavailable: {exc} "
                "(fail closed)"
            ) from exc
        if getattr(record, "attempt_ordinal", None) != self.attempt_ordinal:
            raise ContainmentKeeperRefusedError(
                f"durable render record attempt_ordinal {getattr(record, 'attempt_ordinal', None)} "
                f"does not match this keeper's attempt {self.attempt_ordinal} (fail closed)"
            )
        return record

    def _containment_state(self) -> JobObjectContainmentState:
        if self.supervisor.job_handle is None:
            raise ContainmentKeeperRefusedError(
                "the retained Job Object handle is missing: containment provenance is lost "
                "(fail closed)"
            )
        return self.supervisor.query_containment_state()

    def launch(
        self,
        *,
        attempt_nonce: str,
        command_line: str,
        application_name: Optional[str] = None,
        working_directory: Optional[str] = None,
        create_no_window: bool = True,
    ) -> ContainmentLaunchRecord:
        """Create the Job Object, launch the engine suspended, record, then resume.

        Order is mandated (Contract V1 §9 / §10): ``CreateJobObjectW`` ->
        ``KILL_ON_JOB_CLOSE`` -> ``CreateProcess(CREATE_SUSPENDED)`` ->
        ``AssignProcessToJobObject`` -> durable launch record -> ``ResumeThread``.
        The attempt nonce is accepted ONLY here, in-process, and is never persisted or
        logged; it must be the durable record's own nonce.
        """
        record = self.job_record()
        # MF-3 custody: no record-derived authority without the record's own nonce.
        assert_nonce_belongs_to_record(attempt_nonce, record)

        self.supervisor.create_contained_job()
        suspended = None
        try:
            suspended = create_process_suspended(
                command_line,
                application_name=application_name,
                working_directory=working_directory,
                create_no_window=create_no_window,
            )
            self.supervisor.assign_suspended_process(suspended.process_handle)
            state = self._containment_state()
            if state.total_processes < 1:
                raise ContainmentKeeperRefusedError(
                    "the Job Object reports TotalProcesses == 0 immediately after the engine "
                    "was assigned: containment was not established (fail closed)"
                )
            if not state.kill_on_job_close:
                raise ContainmentKeeperRefusedError(
                    "the Job Object is not configured with KILL_ON_JOB_CLOSE (fail closed)"
                )

            self.engine_pid = suspended.process_id
            launch_record = build_launch_record(
                atlas_job_id=self.atlas_job_id,
                attempt_ordinal=self.attempt_ordinal,
                attempt_nonce=attempt_nonce,
                engine_pid=suspended.process_id,
                process_creation_time_utc=suspended.process_creation_time_utc,
                launch_composition_processes=int(state.total_processes),
                project_identity=self.context.project_dir,
                uproject_digest=self.context.uproject_digest,
                keeper_identity=self.keeper_identity,
                job_identity_descriptor=self.job_name,
                # Never fabricated: the engine mints its session identity, which reaches
                # Atlas later through the engine witness journal.
                editor_session_id=None,
            )
            write_launch_record(
                self._containment_dir(),
                launch_record,
                attempt_nonce=attempt_nonce,
            )
            self.launch_record = launch_record
            # Contract V1 §10: the launch identity is durable BEFORE the engine resumes.
            resume_process(suspended.thread_handle)
        except Exception:
            self._abandon_launch(suspended)
            raise
        finally:
            if suspended is not None:
                close_handle(suspended.thread_handle)

        logger.info(
            "containment launch recorded: atlas_job_id=%s attempt=%s pid=%s composition=%s "
            "launch_record_digest=%s",
            self.atlas_job_id,
            self.attempt_ordinal,
            self.engine_pid,
            self.launch_record.launch_composition_processes,
            self.launch_record.launch_record_digest,
        )
        return self.launch_record

    def _abandon_launch(self, suspended: Any) -> None:
        """Fail closed: no uncontained/unrecorded engine may survive a failed launch."""
        if suspended is not None:
            try:
                terminate_process(suspended.process_handle)
            except Exception:  # noqa: BLE001 - best-effort reap before closing the object
                logger.warning("failed to terminate the suspended engine during fail-closed cleanup")
        try:
            self.supervisor.close()
        except Exception:  # noqa: BLE001
            logger.warning("failed to close the Job Object during fail-closed cleanup")

    def _containment_dir(self) -> Path:
        return Path(self.context.containment_dir)

    # -- authority: observe ------------------------------------------------
    def observe_active_processes(self) -> int:
        """Read the kernel's ActiveProcesses count for the retained object."""
        return int(self._containment_state().active_processes)

    def wait_for_drain(self, timeout_seconds: Optional[float] = None) -> bool:
        """Wait until the retained object reports exactly 0 active processes.

        Returns True only when the drain was observed on the keeper's own retained handle
        while it still owned it. A timeout returns False (the caller fails closed): no
        recovery is triggered, no receipt can follow, and the handle is deliberately NOT
        released here - containment stays intact, and if the keeper process then exits,
        ``KILL_ON_JOB_CLOSE`` reaps the tree (fail closed, never a synthetic completion).
        """
        if self.supervisor.job_handle is None:
            raise ContainmentKeeperRefusedError(
                "cannot observe drain: the retained Job Object handle is missing (fail closed)"
            )
        deadline = self._clock() + (
            self.drain_timeout_seconds if timeout_seconds is None else float(timeout_seconds)
        )
        while True:
            if self.observe_active_processes() == 0:
                self.drain_observed = True
                return True
            if self._clock() >= deadline:
                return False
            self._sleep(self.poll_interval_seconds)

    # -- authority: trigger recovery at the drain edge ---------------------
    def trigger_recovery(self) -> dict:
        """Invoke the recovery invocation with the retained handle, then release it.

        Only reachable after a drain observed on this keeper's own handle: the coordinator
        evaluates the SAME Job Object the engine was launched in, so Atlas restarts are
        irrelevant to quiescence ownership.
        """
        if self.launch_record is None:
            raise ContainmentKeeperRefusedError(
                "cannot trigger recovery: no authenticated launch record exists (fail closed)"
            )
        if not self.drain_observed:
            raise ContainmentKeeperRefusedError(
                "cannot trigger recovery: the retained Job Object has not been observed at "
                "0 active processes (fail closed)"
            )
        if self.supervisor.job_handle is None:
            raise ContainmentKeeperRefusedError(
                "cannot trigger recovery: the retained Job Object handle was lost; the "
                "attempt's containment is unprovable (fail closed)"
            )
        trigger = self._recovery_trigger or default_recovery_trigger
        self.recovery_evidence = trigger(self)
        return self.recovery_evidence

    def release(self) -> None:
        """Release the retained handle (last close reaps the tree under KILL_ON_JOB_CLOSE)."""
        self.supervisor.close()

    def run(
        self,
        *,
        attempt_nonce: str,
        command_line: str,
        application_name: Optional[str] = None,
        working_directory: Optional[str] = None,
        drain_timeout_seconds: Optional[float] = None,
    ) -> dict:
        """The keeper's whole life: launch contained, wait for drain, trigger, release."""
        self.launch(
            attempt_nonce=attempt_nonce,
            command_line=command_line,
            application_name=application_name,
            working_directory=working_directory,
        )
        drained = self.wait_for_drain(drain_timeout_seconds)
        if not drained:
            raise ContainmentKeeperRefusedError(
                "the contained tree did not drain before the keeper's deadline; recovery is not "
                "triggered and the containment fails closed (no synthetic success)"
            )
        try:
            evidence = self.trigger_recovery()
        finally:
            self.release()
        return {
            "atlas_job_id": self.atlas_job_id,
            "attempt_ordinal": self.attempt_ordinal,
            "engine_pid": self.engine_pid,
            "keeper_identity": self.keeper_identity,
            "launch_record_digest": self.launch_record.launch_record_digest,
            "drain_observed": self.drain_observed,
            "invocation_evidence_path": (
                evidence.get("invocation_evidence_path") if isinstance(evidence, dict) else None
            ),
            "recovery_evidence": evidence,
        }


def default_recovery_trigger(keeper: ContainmentKeeper) -> dict:
    """Invoke the recovery composition root with the keeper's retained handle.

    The invocation evidence is DURABLY persisted (red-team cleanup item 1): the drain-edge
    path must leave an artifact beside the containment provenance, not merely return it in
    memory. Persistence uses the composition root's own writer - the keeper acquires no
    classification, receipt or submission authority from doing so.

    A failed write is never swallowed: the trigger raises, so a keeper run cannot report
    success for an invocation whose provenance was not recorded.

    Imported lazily so the keeper itself stays free of recovery policy, and so a keeper
    process that never drains never imports the recovery path at all.
    """
    from scripts.run_unreal_recovery import (
        build_recovery_runtime,
        run_recovery_pass,
        write_invocation_evidence,
    )

    runtime = build_recovery_runtime(
        store_root=keeper.store_root,
        uproject=keeper.context.uproject_path,
        supervisor=keeper.supervisor,
        launch_record=keeper.launch_record,
        deployment_mode=keeper.deployment_mode,
    )
    job_record = keeper.job_record()
    evidence = run_recovery_pass(
        runtime,
        atlas_job_id=keeper.atlas_job_id,
        job_records=[job_record],
    )
    evidence_path = write_invocation_evidence(runtime, evidence)
    evidence["invocation_evidence_path"] = str(evidence_path)
    logger.info("recovery invocation evidence persisted: %s", evidence_path)
    return evidence


# ---------------------------------------------------------------------------
# CLI (the launcher boundary)
# ---------------------------------------------------------------------------
def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Atlas containment keeper: launch Unreal inside a KILL_ON_JOB_CLOSE Job Object, "
            "retain the handle, and trigger recovery at the drain edge."
        )
    )
    parser.add_argument("--uproject", required=True, help="configured .uproject (derives the journal root)")
    parser.add_argument("--store-root", required=True, help="durable Atlas render-job store root")
    parser.add_argument("--atlas-job-id", required=True)
    parser.add_argument("--attempt-ordinal", required=True, type=int)
    parser.add_argument("--engine-command", required=True, help="engine command line to launch contained")
    parser.add_argument("--engine-executable", default=None, help="optional lpApplicationName")
    parser.add_argument("--working-directory", default=None)
    parser.add_argument("--job-name", default=None, help="Job Object name (lookup metadata only)")
    parser.add_argument("--drain-timeout-seconds", type=float, default=DEFAULT_DRAIN_TIMEOUT_SECONDS)
    parser.add_argument("--poll-interval-seconds", type=float, default=DEFAULT_DRAIN_POLL_SECONDS)
    parser.add_argument("--keeper-instance-id", default=None)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Launcher entrypoint. The attempt nonce is NEVER taken from argv/env.

    It is read from the durable render record of the authorized attempt and handed to the
    keeper in-process, per the MF-3 custody rule.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_arg_parser().parse_args(argv)
    keeper = ContainmentKeeper(
        store_root=args.store_root,
        uproject=args.uproject,
        atlas_job_id=args.atlas_job_id,
        attempt_ordinal=args.attempt_ordinal,
        job_name=args.job_name,
        keeper_instance_id=args.keeper_instance_id,
        poll_interval_seconds=args.poll_interval_seconds,
        drain_timeout_seconds=args.drain_timeout_seconds,
    )
    attempt_nonce = keeper.job_record().attempt_nonce
    outcome = keeper.run(
        attempt_nonce=attempt_nonce,
        command_line=args.engine_command,
        application_name=args.engine_executable,
        working_directory=args.working_directory,
        drain_timeout_seconds=args.drain_timeout_seconds,
    )
    print(
        "keeper complete: atlas_job_id={job} attempt={attempt} pid={pid} "
        "launch_record_digest={digest} drain_observed={drained}".format(
            job=outcome["atlas_job_id"],
            attempt=outcome["attempt_ordinal"],
            pid=outcome["engine_pid"],
            digest=outcome["launch_record_digest"],
            drained=outcome["drain_observed"],
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - entrypoint
    raise SystemExit(main())
