"""Atlas Unreal recovery composition root (Contract V1 §9/§10/§20; M7 Case-B path).

THIN COMPOSITION ROOT. This module **assembles** the already-reviewed production pieces and
records invocation provenance. It decides nothing:

* it does not classify recovery cases (the coordinator does);
* it does not publish receipts (the coordinator's store-gated publication does);
* it does not submit renders, mint authorizations or invent identities;
* it does not duplicate any coordinator policy;
* it never creates a Job Object or a supervisor of its own. The §9 quiescence source is the
  containment keeper's retained handle, handed in by the keeper, together with the attempt's
  authenticated launch record (F-DG-1). A call that supplies no launch-bound containment
  source is REFUSED rather than silently replaced by a fresh object.

Production journal root (MF-2): derived from the configured ``.uproject`` as
``<ProjectDir>/AtlasWitnessJournal`` and canonicalised (no symlink/junction escape, no
``Saved/`` placement). An operator-supplied arbitrary ``journal_root`` is deliberately NOT a
parameter of this module.

Usage (keeper drain edge):

    runtime = build_recovery_runtime(
        store_root=..., uproject=..., supervisor=keeper.supervisor,
        launch_record=keeper.launch_record, adapter=...)
    outcome = run_recovery_pass(runtime, atlas_job_id=..., now_utc=...)
"""
from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

from planning.unreal_adapter_production import create_production_adapter
from planning.unreal_containment_launch_record import (
    DEPLOYMENT_MODE_CONTAINED_JOB_OBJECT,
    ContainmentLaunchRecord,
)
from planning.unreal_containment_project import (
    ProjectContainmentContext,
    resolve_project_containment_context,
    verify_record_project_association,
)
from planning.unreal_render_job_store import AtlasRenderJobStore
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_recovery_coordinator import (
    RecoveryDecisionResult,
    UnrealRenderRecoveryCoordinator,
)

#: Probe path for the coordinator's receipt-first store probe. The per-attempt receipt is
#: resolved from ``store.receipts_dir/<atlas_job_id>__<attempt_ordinal>.json`` by the
#: coordinator itself; this path exists only because the constructor takes a probe store.
RECOVERY_RECEIPT_PROBE_FILENAME = "recovery_receipt_probe.json"

DEFAULT_COORDINATOR_ID = "atlas-recovery-composition-root"


class CompositionRefusedError(RuntimeError):
    """Raised when the composition root cannot assemble a sound recovery invocation."""


@dataclass(frozen=True)
class RecoveryRuntime:
    """The assembled (decided-nothing) recovery object graph plus its provenance."""

    store: AtlasRenderJobStore
    receipt_store: UnrealRenderReceiptStore
    coordinator: UnrealRenderRecoveryCoordinator
    context: ProjectContainmentContext
    launch_record: ContainmentLaunchRecord
    supervisor: Any
    deployment_mode: str
    adapter_source_tag: str

    def invocation_evidence(self) -> dict:
        """The recovery invocation's provenance record (no secrets)."""
        return {
            "record_kind": "recovery_invocation",
            "invocation_schema_version": 1,
            "composed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "deployment_mode": self.deployment_mode,
            "coordinator_id": self.coordinator.coordinator_id,
            "adapter_source_tag": self.adapter_source_tag,
            "launch_record_digest": self.launch_record.launch_record_digest,
            "launch_record_attempt": {
                "atlas_job_id": self.launch_record.atlas_job_id,
                "attempt_ordinal": self.launch_record.attempt_ordinal,
            },
            **self.context.snapshot(),
        }


def _adapter_source_tag(adapter: Any) -> str:
    """Best-effort adapter identity for the invocation record (never raises)."""
    try:
        tag = getattr(adapter, "_source_tag", None)
    except Exception:  # noqa: BLE001 - a double that explodes on attribute access is legal
        tag = None
    return tag or type(adapter).__name__


def build_recovery_runtime(
    *,
    store_root: str,
    uproject: str,
    supervisor: Any,
    launch_record: ContainmentLaunchRecord,
    adapter: Any = None,
    deployment_mode: str = DEPLOYMENT_MODE_CONTAINED_JOB_OBJECT,
    coordinator_id: str = DEFAULT_COORDINATOR_ID,
) -> RecoveryRuntime:
    """Assemble the recovery object graph from explicit, already-reviewed components.

    Every argument is supplied by the caller (the keeper owns the launch, the adapter and
    the store location); nothing is defaulted into existence here.
    """
    if supervisor is None or getattr(supervisor, "job_handle", None) is None:
        raise CompositionRefusedError(
            "refusing to compose recovery without the containment keeper's retained Job "
            "Object handle: a locally created Job Object can never satisfy §9 (F-DG-1)"
        )
    if launch_record is None:
        raise CompositionRefusedError(
            "refusing to compose recovery without the attempt's authenticated containment "
            "launch record: §9 quiescence would be unattributable (F-DG-1)"
        )
    if not isinstance(launch_record, ContainmentLaunchRecord):
        raise CompositionRefusedError(
            "launch_record must be a ContainmentLaunchRecord produced by the containment keeper"
        )

    context = resolve_project_containment_context(uproject, store_root)
    store = AtlasRenderJobStore(context.store_root)
    receipt_store = UnrealRenderReceiptStore(
        store.receipts_dir / RECOVERY_RECEIPT_PROBE_FILENAME
    )
    if adapter is None:
        # Fail closed: no synthetic adapter is ever substituted for the live transport.
        adapter = create_production_adapter()
    adapter_source_tag = _adapter_source_tag(adapter)

    coordinator = UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
        coordinator_id=coordinator_id,
        supervisor=supervisor,
        deployment_mode=deployment_mode,
        journal_root=context.journal_root,
        containment_launch_record=launch_record,
        containment_dir=context.containment_dir,
    )

    return RecoveryRuntime(
        store=store,
        receipt_store=receipt_store,
        coordinator=coordinator,
        context=context,
        launch_record=launch_record,
        supervisor=supervisor,
        deployment_mode=deployment_mode,
        adapter_source_tag=adapter_source_tag,
    )


def run_recovery_pass(
    runtime: RecoveryRuntime,
    *,
    atlas_job_id: Optional[str] = None,
    lease_token: int = 1,
    now_utc: Optional[datetime.datetime] = None,
    job_records: Optional[Sequence[Any]] = None,
) -> dict:
    """Run one recovery pass through the assembled coordinator and return evidence.

    The pass itself is the coordinator's; this function only calls it and packages the
    result with the invocation provenance the §8 evidence package requires.

    When ``job_records`` is supplied (the keeper supplies the record it launched), the
    project association of those records is verified against the assembled context and a
    refused association is recorded - the recovery pass still runs, but the refusal is
    first-class evidence rather than a silent pass.
    """
    per_job: list[dict] = []

    if job_records:
        # MF-2: the invocation must PROVE project <-> journal root <-> render record before
        # it may reconcile anything. A record whose attempt binding or project association
        # cannot be proven is refused here (fail closed, no adoption).
        for record in job_records:
            launch_ok, launch_reason = runtime.launch_record.verify_against_job_record(record)
            assoc_ok, assoc_reason, corroboration = verify_record_project_association(
                record, runtime.context, launch_record=runtime.launch_record
            )
            per_job.append(
                {
                    "atlas_job_id": getattr(record, "atlas_job_id", None),
                    "attempt_ordinal": getattr(record, "attempt_ordinal", None),
                    "launch_record_binding": "BOUND" if launch_ok else "REFUSED",
                    "launch_record_binding_reason": launch_reason,
                    "project_association": "BOUND" if assoc_ok else "REFUSED",
                    "project_association_reason": assoc_reason,
                    "project_association_corroboration": corroboration,
                }
            )
            if not launch_ok or not assoc_ok:
                raise CompositionRefusedError(
                    "refusing to reconcile "
                    f"{getattr(record, 'atlas_job_id', None)!r}: "
                    f"launch-record binding={launch_ok} ({launch_reason}) "
                    f"project association={assoc_ok} ({assoc_reason})"
                )

    if atlas_job_id is not None:
        decision = runtime.coordinator.reconcile_single_job(
            atlas_job_id, lease_token=lease_token, now_utc=now_utc
        )
    else:
        decision = runtime.coordinator.reconcile_all_non_terminal_jobs(
            lease_token=lease_token, now_utc=now_utc
        )

    evidence = runtime.invocation_evidence()
    evidence["lease_token"] = lease_token
    evidence["decisions"] = (
        [_decision_evidence(d) for d in decision]
        if isinstance(decision, list)
        else [_decision_evidence(decision)]
    )
    if per_job:
        evidence["job_bindings"] = per_job
    return evidence


def _decision_evidence(decision: RecoveryDecisionResult) -> dict:
    return {
        "atlas_job_id": decision.atlas_job_id,
        "case_classified": decision.case_classified,
        "lifecycle_state_before": decision.lifecycle_state_before.value,
        "lifecycle_state_after": decision.lifecycle_state_after.value,
        "recovery_status_before": decision.recovery_status_before.value,
        "recovery_status_after": decision.recovery_status_after.value,
        "repaired_from_receipt": decision.repaired_from_receipt,
        "receipt_reference": decision.receipt_reference,
        "failure_reason": decision.failure_reason,
    }


def write_invocation_evidence(runtime: RecoveryRuntime, evidence: dict) -> Path:
    """Persist recovery invocation evidence beside the containment provenance."""
    directory = Path(runtime.context.containment_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = directory / f"recovery_invocation_{stamp}.json"
    payload = json.dumps(evidence, sort_keys=True, indent=2, ensure_ascii=True)
    target.write_text(payload, encoding="utf-8")
    return target


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI is intentionally absent: recovery is invoked by the containment keeper."""
    raise CompositionRefusedError(
        "run_unreal_recovery.py is a composition root, not a standalone recovery authority: "
        "it is invoked by the containment keeper at the drain edge, with the keeper's retained "
        "Job Object handle and the attempt's launch record"
    )
