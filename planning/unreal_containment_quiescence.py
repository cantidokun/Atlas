"""Contract V1 §9 containment quiescence WITH launch-object provenance (F-DG-1 closure).

``scripts/run_unreal_supervisor.py::evaluate_process_quiescence`` answers only "does this
handle report ``ActiveProcesses == 0``". That is satisfiable by a *fresh never-used* Job
Object while a different object still holds live processes — the F-DG-1 vacuity attack
(empirically reproduced: a fresh object reports ``TotalProcesses == 0`` and
``ActiveProcesses == 0``, so the attempt-unbound predicate returns ``is_quiescent=True``).

This module implements the §9 predicate as the contract now defines
``JobObjectHandleValid``, i.e. ALL of:

1. **Launch provenance** — the attempt's durable, HMAC-authenticated containment launch
   record exists (written by the keeper before the engine was resumed) and verifies.
2. **Retention** — the queried supervisor is the keeper's retained handle.
3. **Kernel containment configuration** — ``KILL_ON_JOB_CLOSE`` read back set, breakaway
   disabled.
4. **Kernel counter consistency** — ``TotalProcesses >= recorded launch composition >= 1``
   and ``ActiveProcesses == 0``.
5. **Attempt binding** — the launch record agrees with the durable render record on
   ``atlas_job_id``, ``attempt_ordinal`` and the authenticated attempt nonce.

Any conjunct that cannot be established makes quiescence FALSE (fail closed), so terminal
artifacts are never inspected or adopted and the job holds in
``WAITING_FOR_ENGINE_QUIESCENCE``. ``TotalTerminatedProcesses`` is deliberately unused: it
counts processes reaped through the object, not externally terminated ones.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple

from scripts.run_unreal_supervisor import (
    AtlasProcessSupervisor,
    JobObjectContainmentState,
    evaluate_process_quiescence,
)

DEPLOYMENT_MODE_CONTAINED = "CONTAINED_JOB_OBJECT"
DEPLOYMENT_MODE_UNCONTAINED = "UNCONTAINED_ATTACHED"

#: Reason prefixes (stable, asserted by tests).
NO_LAUNCH_PROVENANCE_PREFIX = "JobObjectHandleValid == FALSE:"
KERNEL_EVIDENCE_PREFIX = "Job Object kernel evidence rejected:"


@dataclass(frozen=True)
class ContainmentQuiescenceResult:
    """Outcome of the provenance-bound §9 predicate.

    Field names ``is_quiescent`` / ``active_process_count`` / ``deployment_mode`` /
    ``reason`` are the ones the coordinator's Case-K path already consumes; the extra
    fields carry the §9 evidence for the recovery invocation record.
    """

    is_quiescent: bool
    active_process_count: int
    deployment_mode: str
    reason: str
    provenance_verified: bool = False
    total_processes: int = -1
    kill_on_job_close: bool = False
    breakaway_disabled: bool = False
    launch_record_digest: Optional[str] = None
    kernel_evidence: Mapping[str, Any] = field(default_factory=dict)

    def evidence(self) -> dict:
        """Recovery-invocation evidence material for this predicate evaluation."""
        return {
            "deployment_mode": self.deployment_mode,
            "is_quiescent": self.is_quiescent,
            "provenance_verified": self.provenance_verified,
            "active_processes": self.active_process_count,
            "total_processes": self.total_processes,
            "kill_on_job_close": self.kill_on_job_close,
            "breakaway_disabled": self.breakaway_disabled,
            "launch_record_digest": self.launch_record_digest,
            "reason": self.reason,
            **dict(self.kernel_evidence),
        }


def _refuse(mode: str, reason: str, *, active: int = -1, total: int = -1,
            kill_on_close: bool = False, breakaway_disabled: bool = False,
            launch_record_digest: Optional[str] = None,
            kernel_evidence: Optional[Mapping[str, Any]] = None) -> ContainmentQuiescenceResult:
    return ContainmentQuiescenceResult(
        is_quiescent=False,
        active_process_count=active,
        deployment_mode=mode,
        reason=reason,
        provenance_verified=False,
        total_processes=total,
        kill_on_job_close=kill_on_close,
        breakaway_disabled=breakaway_disabled,
        launch_record_digest=launch_record_digest,
        kernel_evidence=dict(kernel_evidence or {}),
    )


def _kernel_state_of(supervisor: Any) -> Tuple[Optional[JobObjectContainmentState], str]:
    """Read the kernel accounting/limits surface, tolerating legacy fake supervisors."""
    try:
        state = supervisor.query_containment_state()
    except Exception as exc:  # noqa: BLE001 - fail closed on any kernel read failure
        return None, f"{KERNEL_EVIDENCE_PREFIX} query failed ({exc.__class__.__name__}: {exc})"
    if not isinstance(state, JobObjectContainmentState):
        return None, (
            f"{KERNEL_EVIDENCE_PREFIX} supervisor does not expose a real "
            "JobObjectContainmentState (query_containment_state() returned "
            f"{type(state).__name__})"
        )
    return state, ""


def evaluate_containment_quiescence(
    supervisor: Optional[AtlasProcessSupervisor],
    deployment_mode: str,
    *,
    launch_record: Any = None,
    job_record: Any = None,
    containment_dir: Optional[str] = None,
) -> ContainmentQuiescenceResult:
    """Evaluate Contract V1 §9 quiescence including launch-object provenance.

    ``launch_record`` is normally the keeper's own record object (Option 4: recovery runs
    in-process with the retained handle). When it is not supplied but ``containment_dir``
    and ``job_record`` are, the record is resolved and authenticated from the durable
    containment store — the same authentication chain, so a caller cannot bypass it by
    passing a record either.

    ``job_record`` MUST be the durable ``AtlasRenderJobRecord`` of the job being
    reconciled: without it the attempt binding cannot be proven and the predicate fails
    closed.
    """
    normalized_mode = deployment_mode.upper().strip() if isinstance(deployment_mode, str) else ""

    if normalized_mode == DEPLOYMENT_MODE_UNCONTAINED:
        # Contract V1 §9.281-284: unchanged fail-closed semantics; the reason text is
        # deliberately identical to the attempt-unbound predicate.
        return _refuse(
            DEPLOYMENT_MODE_UNCONTAINED,
            evaluate_process_quiescence(None, DEPLOYMENT_MODE_UNCONTAINED).reason,
        )

    if normalized_mode != DEPLOYMENT_MODE_CONTAINED:
        return _refuse(
            deployment_mode if isinstance(deployment_mode, str) else str(deployment_mode),
            f"Unknown deployment mode: {deployment_mode!r}",
        )

    if supervisor is None or getattr(supervisor, "job_handle", None) is None:
        return _refuse(
            DEPLOYMENT_MODE_CONTAINED,
            "Supervisor or Job Object handle is missing/invalid",
        )

    # Conjunct 1 + 5: the attempt's authenticated launch record, bound to this record.
    resolved = launch_record
    resolution_reason = ""
    if resolved is None and containment_dir is not None and job_record is not None:
        from planning.unreal_containment_launch_record import verify_launch_record_for_job

        resolved, resolution_reason = verify_launch_record_for_job(containment_dir, job_record)

    if resolved is None:
        reason = resolution_reason or (
            "no attempt-bound containment launch record was supplied for this attempt"
        )
        return _refuse(
            DEPLOYMENT_MODE_CONTAINED,
            f"{NO_LAUNCH_PROVENANCE_PREFIX} {reason}",
        )

    if getattr(resolved, "deployment_mode", None) != DEPLOYMENT_MODE_CONTAINED:
        return _refuse(
            DEPLOYMENT_MODE_CONTAINED,
            f"{NO_LAUNCH_PROVENANCE_PREFIX} launch record deployment_mode "
            f"{getattr(resolved, 'deployment_mode', None)!r} is not {DEPLOYMENT_MODE_CONTAINED}",
        )

    launch_record_digest = getattr(resolved, "launch_record_digest", None)

    if job_record is None:
        return _refuse(
            DEPLOYMENT_MODE_CONTAINED,
            f"{NO_LAUNCH_PROVENANCE_PREFIX} no durable render record supplied: the launch "
            "record cannot be bound to the attempt",
            launch_record_digest=launch_record_digest,
        )

    binding_ok, binding_reason = resolved.verify_against_job_record(job_record)
    if not binding_ok:
        return _refuse(
            DEPLOYMENT_MODE_CONTAINED,
            f"{NO_LAUNCH_PROVENANCE_PREFIX} {binding_reason}",
            launch_record_digest=launch_record_digest,
        )

    recorded_composition = getattr(resolved, "launch_composition_processes", None)
    if isinstance(recorded_composition, bool) or not isinstance(recorded_composition, int) \
            or recorded_composition < 1:
        return _refuse(
            DEPLOYMENT_MODE_CONTAINED,
            f"{NO_LAUNCH_PROVENANCE_PREFIX} launch record declares an invalid launch "
            f"composition ({recorded_composition!r}); a containment that contained nothing "
            "is not a containment",
            launch_record_digest=launch_record_digest,
        )

    # Conjunct 3 + 4: kernel facts about the object the retained handle refers to.
    state, kernel_error = _kernel_state_of(supervisor)
    if state is None:
        return _refuse(
            DEPLOYMENT_MODE_CONTAINED,
            kernel_error,
            launch_record_digest=launch_record_digest,
        )

    kernel_evidence = {
        "kernel_total_processes": state.total_processes,
        "kernel_total_terminated_processes": state.total_terminated_processes,
        "recorded_launch_composition": recorded_composition,
        "limit_flags": state.limit_flags,
        "job_identity_descriptor": getattr(resolved, "job_identity_descriptor", None),
    }

    if not state.kill_on_job_close:
        return _refuse(
            DEPLOYMENT_MODE_CONTAINED,
            f"{KERNEL_EVIDENCE_PREFIX} JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE is not configured "
            f"(limit_flags={state.limit_flags:#x}); the object's zero would not prove a zero",
            active=state.active_processes, total=state.total_processes,
            kill_on_close=False, breakaway_disabled=state.breakaway_disabled,
            launch_record_digest=launch_record_digest, kernel_evidence=kernel_evidence,
        )

    if not state.breakaway_disabled:
        return _refuse(
            DEPLOYMENT_MODE_CONTAINED,
            f"{KERNEL_EVIDENCE_PREFIX} breakaway is enabled (limit_flags={state.limit_flags:#x}); "
            "a contained launch must not be able to leave the object",
            active=state.active_processes, total=state.total_processes,
            kill_on_close=True, breakaway_disabled=False,
            launch_record_digest=launch_record_digest, kernel_evidence=kernel_evidence,
        )

    if state.total_processes < recorded_composition:
        return _refuse(
            DEPLOYMENT_MODE_CONTAINED,
            f"{KERNEL_EVIDENCE_PREFIX} TotalProcesses={state.total_processes} is below the recorded "
            f"launch composition {recorded_composition}: this object did not contain this "
            "attempt's process tree (a fresh/foreign object reports TotalProcesses == 0)",
            active=state.active_processes, total=state.total_processes,
            kill_on_close=True, breakaway_disabled=True,
            launch_record_digest=launch_record_digest, kernel_evidence=kernel_evidence,
        )

    if state.active_processes != 0:
        return _refuse(
            DEPLOYMENT_MODE_CONTAINED,
            f"Job Object still has {state.active_processes} active processes",
            active=state.active_processes, total=state.total_processes,
            kill_on_close=True, breakaway_disabled=True,
            launch_record_digest=launch_record_digest, kernel_evidence=kernel_evidence,
        )

    return ContainmentQuiescenceResult(
        is_quiescent=True,
        active_process_count=0,
        deployment_mode=DEPLOYMENT_MODE_CONTAINED,
        reason=(
            "Job Object contains exactly 0 active processes over the attempt's retained launch "
            "object (KILL_ON_JOB_CLOSE, breakaway disabled, "
            f"TotalProcesses={state.total_processes} >= recorded composition {recorded_composition})"
        ),
        provenance_verified=True,
        total_processes=state.total_processes,
        kill_on_job_close=True,
        breakaway_disabled=True,
        launch_record_digest=launch_record_digest,
        kernel_evidence=kernel_evidence,
    )
