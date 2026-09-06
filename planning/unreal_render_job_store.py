"""Durable, versioned, fail-closed store for AtlasRenderJobRecord.

Authoritative specification: docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md §6, §8, §24, §29.
"""

from __future__ import annotations

import contextlib
import datetime
import json
import os
import tempfile
from pathlib import Path
from typing import Iterator, Optional, Union

from planning.unreal_render_job_record import (
    AtlasRenderJobRecord,
    AtlasRenderJobRecordError,
    validate_canonical_atlas_job_id,
)
from planning.unreal_render_job_states import (
    TERMINAL_LIFECYCLE_STATES,
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
from planning.unreal_render_receipt import UnrealRenderReceipt
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore


class AtlasRenderJobStoreError(RuntimeError):
    """Base error for durable render job store failures."""


class AtlasRenderJobStoreCorruptionError(AtlasRenderJobStoreError):
    """Raised when an on-disk record is corrupt or has an inconsistent authoritative digest."""


class AtlasRenderJobStoreLockError(AtlasRenderJobStoreError):
    """Raised when coordinator or per-job execution ownership cannot be acquired."""


class AtlasRenderJobStoreStaleWriterError(AtlasRenderJobStoreError):
    """Raised when an update is rejected due to revision conflict / stale writer."""


class AtlasRenderJobStoreRevisionMismatchError(AtlasRenderJobStoreError):
    """Raised when expected record revision does not match on update."""


class AtlasRenderJobStore:
    """Fail-closed durable persistence for AtlasRenderJobRecord.
    
    Provides:
    - versioned serialization with envelope integrity
    - atomic file replacement (tempfile + flush + fsync + os.replace)
    - corruption detection with non-destructive quarantine
    - single-coordinator store ownership via coordinator.lock
    - per-job exclusive write ownership via <atlas_job_id>.lock
    - stale-writer rejection via last_observed_revision compare-and-swap
    """

    STORE_VERSION = 1

    def __init__(self, root_dir: Union[str, os.PathLike]):
        self.root = Path(root_dir).resolve()
        self.jobs_dir = self.root / "jobs"
        self.locks_dir = self.root / "locks"
        self.quarantine_dir = self.root / "quarantine"
        self.receipts_dir = self.root / "receipts"
        self.coordinator_lock_file = self.locks_dir / "coordinator.lock"

        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.receipts_dir.mkdir(parents=True, exist_ok=True)

    def _job_file_path(self, atlas_job_id: str) -> Path:
        valid_id = validate_canonical_atlas_job_id(atlas_job_id)
        return self.jobs_dir / f"{valid_id}.json"

    def _job_lock_file_path(self, atlas_job_id: str) -> Path:
        valid_id = validate_canonical_atlas_job_id(atlas_job_id)
        return self.locks_dir / f"{valid_id}.lock"

    # -------------------------------------------------------------------------
    # Coordinator & Per-Job Locking
    # -------------------------------------------------------------------------

    @contextlib.contextmanager
    def acquire_coordinator(
        self,
        coordinator_id: str,
        lease_token: int = 1,
    ) -> Iterator[int]:
        """Acquire exclusive store-level coordinator ownership."""
        if not isinstance(coordinator_id, str) or not coordinator_id.strip():
            raise ValueError("coordinator_id must be a non-empty string")
        if not isinstance(lease_token, int) or isinstance(lease_token, bool) or lease_token < 1:
            raise ValueError("lease_token must be a positive integer >= 1")

        lock_path = self.coordinator_lock_file
        # Create lock file exclusively
        fd = None
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            payload = {
                "coordinator_id": coordinator_id.strip(),
                "lease_token": lease_token,
                "acquired_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "pid": os.getpid(),
            }
            os.write(fd, json.dumps(payload, sort_keys=True).encode("utf-8"))
        except FileExistsError as exc:
            raise AtlasRenderJobStoreLockError(
                f"Another Atlas coordinator is currently active for store {str(self.root)!r}"
            ) from exc
        finally:
            if fd is not None:
                os.close(fd)

        try:
            yield lease_token
        finally:
            try:
                if lock_path.exists():
                    lock_path.unlink()
            except OSError:
                pass

    @contextlib.contextmanager
    def acquire_job_claim(self, atlas_job_id: str, claim_holder_id: str) -> Iterator[None]:
        """Acquire exclusive per-job execution claim for non-terminal lifecycle."""
        valid_id = validate_canonical_atlas_job_id(atlas_job_id)
        lock_path = self._job_lock_file_path(valid_id)

        fd = None
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            payload = {
                "atlas_job_id": valid_id,
                "claim_holder_id": claim_holder_id.strip(),
                "acquired_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "pid": os.getpid(),
            }
            os.write(fd, json.dumps(payload, sort_keys=True).encode("utf-8"))
        except FileExistsError as exc:
            raise AtlasRenderJobStoreLockError(
                f"Exclusive execution claim for job {valid_id} is already held by another worker"
            ) from exc
        finally:
            if fd is not None:
                os.close(fd)

        try:
            yield
        finally:
            try:
                if lock_path.exists():
                    lock_path.unlink()
            except OSError:
                pass

    # -------------------------------------------------------------------------
    # Persistence & Atomic Replacement
    # -------------------------------------------------------------------------

    def _flush_parent_directory(self, target_dir: Path) -> None:
        if os.name == "nt":
            return
        try:
            fd = os.open(str(target_dir), os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError:
            pass

    def _atomic_write_json(self, target_path: Path, payload: dict[str, Any]) -> None:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")

        fd, temp_path = tempfile.mkstemp(
            prefix=f".{target_path.name}.",
            suffix=".tmp",
            dir=str(target_path.parent),
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, str(target_path))
            self._flush_parent_directory(target_path.parent)
        except OSError as exc:
            raise AtlasRenderJobStoreError(f"Failed to atomically persist {str(target_path)!r}") from exc
        finally:
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    def create(self, record: AtlasRenderJobRecord) -> AtlasRenderJobRecord:
        """Create and persist a new record. Fails closed if record file already exists."""
        if not isinstance(record, AtlasRenderJobRecord):
            raise TypeError("record must be an AtlasRenderJobRecord")

        target_path = self._job_file_path(record.atlas_job_id)
        if target_path.exists():
            raise AtlasRenderJobStoreError(
                f"Cannot create existing job record: {record.atlas_job_id}"
            )

        envelope = {
            "store_version": self.STORE_VERSION,
            "record": record.to_dict(),
            "authoritative_digest": record.authoritative_digest,
        }
        self._atomic_write_json(target_path, envelope)
        return record

    def load(self, atlas_job_id: str) -> AtlasRenderJobRecord:
        """Load and validate record. Fails closed on corruption or digest mismatch."""
        target_path = self._job_file_path(atlas_job_id)
        if not target_path.exists():
            raise FileNotFoundError(f"Job record not found: {atlas_job_id}")

        try:
            with target_path.open("r", encoding="utf-8") as handle:
                envelope = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            quarantine_path = self.quarantine_corrupt_file(target_path, f"JSON unreadable: {exc}")
            raise AtlasRenderJobStoreCorruptionError(
                f"Record {atlas_job_id} is unreadable/corrupt; quarantined to {str(quarantine_path)!r}"
            ) from exc

        if not isinstance(envelope, dict):
            quarantine_path = self.quarantine_corrupt_file(target_path, "Envelope is not an object")
            raise AtlasRenderJobStoreCorruptionError(
                f"Record envelope {atlas_job_id} is corrupt; quarantined to {str(quarantine_path)!r}"
            )

        if envelope.get("store_version") != self.STORE_VERSION:
            raise AtlasRenderJobStoreError(
                f"Unsupported store_version: {envelope.get('store_version')}"
            )

        record_dict = envelope.get("record")
        stored_digest = envelope.get("authoritative_digest")

        if not isinstance(record_dict, dict) or not isinstance(stored_digest, str):
            quarantine_path = self.quarantine_corrupt_file(target_path, "Malformed envelope structure")
            raise AtlasRenderJobStoreCorruptionError(
                f"Record {atlas_job_id} has malformed envelope; quarantined to {str(quarantine_path)!r}"
            )

        try:
            record = AtlasRenderJobRecord.from_dict(record_dict)
        except AtlasRenderJobRecordError as exc:
            quarantine_path = self.quarantine_corrupt_file(target_path, f"Record validation error: {exc}")
            raise AtlasRenderJobStoreCorruptionError(
                f"Record {atlas_job_id} validation failed: {exc}; quarantined to {str(quarantine_path)!r}"
            ) from exc

        if record.authoritative_digest != stored_digest:
            quarantine_path = self.quarantine_corrupt_file(
                target_path,
                f"Authoritative digest mismatch: expected {record.authoritative_digest}, stored {stored_digest}",
            )
            raise AtlasRenderJobStoreCorruptionError(
                f"Record {atlas_job_id} authoritative digest mismatch; quarantined to {str(quarantine_path)!r}"
            )

        return record

    def update(
        self,
        record: AtlasRenderJobRecord,
        expected_revision: Optional[int] = None,
    ) -> AtlasRenderJobRecord:
        """Update an existing record with revision check (stale-writer rejection)."""
        if not isinstance(record, AtlasRenderJobRecord):
            raise TypeError("record must be an AtlasRenderJobRecord")

        target_path = self._job_file_path(record.atlas_job_id)
        if not target_path.exists():
            raise FileNotFoundError(f"Cannot update non-existent job record: {record.atlas_job_id}")

        # Stale-writer verification
        current = self.load(record.atlas_job_id)
        if expected_revision is not None:
            if current.last_observed_revision != expected_revision:
                raise AtlasRenderJobStoreStaleWriterError(
                    f"Stale writer for job {record.atlas_job_id}: current revision is {current.last_observed_revision}, expected {expected_revision}"
                )
        else:
            if record.last_observed_revision <= current.last_observed_revision:
                raise AtlasRenderJobStoreStaleWriterError(
                    f"Monotonic revision violation for job {record.atlas_job_id}: update revision {record.last_observed_revision} <= current {current.last_observed_revision}"
                )

        envelope = {
            "store_version": self.STORE_VERSION,
            "record": record.to_dict(),
            "authoritative_digest": record.authoritative_digest,
        }
        self._atomic_write_json(target_path, envelope)
        return record

    def exists(self, atlas_job_id: str) -> bool:
        """Check if a valid job file exists on disk."""
        try:
            path = self._job_file_path(atlas_job_id)
            return path.is_file()
        except AtlasRenderJobRecordError:
            return False

    def list_job_ids(self) -> list[str]:
        """List all valid atlas_job_ids currently present in the store."""
        job_ids = []
        for file in self.jobs_dir.glob("*.json"):
            stem = file.stem
            try:
                valid_id = validate_canonical_atlas_job_id(stem)
                job_ids.append(valid_id)
            except AtlasRenderJobRecordError:
                continue
        return sorted(job_ids)

    def publish_verified_receipt(
        self,
        *,
        atlas_job_id: str,
        attempt_ordinal: int,
        presented_lease_token: int,
        expected_record_revision: int,
        receipt: UnrealRenderReceipt,
    ) -> tuple[AtlasRenderJobRecord, UnrealRenderReceipt]:
        """Atomically validate fencing, advance watermark, publish receipt, and finalize record.
        
        Store-gated fencing protocol:
        1. Load current record.
        2. Validate presented_lease_token > record.last_accepted_lease_token.
        3. Validate expected_record_revision == record.last_observed_revision.
        4. Validate record is not already finalized.
        5. Durably advance record.last_accepted_lease_token = presented_lease_token.
        6. Publish receipt atomically (write .tmp + MoveFileExW / replace onto target).
        7. Transition record to FINALIZED / RESOLVED and update.
        """
        if not isinstance(receipt, UnrealRenderReceipt):
            raise TypeError("receipt must be an UnrealRenderReceipt")

        # 1. Load record under per-job path
        record = self.load(atlas_job_id)

        # 2. Fencing token check
        if presented_lease_token <= record.last_accepted_lease_token:
            raise AtlasRenderJobStoreStaleWriterError(
                f"Fencing token {presented_lease_token} rejected: record already has last_accepted_lease_token {record.last_accepted_lease_token}"
            )

        # 3. Optimistic revision check
        if record.last_observed_revision != expected_record_revision:
            raise AtlasRenderJobStoreRevisionMismatchError(
                f"Record revision mismatch: expected {expected_record_revision}, current is {record.last_observed_revision}"
            )

        # 4. Lifecycle eligibility check
        if record.lifecycle_state in TERMINAL_LIFECYCLE_STATES:
            raise AtlasRenderJobStoreError(
                f"Cannot publish receipt for job {atlas_job_id} in terminal state {record.lifecycle_state}"
            )

        # 5. Advance fencing watermark (write-ahead persistence)
        watermark_record = record.transition(
            last_accepted_lease_token=presented_lease_token,
        )
        self.update(watermark_record, expected_revision=record.last_observed_revision)

        # 6. Publish receipt via temporary file + atomic no-replace publication
        receipt_filename = f"{atlas_job_id}__{attempt_ordinal}.json"
        receipt_path = self.receipts_dir / receipt_filename
        receipt_store = UnrealRenderReceiptStore(receipt_path)

        if receipt_store.exists():
            existing = receipt_store.load()
            if existing.receipt_digest != receipt.receipt_digest:
                raise AtlasRenderJobStoreError(
                    f"Receipt collision at {str(receipt_path)!r} with differing digest"
                )
        else:
            receipt_store.save(receipt)

        # 7. Finalize record
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        final_record = watermark_record.transition(
            lifecycle_state=RenderJobLifecycleState.FINALIZED,
            recovery_status=RenderJobRecoveryStatus.RESOLVED,
            unreal_job_id=receipt.job_id,
            receipt_reference=str(receipt_path),
            last_observed_at=now_utc,
        )
        self.update(final_record, expected_revision=watermark_record.last_observed_revision)

        return final_record, receipt

    def quarantine_corrupt_file(self, file_path: Path, reason: str) -> Path:
        """Non-destructively quarantine a corrupted or tampered record file."""
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        quarantine_file_name = f"{file_path.name}.corrupt.{timestamp}"
        quarantine_target = self.quarantine_dir / quarantine_file_name

        try:
            if file_path.exists():
                os.replace(str(file_path), str(quarantine_target))
            # Write diagnostic sidecar metadata
            meta_path = self.quarantine_dir / f"{quarantine_file_name}.meta.json"
            meta_payload = {
                "original_path": str(file_path),
                "quarantine_path": str(quarantine_target),
                "reason": reason,
                "timestamp": timestamp,
            }
            with meta_path.open("w", encoding="utf-8") as m_handle:
                json.dump(meta_payload, m_handle, sort_keys=True, indent=2)
        except OSError as exc:
            raise AtlasRenderJobStoreError(f"Failed to quarantine corrupt file {str(file_path)!r}") from exc

        return quarantine_target
