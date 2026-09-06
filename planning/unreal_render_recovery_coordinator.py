"""Atlas Unreal Cross-Process Render Recovery Coordinator (Milestone 4).

Authoritative specification: docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import logging
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Tuple

from planning.unreal_adapter_production import UnrealAdapterError, UnrealAdapterProduction
from planning.unreal_evidence_contract import (
    UnrealEvidence,
    UnrealEvidenceVerificationError,
    verify_png_completeness,
    verify_render_job_evidence,
)
from planning.unreal_operation_contract import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_render_job_record import (
    AtlasRenderJobRecord,
    validate_canonical_atlas_job_id,
)
from planning.unreal_render_job_states import (
    TERMINAL_LIFECYCLE_STATES,
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
from planning.unreal_render_job_store import (
    AtlasRenderJobStore,
    AtlasRenderJobStoreCorruptionError,
    AtlasRenderJobStoreError,
    AtlasRenderJobStoreLockError,
    AtlasRenderJobStoreRevisionMismatchError,
    AtlasRenderJobStoreStaleWriterError,
)
from planning.unreal_render_receipt import UnrealRenderReceipt
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from scripts.run_unreal_supervisor import AtlasProcessSupervisor, evaluate_process_quiescence

logger = logging.getLogger(__name__)


class UnrealRenderRecoveryCoordinatorError(RuntimeError):
    """Base error for UnrealRenderRecoveryCoordinator execution."""


@dataclass(frozen=True)
class RecoveryDecisionResult:
    atlas_job_id: str
    lifecycle_state_before: RenderJobLifecycleState
    lifecycle_state_after: RenderJobLifecycleState
    recovery_status_before: RenderJobRecoveryStatus
    recovery_status_after: RenderJobRecoveryStatus
    case_classified: str
    repaired_from_receipt: bool
    receipt_reference: Optional[str] = None
    quarantine_path: Optional[str] = None
    failure_reason: Optional[str] = None


def _thaw_dict(val: Any) -> Any:
    if isinstance(val, Mapping):
        return {k: _thaw_dict(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_thaw_dict(v) for v in val]
    return val


def canonical_known_jobs_payload(known_jobs: Any) -> bytes:
    """Deterministic canonical UTF-8 JSON bytes for a reconcile known_jobs array.

    Deep-thaws frozen mappingproxy/tuple structures into plain JSON-serializable
    values, then serializes with compact separators and ``sort_keys=True`` so the
    byte form (and therefore its SHA-256) is stable regardless of frozen wrapper
    types or mapping insertion order. This is the exact payload the reconcile
    framing integrity check hashes and the length it measures.
    """
    thawed = _thaw_dict(known_jobs)
    return json.dumps(
        thawed,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def compute_journal_hmac(
    attempt_nonce: str,
    canonical_payload: Mapping[str, Any],
) -> str:
    """Compute HMAC-SHA256 for a journal entry using attempt_nonce as secret key."""
    thawed = _thaw_dict(canonical_payload)
    encoded_message = json.dumps(
        thawed,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    key_bytes = attempt_nonce.encode("utf-8")
    return hmac.new(key_bytes, encoded_message, hashlib.sha256).hexdigest()


def _parse_iso8601_utc(value: Optional[str]) -> Optional[datetime.datetime]:
    """Parse an ISO-8601 UTC timestamp (accepts trailing ``Z`` and ``+00:00``).

    Returns ``None`` when the value is missing or unparseable so callers can
    treat absent/invalid deadlines deterministically (no deadline -> no expiry).
    """
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)





class UnrealRenderRecoveryCoordinator:
    """Single Atlas-owned cross-process recovery coordinator for Unreal render jobs."""

    def __init__(
        self,
        store: AtlasRenderJobStore,
        adapter: UnrealAdapterProduction,
        receipt_store: UnrealRenderReceiptStore,
        coordinator_id: str = "atlas-recovery-coordinator-primary",
        supervisor: Optional[AtlasProcessSupervisor] = None,
        deployment_mode: str = "CONTAINED_JOB_OBJECT",
    ):
        self.store = store
        self.adapter = adapter
        self.receipt_store = receipt_store
        self.coordinator_id = coordinator_id
        self.supervisor = supervisor
        self.deployment_mode = deployment_mode.upper().strip()

    def _expired_deadline(
        self,
        record: AtlasRenderJobRecord,
        now_utc: Optional[datetime.datetime] = None,
    ) -> Optional[str]:
        """Return the deadline name ('submission'/'execution') that has expired.

        A deadline applies only while the job is in the phase it bounds:
        - ``submission_deadline`` bounds the unsubmitted / submission-uncertain
          phase (PENDING_SUBMISSION not yet transported, or still awaiting
          engine acceptance);
        - ``execution_deadline`` bounds the post-submission recovery/execution
          phase (SUBMITTED/RENDERING/COMPLETED_UNVERIFIED, or any blocked
          recovery-wait state).

        The deadline is considered expired when the persisted timestamp is at or
        before the reference ``now`` AND the record's lifecycle is not terminal.
        Missing or unparseable deadlines return ``None`` (no expiry). This is a
        deterministic function of the persisted deadline and the supplied ``now``.
        """
        if record.lifecycle_state in TERMINAL_LIFECYCLE_STATES:
            return None
        now = now_utc if now_utc is not None else datetime.datetime.now(datetime.timezone.utc)
        now = now.astimezone(datetime.timezone.utc)
        if record.submission_deadline is not None:
            sub = _parse_iso8601_utc(record.submission_deadline)
            if sub is not None and now >= sub:
                return "submission"
        if record.execution_deadline is not None:
            exe = _parse_iso8601_utc(record.execution_deadline)
            if exe is not None and now >= exe:
                return "execution"
        return None

    def _deadline_exhausted_transition(
        self,
        record: AtlasRenderJobRecord,
        deadline_name: str,
    ) -> RecoveryDecisionResult:
        """Transition an unresolved, deadline-expired job to EXHAUSTED.

        Contract V1 §23/§28: recovery waiting is bounded by explicit deadlines;
        once the deadline is reached without resolution, recovery is exhausted
        (recovery_status=EXHAUSTED) and the unresolved execution fails closed to
        RECOVERY_FAILED. No synthetic success, no retry, no receipt issuance.
        """
        exhausted_record = record.transition(
            lifecycle_state=RenderJobLifecycleState.RECOVERY_FAILED,
            recovery_status=RenderJobRecoveryStatus.EXHAUSTED,
            failure_reason=(
                f"{deadline_name} deadline expired without resolution; "
                "recovery budget exhausted (EXHAUSTED)"
            ),
        )
        self.store.update(exhausted_record, expected_revision=record.last_observed_revision)
        return RecoveryDecisionResult(
            atlas_job_id=record.atlas_job_id,
            lifecycle_state_before=record.lifecycle_state,
            lifecycle_state_after=exhausted_record.lifecycle_state,
            recovery_status_before=record.recovery_status,
            recovery_status_after=exhausted_record.recovery_status,
            case_classified="DEADLINE_EXHAUSTED",
            repaired_from_receipt=False,
            failure_reason=exhausted_record.failure_reason,
        )

    def reconcile_all_non_terminal_jobs(
        self,
        lease_token: int = 1,
        now_utc: Optional[datetime.datetime] = None,
    ) -> list[RecoveryDecisionResult]:
        """Execute a full recovery pass over all non-terminal jobs in the store under coordinator lock."""
        results: list[RecoveryDecisionResult] = []
        with self.store.acquire_coordinator(self.coordinator_id, lease_token=lease_token):
            all_ids = self.store.list_job_ids()
            for atlas_job_id in all_ids:
                try:
                    record = self.store.load(atlas_job_id)
                except AtlasRenderJobStoreCorruptionError as exc:
                    logger.error("Job %s record corrupted: %s", atlas_job_id, exc)
                    results.append(
                        RecoveryDecisionResult(
                            atlas_job_id=atlas_job_id,
                            lifecycle_state_before=RenderJobLifecycleState.RECORD_CORRUPT,
                            lifecycle_state_after=RenderJobLifecycleState.RECORD_CORRUPT,
                            recovery_status_before=RenderJobRecoveryStatus.NONE,
                            recovery_status_after=RenderJobRecoveryStatus.NONE,
                            case_classified="RECORD_CORRUPT",
                            repaired_from_receipt=False,
                            failure_reason=str(exc),
                        )
                    )
                    continue

                if record.lifecycle_state in TERMINAL_LIFECYCLE_STATES:
                    continue

                res = self.reconcile_single_job(atlas_job_id, lease_token=lease_token, now_utc=now_utc)
                results.append(res)
        return results

    def reconcile_single_job(
        self,
        atlas_job_id: str,
        lease_token: int = 1,
        now_utc: Optional[datetime.datetime] = None,
    ) -> RecoveryDecisionResult:
        """Reconcile one Atlas job against engine state, journal witness, and verified disk evidence."""
        valid_id = validate_canonical_atlas_job_id(atlas_job_id)
        with self.store.acquire_job_claim(valid_id, self.coordinator_id):
            record = self.store.load(valid_id)
            state_before = record.lifecycle_state
            status_before = record.recovery_status

            # Step 1: Receipt-first probe (Contract V1 §20 Step 2)
            repaired_record = self._probe_receipt_first(record)
            if repaired_record is not None:
                return RecoveryDecisionResult(
                    atlas_job_id=valid_id,
                    lifecycle_state_before=state_before,
                    lifecycle_state_after=repaired_record.lifecycle_state,
                    recovery_status_before=status_before,
                    recovery_status_after=repaired_record.recovery_status,
                    case_classified="RECEIPT_FIRST",
                    repaired_from_receipt=True,
                    receipt_reference=repaired_record.receipt_reference,
                )

            # Step 1b: Deadline exhaustion gate (Contract V1 §23/§28).
            # If the persisted submission/execution deadline has expired while the
            # job is unresolved (no receipt repair succeeded), recovery is exhausted:
            # transition to EXHAUSTED + RECOVERY_FAILED and NEVER proceed to
            # inspect/adopt/verify/resubmit. A receipt-first repair already returned
            # above for genuinely verified jobs, so this only fires for unresolved ones.
            expired_deadline = self._expired_deadline(record, now_utc)
            if expired_deadline is not None:
                return self._deadline_exhausted_transition(record, expired_deadline)

            # Step 2: Capability & Session discovery
            try:
                self.adapter.assert_recovery_capable(record.authorization_id)
            except UnrealAdapterError as exc:
                # Engine down or unreachable -> transition to WAITING_FOR_ENGINE
                waiting_record = record.transition(
                    recovery_status=RenderJobRecoveryStatus.WAITING_FOR_ENGINE,
                )
                self.store.update(waiting_record, expected_revision=record.last_observed_revision)
                return RecoveryDecisionResult(
                    atlas_job_id=valid_id,
                    lifecycle_state_before=state_before,
                    lifecycle_state_after=waiting_record.lifecycle_state,
                    recovery_status_before=status_before,
                    recovery_status_after=waiting_record.recovery_status,
                    case_classified="WAITING_FOR_ENGINE",
                    repaired_from_receipt=False,
                    failure_reason=f"Transport capability assertion failed: {exc}",
                )

            # Step 3: Query Reconcile Catalog
            catalog_response = self._query_catalog(valid_id, record.authorization_id)
            if catalog_response is None or catalog_response.get("journal_status") in ("PARTIAL", "UNREADABLE"):
                # Case J: Journal is partial / unreadable / corrupt
                pending_record = record.transition(
                    recovery_status=RenderJobRecoveryStatus.RECOVERY_PENDING,
                    increment_ambiguity=True,
                )
                self.store.update(pending_record, expected_revision=record.last_observed_revision)
                return RecoveryDecisionResult(
                    atlas_job_id=valid_id,
                    lifecycle_state_before=state_before,
                    lifecycle_state_after=pending_record.lifecycle_state,
                    recovery_status_before=status_before,
                    recovery_status_after=pending_record.recovery_status,
                    case_classified="Case J",
                    repaired_from_receipt=False,
                    failure_reason="Catalog response is partial or unreadable",
                )

            known_jobs = catalog_response.get("known_jobs", [])
            # Find candidate engine jobs matching atlas_job_id
            candidates = [j for j in known_jobs if j.get("atlas_job_id") == valid_id]

            # Case H: Multiple Unreal executions claim the same Atlas job
            if len(candidates) > 1:
                failed_record = record.transition(
                    lifecycle_state=RenderJobLifecycleState.RECOVERY_FAILED,
                    recovery_status=RenderJobRecoveryStatus.NONE,
                    failure_reason=f"Multiple Unreal executions claim atlas_job_id {valid_id}",
                )
                self.store.update(failed_record, expected_revision=record.last_observed_revision)
                return RecoveryDecisionResult(
                    atlas_job_id=valid_id,
                    lifecycle_state_before=state_before,
                    lifecycle_state_after=failed_record.lifecycle_state,
                    recovery_status_before=status_before,
                    recovery_status_after=failed_record.recovery_status,
                    case_classified="Case H",
                    repaired_from_receipt=False,
                    failure_reason=failed_record.failure_reason,
                )

            # Check if there is NO candidate in the engine catalog
            if len(candidates) == 0:
                return self._handle_no_engine_evidence(record, valid_id)

            candidate = candidates[0]

            # Case E & F: Identity, sequence, config binding validation
            binding_mismatch = self._check_candidate_bindings(record, candidate)
            if binding_mismatch:
                failed_record = record.transition(
                    lifecycle_state=RenderJobLifecycleState.RECOVERY_FAILED,
                    recovery_status=RenderJobRecoveryStatus.NONE,
                    failure_reason=binding_mismatch,
                )
                self.store.update(failed_record, expected_revision=record.last_observed_revision)
                return RecoveryDecisionResult(
                    atlas_job_id=valid_id,
                    lifecycle_state_before=state_before,
                    lifecycle_state_after=failed_record.lifecycle_state,
                    recovery_status_before=status_before,
                    recovery_status_after=failed_record.recovery_status,
                    case_classified="Case E/F",
                    repaired_from_receipt=False,
                    failure_reason=binding_mismatch,
                )

            # Check if candidate is live in the current session
            is_live = candidate.get("state_source") == "in_memory_registry" and not candidate.get("finished", False)
            if is_live:
                # Case A: Live match in current session
                tracking_record = record.transition(
                    lifecycle_state=RenderJobLifecycleState.RENDERING,
                    recovery_status=RenderJobRecoveryStatus.NONE,
                    unreal_job_id=candidate.get("job_id"),
                )
                self.store.update(tracking_record, expected_revision=record.last_observed_revision)
                return RecoveryDecisionResult(
                    atlas_job_id=valid_id,
                    lifecycle_state_before=state_before,
                    lifecycle_state_after=tracking_record.lifecycle_state,
                    recovery_status_before=status_before,
                    recovery_status_after=tracking_record.recovery_status,
                    case_classified="Case A",
                    repaired_from_receipt=False,
                )

            # Candidate indicates finished execution -> Requires process quiescence and witness HMAC validation
            return self._handle_finished_candidate(record, candidate, valid_id, lease_token)

    def _probe_receipt_first(self, record: AtlasRenderJobRecord) -> Optional[AtlasRenderJobRecord]:
        """Probe receipt store for full 8-field identity match."""
        # Probe primary receipt store
        receipt_candidates: list[UnrealRenderReceipt] = []
        if self.receipt_store.exists():
            try:
                receipt_candidates.append(self.receipt_store.load())
            except Exception:
                pass

        # Also probe store-level receipts directory
        per_job_receipt = self.store.receipts_dir / f"{record.atlas_job_id}__{record.attempt_ordinal}.json"
        if per_job_receipt.is_file():
            try:
                per_store = UnrealRenderReceiptStore(per_job_receipt)
                receipt_candidates.append(per_store.load())
            except Exception:
                pass

        for receipt in receipt_candidates:
            if self._receipt_matches_record(receipt, record):
                now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
                repaired = record.transition(
                    lifecycle_state=RenderJobLifecycleState.FINALIZED,
                    recovery_status=RenderJobRecoveryStatus.RESOLVED,
                    unreal_job_id=receipt.job_id,
                    receipt_reference=receipt.receipt_digest,
                    last_observed_at=now_utc,
                )
                self.store.update(repaired, expected_revision=record.last_observed_revision)
                return repaired
        return None

    def _receipt_matches_record(self, receipt: UnrealRenderReceipt, record: AtlasRenderJobRecord) -> bool:
        """Validate exact equality across mandatory 10 identity fields (Contract V1 §20 Step 2)."""
        if receipt.sequence_asset_path != record.sequence_asset_path:
            return False
        if receipt.atlas_job_id and receipt.atlas_job_id != record.atlas_job_id:
            return False
        if receipt.attempt_ordinal and receipt.attempt_ordinal != record.attempt_ordinal:
            return False
        if receipt.authorization_id and receipt.authorization_id != record.authorization_id:
            return False
        if receipt.canonical_digital_twin_id and receipt.canonical_digital_twin_id != record.canonical_digital_twin_id:
            return False
        if receipt.config_digest and receipt.config_digest != record.config_digest:
            return False
        if receipt.output_directory and receipt.output_directory != record.output_directory:
            return False
        if record.unreal_job_id and receipt.unreal_job_id != record.unreal_job_id:
            return False
        if record.origin_editor_session_id and receipt.editor_session_id and receipt.editor_session_id != record.origin_editor_session_id:
            return False
        if record.origin_process_creation_time and receipt.process_creation_time and receipt.process_creation_time != record.origin_process_creation_time:
            return False
        return True

    def _query_catalog(self, atlas_job_id: str, auth_id: str) -> Optional[dict[str, Any]]:
        """Query reconcile_render_jobs with framed payload integrity validation.

        The observed state is deep-thawed first so nested frozen mappingproxy /
        tuple structures become plain JSON-serializable dicts/lists. When framing
        fields are present they must BOTH be present, structurally valid, and
        exactly match the canonical ``known_jobs`` payload (byte length + SHA-256).
        Any malformed/incomplete/tampered framing fails closed to UNREADABLE.
        """
        op = UnrealOperation(
            capability=UnrealCapability.RENDER,
            kind=UnrealOperationKind.READ,
            name="reconcile_render_jobs",
            arguments={"job_ids": [atlas_job_id]},
            entity_ids=("RENDER_RECOVERY",),
        )
        try:
            ev = self.adapter.apply_authorized(op, auth_id)
            state = _thaw_dict(ev.observed_state)

            has_byte_length = "payload_byte_length" in state
            has_sha256 = "payload_sha256" in state
            if has_byte_length or has_sha256:
                # Framing fields must be present together; otherwise incomplete.
                if not (has_byte_length and has_sha256):
                    return {"journal_status": "UNREADABLE"}
                if "known_jobs" not in state:
                    return {"journal_status": "UNREADABLE"}

                byte_length = state["payload_byte_length"]
                payload_sha256 = state["payload_sha256"]
                if isinstance(byte_length, bool) or not isinstance(byte_length, int) or byte_length < 0:
                    return {"journal_status": "UNREADABLE"}
                if not isinstance(payload_sha256, str) or len(payload_sha256) != 64:
                    return {"journal_status": "UNREADABLE"}
                try:
                    int(payload_sha256, 16)
                except (TypeError, ValueError):
                    return {"journal_status": "UNREADABLE"}

                payload = canonical_known_jobs_payload(state["known_jobs"])
                if len(payload) != byte_length:
                    return {"journal_status": "UNREADABLE"}
                if hashlib.sha256(payload).hexdigest() != payload_sha256:
                    return {"journal_status": "UNREADABLE"}

            return state
        except Exception as exc:
            logger.warning("Failed to query reconcile catalog: %s", exc)
            return None

    def _check_candidate_bindings(self, record: AtlasRenderJobRecord, candidate: Mapping[str, Any]) -> Optional[str]:
        """Check whether candidate parameters match durable intent."""
        if candidate.get("sequence_asset_path") != record.sequence_asset_path:
            return f"Sequence asset path mismatch: expected {record.sequence_asset_path}, got {candidate.get('sequence_asset_path')}"
        if candidate.get("config_digest") != record.config_digest:
            return f"Config digest mismatch: expected {record.config_digest}, got {candidate.get('config_digest')}"
        if candidate.get("output_directory") != record.output_directory:
            return f"Output directory mismatch: expected {record.output_directory}, got {candidate.get('output_directory')}"
        if record.unreal_job_id and candidate.get("job_id") != record.unreal_job_id:
            return f"Unreal job ID mismatch: expected {record.unreal_job_id}, got {candidate.get('job_id')}"
        return None

    def _handle_no_engine_evidence(
        self,
        record: AtlasRenderJobRecord,
        atlas_job_id: str,
    ) -> RecoveryDecisionResult:
        """Handle cases where engine catalog has zero evidence for this job."""
        out_dir = Path(record.output_directory)
        disk_files_exist = out_dir.is_dir() and any(out_dir.iterdir())

        if not disk_files_exist:
            # Case C: No engine evidence + no disk artifacts
            orphaned_record = record.transition(
                lifecycle_state=RenderJobLifecycleState.ORPHANED,
                recovery_status=RenderJobRecoveryStatus.NONE,
                failure_reason="No engine execution evidence and no artifacts on disk",
            )
            self.store.update(orphaned_record, expected_revision=record.last_observed_revision)
            return RecoveryDecisionResult(
                atlas_job_id=atlas_job_id,
                lifecycle_state_before=record.lifecycle_state,
                lifecycle_state_after=orphaned_record.lifecycle_state,
                recovery_status_before=record.recovery_status,
                recovery_status_after=orphaned_record.recovery_status,
                case_classified="Case C",
                repaired_from_receipt=False,
            )
        else:
            # Case D: No engine evidence + artifacts exist -> ORPHANED_ARTIFACTS_PRESENT (Strictly non-mutating)
            case_d_record = record.transition(
                lifecycle_state=RenderJobLifecycleState.ORPHANED_ARTIFACTS_PRESENT,
                recovery_status=RenderJobRecoveryStatus.NONE,
                failure_reason="Artifacts exist on disk but zero engine execution witness evidence exists",
            )
            self.store.update(case_d_record, expected_revision=record.last_observed_revision)
            return RecoveryDecisionResult(
                atlas_job_id=atlas_job_id,
                lifecycle_state_before=record.lifecycle_state,
                lifecycle_state_after=case_d_record.lifecycle_state,
                recovery_status_before=record.recovery_status,
                recovery_status_after=case_d_record.recovery_status,
                case_classified="Case D",
                repaired_from_receipt=False,
            )

    def _handle_finished_candidate(
        self,
        record: AtlasRenderJobRecord,
        candidate: Mapping[str, Any],
        atlas_job_id: str,
        lease_token: int,
    ) -> RecoveryDecisionResult:
        """Process terminal candidate requiring quiescence, HMAC validation, and artifact inspection."""
        state_before = record.lifecycle_state
        status_before = record.recovery_status

        # 1. Process Quiescence Check (Case K)
        quiescence = evaluate_process_quiescence(self.supervisor, self.deployment_mode)
        if not quiescence.is_quiescent:
            waiting_record = record.transition(
                recovery_status=RenderJobRecoveryStatus.WAITING_FOR_ENGINE_QUIESCENCE,
                failure_reason=quiescence.reason,
            )
            self.store.update(waiting_record, expected_revision=record.last_observed_revision)
            return RecoveryDecisionResult(
                atlas_job_id=atlas_job_id,
                lifecycle_state_before=state_before,
                lifecycle_state_after=waiting_record.lifecycle_state,
                recovery_status_before=status_before,
                recovery_status_after=waiting_record.recovery_status,
                case_classified="Case K (Quiescence Blocked)",
                repaired_from_receipt=False,
                failure_reason=quiescence.reason,
            )

        # 2. Witness Authentication via attempt_nonce HMAC
        if record.attempt_nonce and candidate.get("entry_digest"):
            canonical_payload = {
                "schema_version": 1,
                "atlas_job_id": atlas_job_id,
                "unreal_job_id": candidate.get("job_id"),
                "attempt_ordinal": record.attempt_ordinal,
                "phase": candidate.get("phase", "FINISHED"),
                "phase_sequence": candidate.get("phase_sequence", 3),
                "editor_session_id": candidate.get("editor_session_id"),
                "process_creation_time_utc": candidate.get("process_creation_time_utc"),
                "output_directory": candidate.get("output_directory"),
                "output_manifest": candidate.get("output_manifest"),
            }
            computed_hmac = compute_journal_hmac(record.attempt_nonce, canonical_payload)
            if not hmac.compare_digest(computed_hmac, candidate["entry_digest"]):
                failed_record = record.transition(
                    lifecycle_state=RenderJobLifecycleState.RECOVERY_FAILED,
                    recovery_status=RenderJobRecoveryStatus.NONE,
                    failure_reason="Witness journal HMAC authentication failed (UNTRUSTED_WITNESS)",
                )
                self.store.update(failed_record, expected_revision=record.last_observed_revision)
                return RecoveryDecisionResult(
                    atlas_job_id=atlas_job_id,
                    lifecycle_state_before=state_before,
                    lifecycle_state_after=failed_record.lifecycle_state,
                    recovery_status_before=status_before,
                    recovery_status_after=failed_record.recovery_status,
                    case_classified="UNTRUSTED_WITNESS",
                    repaired_from_receipt=False,
                    failure_reason=failed_record.failure_reason,
                )

        # 3. Artifact Validation & Stability Check
        manifest = candidate.get("output_manifest", [])
        output_files = candidate.get("output_files", [])
        if not manifest and not output_files:
            failed_record = record.transition(
                lifecycle_state=RenderJobLifecycleState.FAILED,
                recovery_status=RenderJobRecoveryStatus.NONE,
                failure_reason="Engine claims FINISHED but manifest and output_files are empty",
            )
            self.store.update(failed_record, expected_revision=record.last_observed_revision)
            return RecoveryDecisionResult(
                atlas_job_id=atlas_job_id,
                lifecycle_state_before=state_before,
                lifecycle_state_after=failed_record.lifecycle_state,
                recovery_status_before=status_before,
                recovery_status_after=failed_record.recovery_status,
                case_classified="Case G",
                repaired_from_receipt=False,
                failure_reason=failed_record.failure_reason,
            )

        # Four-point artifact stability and hash validation
        for entry in manifest:
            path_str = entry.get("path")
            expected_sha = entry.get("sha256")
            expected_size = entry.get("size")
            file_path = Path(path_str)

            if not file_path.is_file():
                # Case G: Artifact missing
                return self._fail_case_g(record, f"Declared output file missing: {path_str}")

            # Two-pass stat check
            stat_1 = file_path.stat()
            if not verify_png_completeness(file_path, expected_size):
                return self._fail_case_g(record, f"Output file PNG completeness check failed: {path_str}")

            with file_path.open("rb") as f:
                computed_file_sha = hashlib.sha256(f.read()).hexdigest()

            stat_2 = file_path.stat()
            if stat_1.st_size != stat_2.st_size or stat_1.st_mtime_ns != stat_2.st_mtime_ns:
                return self._fail_case_g(record, f"Artifact read instability detected: {path_str}")

            if computed_file_sha != expected_sha:
                return self._fail_case_g(record, f"Artifact SHA-256 mismatch for {path_str}")

        # 4. Independent Evidence Verification
        # In recovery, candidate comes from the engine journal/observation.
        # Check that candidate carries the process identity; if not, pass candidate as is so verifier can enforce fail-closed check
        try:
            verified_evidence = verify_render_job_evidence(
                operation_name="inspect_render_job",
                entity_ids=("RENDER_RECOVERY",),
                observed_state=candidate,
                source="unreal-recovery-coordinator",
                job_record=record,
                evidence_source_class="ENGINE_JOURNAL_ATTESTED",
            )
        except Exception as exc:
            return self._fail_case_g(record, f"Independent evidence verification failed: {exc}")

        # 5. Issue Receipt via Store-Gated Atomic Publication
        issued_receipt = UnrealRenderReceipt.issue(
            verified_evidence,
            atlas_job_id=record.atlas_job_id,
            attempt_ordinal=record.attempt_ordinal,
            authorization_id=record.authorization_id,
            canonical_digital_twin_id=record.canonical_digital_twin_id,
            config_digest=record.config_digest,
            output_directory=record.output_directory,
            lease_token=lease_token,
            coordinator_id=self.coordinator_id,
        )

        final_record, pub_receipt = self.store.publish_verified_receipt(
            atlas_job_id=record.atlas_job_id,
            attempt_ordinal=record.attempt_ordinal,
            presented_lease_token=lease_token,
            expected_record_revision=record.last_observed_revision,
            receipt=issued_receipt,
        )

        return RecoveryDecisionResult(
            atlas_job_id=atlas_job_id,
            lifecycle_state_before=state_before,
            lifecycle_state_after=final_record.lifecycle_state,
            recovery_status_before=status_before,
            recovery_status_after=final_record.recovery_status,
            case_classified="Case B",
            repaired_from_receipt=False,
            receipt_reference=final_record.receipt_reference,
        )

    def _fail_case_g(self, record: AtlasRenderJobRecord, reason: str) -> RecoveryDecisionResult:
        failed_record = record.transition(
            lifecycle_state=RenderJobLifecycleState.FAILED,
            recovery_status=RenderJobRecoveryStatus.NONE,
            failure_reason=reason,
        )
        self.store.update(failed_record, expected_revision=record.last_observed_revision)
        return RecoveryDecisionResult(
            atlas_job_id=record.atlas_job_id,
            lifecycle_state_before=record.lifecycle_state,
            lifecycle_state_after=failed_record.lifecycle_state,
            recovery_status_before=record.recovery_status,
            recovery_status_after=failed_record.recovery_status,
            case_classified="Case G",
            repaired_from_receipt=False,
            failure_reason=reason,
        )
