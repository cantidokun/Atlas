"""Atlas-side submission and idempotency orchestration service for Unreal render recovery.

Authoritative specification: docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md §7, §8, §12, §18, §27.
Milestone 3: Atlas Submission / Idempotency Integration.
"""

from __future__ import annotations

import datetime
import os
import secrets
import uuid
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from planning.unreal_adapter_production import (
    REQUIRED_RECOVERY_CAPABILITIES,
    UnrealAdapterError,
    UnrealAdapterProduction,
)
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_render_contract import (
    UnrealRenderConfig,
    compute_render_config_digest,
    compute_render_request_digest,
    derive_isolated_output_directory,
)
from planning.unreal_render_job_record import (
    AtlasRenderJobRecord,
    AtlasRenderJobRecordError,
    validate_canonical_atlas_job_id,
)
from planning.unreal_render_job_states import (
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
from planning.unreal_render_job_store import (
    AtlasRenderJobStore,
    AtlasRenderJobStoreError,
    AtlasRenderJobStoreLockError,
)
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_transport_named_pipe import (
    NamedPipeTransportDisconnectedError,
    NamedPipeTransportError,
    NamedPipeTransportTimeoutError,
)


class UnrealRenderSubmissionError(RuntimeError):
    """Raised when render submission fails closed."""


@dataclass(frozen=True)
class RenderSubmissionResult:
    """Outcome of an authorized submission attempt."""

    record: AtlasRenderJobRecord
    is_duplicate: bool
    is_repaired_from_receipt: bool
    acceptance_unknown: bool
    rejection_code: Optional[str] = None


class UnrealRenderSubmissionService:
    """Orchestrates the authorized submission boundary without authorization authority.
    
    Order of execution:
    1. Validate authorization & plan context
    2. Mint immutable root identity & derive isolated output namespace
    3. Compute config & request digests
    4. Receipt-first probe (repair if valid receipt already exists)
    5. Persist durable intent as PENDING_SUBMISSION
    6. Acquire exclusive per-job execution claim
    7. Capability-gate Unreal engine session
    8. Transmit submit_render over transport
    9. On success: bind observed Unreal identity, persist SUBMITTED state
    10. On timeout/disconnect: record RECOVERY_PENDING (acceptance-unknown), do NOT resubmit
    11. On rejection: record FAILED or RECOVERY_FAILED
    """

    def __init__(
        self,
        *,
        store: AtlasRenderJobStore,
        adapter: UnrealAdapterProduction,
        receipt_store: Optional[UnrealRenderReceiptStore] = None,
        worker_id: Optional[str] = None,
    ) -> None:
        self._store = store
        self._adapter = adapter
        self._receipt_store = receipt_store
        self._worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"

    def submit_render(
        self,
        *,
        authorization_id: str,
        canonical_digital_twin_id: str,
        sequence_asset_path: str,
        output_parent_directory: str,
        render_config: UnrealRenderConfig | Mapping[str, Any],
        entity_ids: Sequence[str] = ("FIELD_SURFACE",),
        attempt_ordinal: int = 1,
        existing_atlas_job_id: Optional[str] = None,
        submission_deadline: Optional[str] = None,
        execution_deadline: Optional[str] = None,
    ) -> RenderSubmissionResult:
        """Submit an authorized render job under strict durability and idempotency rules."""
        # 1. Validate authorization and required plan inputs
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise UnrealRenderSubmissionError("authorization_id must be a non-empty string")
        if not isinstance(canonical_digital_twin_id, str) or not canonical_digital_twin_id.strip():
            raise UnrealRenderSubmissionError("canonical_digital_twin_id must be a non-empty string")
        if not isinstance(sequence_asset_path, str) or not sequence_asset_path.strip():
            raise UnrealRenderSubmissionError("sequence_asset_path must be a non-empty string")
        if not isinstance(output_parent_directory, str) or not output_parent_directory.strip():
            raise UnrealRenderSubmissionError("output_parent_directory must be a non-empty string")

        entity_ids_tuple = tuple(entity_ids)
        if not entity_ids_tuple or any(not isinstance(e, str) or not e.strip() for e in entity_ids_tuple):
            raise UnrealRenderSubmissionError("entity_ids must be a non-empty sequence of non-empty strings")

        # 2. Derive or validate atlas_job_id
        if existing_atlas_job_id is not None:
            atlas_job_id = validate_canonical_atlas_job_id(existing_atlas_job_id)
        else:
            atlas_job_id = f"atlas-render-job-{uuid.uuid4()}"

        # 3. Output directory & digests
        output_directory = derive_isolated_output_directory(output_parent_directory, atlas_job_id)
        config_digest = compute_render_config_digest(render_config)
        request_digest = compute_render_request_digest(
            sequence_asset_path=sequence_asset_path,
            output_directory=output_directory,
            config_digest=config_digest,
            authorization_id=authorization_id,
            entity_ids=entity_ids_tuple,
        )

        # Expected output spec
        if isinstance(render_config, UnrealRenderConfig):
            expected_output_spec = {
                "format": render_config.output_format,
                "width": render_config.width,
                "height": render_config.height,
                "start_frame": render_config.start_frame,
                "end_frame": render_config.end_frame,
            }
        else:
            expected_output_spec = dict(render_config)

        # 4. Check for existing record on disk (Idempotency / Conflict check)
        record: Optional[AtlasRenderJobRecord] = None
        if self._store.exists(atlas_job_id):
            record = self._store.load(atlas_job_id)

            # Terminal record blocks any new submission
            if record.lifecycle_state in (
                RenderJobLifecycleState.FINALIZED,
                RenderJobLifecycleState.FAILED,
                RenderJobLifecycleState.ORPHANED,
                RenderJobLifecycleState.ORPHANED_ARTIFACTS_PRESENT,
                RenderJobLifecycleState.RECOVERY_FAILED,
                RenderJobLifecycleState.RECORD_CORRUPT,
            ):
                raise UnrealRenderSubmissionError(
                    f"Cannot submit render for job {atlas_job_id}: record is terminal ({record.lifecycle_state.value})"
                )

            # Compare immutable submission identity
            b_seq = record.sequence_asset_path == sequence_asset_path.strip()
            b_auth = record.authorization_id == authorization_id.strip()
            b_twin = record.canonical_digital_twin_id == canonical_digital_twin_id.strip()
            b_dir = record.output_directory == output_directory
            b_cfg = record.config_digest == config_digest

            if not (b_seq and b_auth and b_twin and b_dir and b_cfg):
                # Conflicting reuse of existing atlas_job_id
                raise UnrealRenderSubmissionError(
                    f"Conflicting reuse of existing atlas_job_id: {atlas_job_id}"
                )

            # If already SUBMITTED or RENDERING, return existing state idempotently
            if record.lifecycle_state in (
                RenderJobLifecycleState.SUBMITTED,
                RenderJobLifecycleState.RENDERING,
                RenderJobLifecycleState.COMPLETED_UNVERIFIED,
            ):
                return RenderSubmissionResult(
                    record=record,
                    is_duplicate=True,
                    is_repaired_from_receipt=False,
                    acceptance_unknown=False,
                )

        # 5. Receipt-first probe: if a verified receipt already exists for this job, repair to FINALIZED
        if self._receipt_store is not None and self._receipt_store.exists():
            try:
                receipt = self._receipt_store.load()
                # Check if receipt binds to this logical job
                if receipt.sequence_asset_path == sequence_asset_path.strip():
                    # Create or update record directly to FINALIZED
                    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    if record is None:
                        record = AtlasRenderJobRecord.create_intent(
                            atlas_job_id=atlas_job_id,
                            attempt_ordinal=attempt_ordinal,
                            authorization_id=authorization_id.strip(),
                            canonical_digital_twin_id=canonical_digital_twin_id.strip(),
                            sequence_asset_path=sequence_asset_path.strip(),
                            request_digest=request_digest,
                            config_digest=config_digest,
                            output_parent_directory=output_parent_directory.strip(),
                            output_directory=output_directory,
                            expected_output_spec=expected_output_spec,
                            created_at=now_utc,
                        )
                        self._store.create(record)

                    repaired = record.transition(
                        lifecycle_state=RenderJobLifecycleState.FINALIZED,
                        recovery_status=RenderJobRecoveryStatus.RESOLVED,
                        unreal_job_id=receipt.job_id,
                        receipt_reference=receipt.receipt_digest,
                        last_observed_at=now_utc,
                    )
                    self._store.update(repaired, expected_revision=record.last_observed_revision)
                    return RenderSubmissionResult(
                        record=repaired,
                        is_duplicate=True,
                        is_repaired_from_receipt=True,
                        acceptance_unknown=False,
                    )
            except Exception:
                # Receipt-first probe only repairs when a verified, consistent receipt is proven to exist
                pass

        # 6. Create & Persist durable intent as PENDING_SUBMISSION if not yet created
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if record is None:
            attempt_nonce = secrets.token_hex(32)
            record = AtlasRenderJobRecord.create_intent(
                atlas_job_id=atlas_job_id,
                attempt_ordinal=attempt_ordinal,
                authorization_id=authorization_id.strip(),
                canonical_digital_twin_id=canonical_digital_twin_id.strip(),
                sequence_asset_path=sequence_asset_path.strip(),
                request_digest=request_digest,
                config_digest=config_digest,
                output_parent_directory=output_parent_directory.strip(),
                output_directory=output_directory,
                expected_output_spec=expected_output_spec,
                created_at=now_iso,
                submission_deadline=submission_deadline,
                execution_deadline=execution_deadline,
                attempt_nonce=attempt_nonce,
            )
            self._store.create(record)

        # 7. Acquire exclusive per-job execution claim
        with self._store.acquire_job_claim(atlas_job_id, self._worker_id):
            # Refresh record under lock to catch any concurrent modification
            record = self._store.load(atlas_job_id)
            expected_rev = record.last_observed_revision
            # 8. Capability negotiation
            try:
                self._adapter.assert_recovery_capable(authorization_id)
            except UnrealAdapterError as exc:
                failed_record = record.transition(
                    lifecycle_state=RenderJobLifecycleState.FAILED,
                    failure_reason=f"Engine capability assertion failed: {exc}",
                )
                self._store.update(failed_record, expected_revision=record.last_observed_revision)
                raise UnrealRenderSubmissionError(f"Submission rejected by capability gate: {exc}") from exc

            # 9. Build submit_render operation
            submit_arguments = {
                "entity_ids": entity_ids_tuple,
                "atlas_job_id": atlas_job_id,
                "sequence_asset_path": sequence_asset_path.strip(),
                "output_directory": output_directory,
                "config_digest": config_digest,
                "attempt_nonce": record.attempt_nonce or "",
            }
            submit_op = UnrealOperation(
                capability=UnrealCapability.RENDER,
                kind=UnrealOperationKind.WRITE,
                name="submit_render",
                arguments=submit_arguments,
                entity_ids=entity_ids_tuple,
            )

            # 10. Dispatch transport request
            t_submitted = datetime.datetime.now(datetime.timezone.utc).isoformat()
            try:
                submit_evidence = self._adapter.apply_authorized(submit_op, authorization_id)
            except UnrealAdapterError as exc:
                err_text = str(exc)
                if isinstance(exc.__cause__, (NamedPipeTransportTimeoutError, NamedPipeTransportDisconnectedError)):
                    # Acceptance unknown: do NOT resubmit, do NOT mark FAILED
                    pending_record = record.transition(
                        lifecycle_state=RenderJobLifecycleState.PENDING_SUBMISSION,
                        recovery_status=RenderJobRecoveryStatus.RECOVERY_PENDING,
                        atlas_submitted_at=t_submitted,
                        failure_reason=f"Transport uncertainty during submission: {exc.__cause__}",
                        increment_ambiguity=True,
                    )
                    self._store.update(pending_record, expected_revision=record.last_observed_revision)
                    return RenderSubmissionResult(
                        record=pending_record,
                        is_duplicate=False,
                        is_repaired_from_receipt=False,
                        acceptance_unknown=True,
                        rejection_code="ERR_TRANSPORT_UNCERTAINTY",
                    )

                # Authoritative Unreal rejection
                if "ERR_JOB_ID_CONFLICT" in err_text:
                    rejected_record = record.transition(
                        lifecycle_state=RenderJobLifecycleState.RECOVERY_FAILED,
                        failure_reason=err_text,
                    )
                    code = "ERR_JOB_ID_CONFLICT"
                else:
                    rejected_record = record.transition(
                        lifecycle_state=RenderJobLifecycleState.FAILED,
                        failure_reason=err_text,
                    )
                    code = "ERR_OPERATION_FAILED"

                self._store.update(rejected_record, expected_revision=record.last_observed_revision)
                return RenderSubmissionResult(
                    record=rejected_record,
                    is_duplicate=False,
                    is_repaired_from_receipt=False,
                    acceptance_unknown=False,
                    rejection_code=code,
                )
            except (NamedPipeTransportTimeoutError, NamedPipeTransportDisconnectedError) as exc:
                # Acceptance unknown: do NOT resubmit, do NOT mark FAILED
                pending_record = record.transition(
                    lifecycle_state=RenderJobLifecycleState.PENDING_SUBMISSION,
                    recovery_status=RenderJobRecoveryStatus.RECOVERY_PENDING,
                    atlas_submitted_at=t_submitted,
                    failure_reason=f"Transport uncertainty during submission: {exc}",
                    increment_ambiguity=True,
                )
                self._store.update(pending_record, expected_revision=record.last_observed_revision)
                return RenderSubmissionResult(
                    record=pending_record,
                    is_duplicate=False,
                    is_repaired_from_receipt=False,
                    acceptance_unknown=True,
                    rejection_code="ERR_TRANSPORT_UNCERTAINTY",
                )

            # 11. Extract observed Unreal identity
            raw_state = submit_evidence.observed_state
            unreal_job_id: Optional[str] = None
            if "render_job" in raw_state and isinstance(raw_state["render_job"], Mapping):
                unreal_job_id = str(raw_state["render_job"].get("job_id"))
            else:
                for entry in raw_state.values():
                    if isinstance(entry, Mapping) and "render_job" in entry and isinstance(entry["render_job"], Mapping):
                        unreal_job_id = str(entry["render_job"].get("job_id"))
                        break

            if not unreal_job_id:
                # Response received but missing unreal_job_id
                uncertain_record = record.transition(
                    lifecycle_state=RenderJobLifecycleState.PENDING_SUBMISSION,
                    recovery_status=RenderJobRecoveryStatus.RECOVERY_PENDING,
                    atlas_submitted_at=t_submitted,
                    failure_reason="Malformed submit_render response: missing unreal_job_id",
                    increment_ambiguity=True,
                )
                self._store.update(uncertain_record, expected_revision=record.last_observed_revision)
                return RenderSubmissionResult(
                    record=uncertain_record,
                    is_duplicate=False,
                    is_repaired_from_receipt=False,
                    acceptance_unknown=True,
                    rejection_code="ERR_MALFORMED_OBSERVED_STATE",
                )

            now_accepted = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # Extract session identity if captured in evidence metadata
            sess_meta = raw_state.get("_session_identity", {})
            origin_session_id = sess_meta.get("editor_session_id")
            origin_pid = sess_meta.get("process_id")
            origin_creation_time = sess_meta.get("process_creation_time_utc")

            # Transition record to SUBMITTED
            submitted_record = record.transition(
                lifecycle_state=RenderJobLifecycleState.SUBMITTED,
                recovery_status=RenderJobRecoveryStatus.NONE,
                atlas_submitted_at=t_submitted,
                engine_accepted_at=now_accepted,
                unreal_job_id=unreal_job_id,
                origin_editor_session_id=origin_session_id,
                origin_process_id=origin_pid,
                origin_process_creation_time=origin_creation_time,
                last_observed_at=now_accepted,
            )
            self._store.update(submitted_record, expected_revision=record.last_observed_revision)

            return RenderSubmissionResult(
                record=submitted_record,
                is_duplicate=False,
                is_repaired_from_receipt=False,
                acceptance_unknown=False,
            )
