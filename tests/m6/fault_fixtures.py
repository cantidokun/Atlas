"""Shared deterministic fixtures/factories for the Milestone 6 fault-injection suite.

Authoritative specification: docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md
§31 (Required Deterministic Tests) and §32 (Required C++ Unreal Automation Tests).

Design rules honored throughout M6:
- Every fixture is fully deterministic (no timing sleeps, no real process crashes,
  no live Unreal transport). Failures are injected via controlled fakes, scripted
  responses, deterministic filesystem fixtures, and mocked process identities.
- Test names are mapped to the contract matrix item they validate via a systematic
  ``_M6_<item>_`` suffix convention and a ``m6_item`` pytest marker.
- No production behavior is modified; no M4/M5 guard is weakened.
"""

from __future__ import annotations

import hashlib
import json
import struct
import uuid
import zlib
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence
from unittest.mock import MagicMock

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_operation_contract import UnrealCapability, UnrealOperation, UnrealOperationKind
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
    AtlasRenderJobStoreCorruptionError,
    AtlasRenderJobStoreError,
    AtlasRenderJobStoreLockError,
    AtlasRenderJobStoreRevisionMismatchError,
    AtlasRenderJobStoreStaleWriterError,
)
from planning.unreal_render_receipt import UnrealRenderReceipt
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_recovery_coordinator import (
    UnrealRenderRecoveryCoordinator,
    compute_journal_hmac,
)
from scripts.run_unreal_supervisor import AtlasProcessSupervisor


def make_valid_png(path: Path, width: int = 1, height: int = 1) -> bytes:
    """Create a minimal valid PNG (8-bit RGB) at ``path`` and return its bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sig = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF)
    ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + ihdr_crc
    raw_scanlines = b"\x00" * (1 + width * 3) * height
    compressed = zlib.compress(raw_scanlines)
    idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF)
    idat = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + idat_crc
    iend_crc = struct.pack(">I", 0xAE426082)
    iend = struct.pack(">I", 0) + b"IEND" + iend_crc
    content = sig + ihdr + idat + iend
    path.write_bytes(content)
    return content


def make_truncated_png_bytes(full_png: bytes, cut: int = 6) -> bytes:
    """Return ``full_png`` truncated by ``cut`` trailing bytes (invalid/truncated PNG)."""
    return full_png[: len(full_png) - cut]


def canonical_intent_kwargs(
    tmp_path: Path,
    atlas_job_id: str = "atlas-render-job-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    attempt_ordinal: int = 1,
    nonce: str = "m6-nonce-1234567890abcdef1234567890abcdef",
    start_frame: int = 0,
    end_frame: int = 0,
    **overrides: Any,
) -> dict[str, Any]:
    """Build deterministic kwargs for AtlasRenderJobRecord.create_intent."""
    out_parent = str(tmp_path / "renders")
    out_dir = str(tmp_path / "renders" / atlas_job_id)
    kwargs: dict[str, Any] = {
        "atlas_job_id": atlas_job_id,
        "attempt_ordinal": attempt_ordinal,
        "authorization_id": "auth-m6-test",
        "canonical_digital_twin_id": "twin-m6-test",
        "sequence_asset_path": "/Game/AtlasTest/AtlasSequencerFixtureSequence",
        "request_digest": "req-digest-m6",
        "config_digest": "cfg-digest-m6",
        "output_parent_directory": out_parent,
        "output_directory": out_dir,
        "expected_output_spec": {
            "format": "png",
            "width": 1,
            "height": 1,
            "start_frame": start_frame,
            "end_frame": end_frame,
        },
        "created_at": "2026-09-06T00:00:00Z",
        "attempt_nonce": nonce,
    }
    kwargs.update(overrides)
    return kwargs


def make_intent_record(tmp_path: Path, **overrides: Any) -> AtlasRenderJobRecord:
    """Create a fresh PENDING_SUBMISSION intent record (deterministic)."""
    kwargs = canonical_intent_kwargs(tmp_path)
    # If atlas_job_id is overridden, the isolated output directory must be
    # recomputed so it contains the new id (contract: output dir must contain id).
    if "atlas_job_id" in overrides:
        kwargs["output_directory"] = str(Path(tmp_path) / "renders" / overrides["atlas_job_id"])
    for key, val in overrides.items():
        kwargs[key] = val
    return AtlasRenderJobRecord.create_intent(**kwargs)


def make_submitted_record(tmp_path: Path, **overrides: Any) -> AtlasRenderJobRecord:
    """Create an intent record and transition it to SUBMITTED with bound identity."""
    rec = make_intent_record(tmp_path, **{k: v for k, v in overrides.items() if k != "lifecycle_state"})
    return rec.transition(
        lifecycle_state=RenderJobLifecycleState.SUBMITTED,
        atlas_submitted_at="2026-09-06T00:00:01Z",
        engine_accepted_at="2026-09-06T00:00:02Z",
        unreal_job_id="unreal-job-m6-001",
        origin_editor_session_id="session-m6-editor",
        origin_process_id=4242,
        origin_process_creation_time="2026-09-06T00:00:00Z",
        last_observed_at="2026-09-06T00:00:02Z",
    )


def make_store(tmp_path: Path) -> AtlasRenderJobStore:
    return AtlasRenderJobStore(tmp_path / "store")


def make_receipt_store(tmp_path: Path) -> UnrealRenderReceiptStore:
    return UnrealRenderReceiptStore(tmp_path / "receipts" / "rcpt.json")


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_valid_render_artifact(
    record: AtlasRenderJobRecord,
    filename: str = "AtlasRender_0000.png",
    width: int = 1,
    height: int = 1,
) -> tuple[Path, bytes]:
    """Write a valid PNG into record.output_directory and return (path, bytes)."""
    out = Path(record.output_directory)
    out.mkdir(parents=True, exist_ok=True)
    p = out / filename
    data = make_valid_png(p, width=width, height=height)
    return p, data


def build_finished_candidate(
    record: AtlasRenderJobRecord,
    *,
    artifact_paths: Optional[Sequence[str]] = None,
    artifact_manifest: Optional[Sequence[Mapping[str, Any]]] = None,
    phase: str = "FINISHED",
    phase_sequence: int = 3,
    hmac_digest: Optional[str] = None,
    override: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Build a terminal reconcile candidate matching the coordinator's expectations.

    If ``hmac_digest`` is omitted, it is computed from ``record.attempt_nonce``
    using the exact canonical payload the coordinator reconstructs in
    ``_handle_finished_candidate`` so that a valid Case B completes.
    """
    if artifact_paths is None:
        artifact_paths = []
    if artifact_manifest is None:
        artifact_manifest = []
    outs = [str(p) for p in artifact_paths]
    candidate: dict[str, Any] = {
        "atlas_job_id": record.atlas_job_id,
        "job_id": record.unreal_job_id or "unreal-job-m6-001",
        "sequence_asset_path": record.sequence_asset_path,
        "authorization_id": record.authorization_id,
        "canonical_digital_twin_id": record.canonical_digital_twin_id,
        "config_digest": record.config_digest,
        "output_directory": record.output_directory,
        "phase": phase,
        "phase_sequence": phase_sequence,
        "editor_session_id": record.origin_editor_session_id or "session-m6-editor",
        "process_id": record.origin_process_id or 4242,
        "process_creation_time_utc": record.origin_process_creation_time or "2026-09-06T00:00:00Z",
        "expected_output_spec": dict(record.expected_output_spec),
        "status": "completed",
        "finished": True,
        "success": True,
        "failed": False,
        "output_files": outs,
        "output_manifest": [dict(m) for m in artifact_manifest],
        "state_source": "witness_journal",
    }
    if hmac_digest is None and record.attempt_nonce is not None:
        canonical_payload = {
            "schema_version": 1,
            "atlas_job_id": record.atlas_job_id,
            "unreal_job_id": candidate["job_id"],
            "attempt_ordinal": record.attempt_ordinal,
            "phase": phase,
            "phase_sequence": phase_sequence,
            "editor_session_id": candidate["editor_session_id"],
            "process_creation_time_utc": candidate["process_creation_time_utc"],
            "output_directory": record.output_directory,
            "output_manifest": candidate["output_manifest"],
        }
        candidate["entry_digest"] = compute_journal_hmac(record.attempt_nonce, canonical_payload)
    elif hmac_digest is not None:
        candidate["entry_digest"] = hmac_digest
    if override:
        candidate.update({k: v for k, v in override.items()})
        candidate["output_files"] = [str(p) for p in candidate["output_files"]]
    return candidate


def make_manifest_for(record: AtlasRenderJobRecord, paths: Sequence[Path]) -> list[dict[str, Any]]:
    return [
        {
            "path": str(p),
            "size": len(p.read_bytes()),
            "sha256": sha256_of(p.read_bytes()),
        }
        for p in paths
    ]


class ScriptedCoordinatorAdapter:
    """Fake adapter returning a scripted reconcile response.

    This deterministically injects engine failure states without a live transport.
    """

    def __init__(
        self,
        *,
        reconcile_response: Optional[Mapping[str, Any]] = None,
        capability_error: Optional[Exception] = None,
        reconcile_error: Optional[Exception] = None,
    ) -> None:
        self.reconcile_response = dict(reconcile_response or {"journal_status": "COMPLETE", "known_jobs": []})
        self.capability_error = capability_error
        self.reconcile_error = reconcile_error
        self.reconcile_query_count = 0
        self.capability_call_count = 0
        self.apply_authorized_called = False

    def assert_recovery_capable(self, authorization_id: str) -> None:
        self.capability_call_count += 1
        if self.capability_error is not None:
            raise self.capability_error

    def apply_authorized(self, op: UnrealOperation, authorization_id: str) -> UnrealEvidence:
        self.apply_authorized_called = True
        self.reconcile_query_count += 1
        if self.reconcile_error is not None:
            raise self.reconcile_error
        return UnrealEvidence(
            operation_name=op.name,
            entity_ids=tuple(op.entity_ids),
            observed_state=self.reconcile_response,
            source="unreal-editor-5.6",
            verified=False,
        )


def quiescent_supervisor() -> MagicMock:
    sup = MagicMock(spec=AtlasProcessSupervisor)
    sup.job_handle = 1234
    sup.query_active_processes.return_value = 0
    return sup


def non_quiescent_supervisor(active: int = 2) -> MagicMock:
    sup = MagicMock(spec=AtlasProcessSupervisor)
    sup.job_handle = 1234
    sup.query_active_processes.return_value = active
    return sup


def make_coordinator(
    store: AtlasRenderJobStore,
    adapter: "ScriptedCoordinatorAdapter | Any",
    receipt_store: Optional[UnrealRenderReceiptStore] = None,
    supervisor: Any = None,
    deployment_mode: str = "CONTAINED_JOB_OBJECT",
) -> UnrealRenderRecoveryCoordinator:
    return UnrealRenderRecoveryCoordinator(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store or make_receipt_store(Path(store.root) / ".." / "receipts_m6" / "rcpt.json"),
        supervisor=supervisor,
        deployment_mode=deployment_mode,
    )


def issue_receipt_for(
    record: AtlasRenderJobRecord,
    output_file: Optional[Path] = None,
    *,
    lease_token: int = 1,
    coordinator_id: str = "m6-coordinator",
) -> UnrealRenderReceipt:
    """Issue a verified UnrealRenderReceipt for a fully-verified render artifact."""
    if output_file is None:
        output_file = Path(record.output_directory) / "AtlasRender_0000.png"
        make_valid_png(output_file)
    data = output_file.read_bytes()
    observed = {
        "job_id": record.unreal_job_id or "unreal-job-m6-001",
        "atlas_job_id": record.atlas_job_id,
        "sequence_asset_path": record.sequence_asset_path,
        "authorization_id": record.authorization_id,
        "canonical_digital_twin_id": record.canonical_digital_twin_id,
        "config_digest": record.config_digest,
        "output_directory": record.output_directory,
        "editor_session_id": record.origin_editor_session_id or "session-m6-editor",
        "process_id": record.origin_process_id or 4242,
        "process_creation_time_utc": record.origin_process_creation_time or "2026-09-06T00:00:00Z",
        "expected_output_spec": dict(record.expected_output_spec),
        "status": "finished",
        "finished": True,
        "success": True,
        "failed": False,
        "output_files": [str(output_file)],
        "output_manifest": [
            {"path": str(output_file), "size": len(data), "sha256": sha256_of(data)}
        ],
    }
    # Build verified evidence through the authoritative verifier where possible,
    # mirroring the production boundary (never synthesize verified=True by hand).
    from planning.unreal_evidence_contract import verify_render_job_evidence

    evidence = verify_render_job_evidence(
        operation_name="inspect_render_job",
        entity_ids=("RENDER_RECOVERY",),
        observed_state=observed,
        source="unreal-recovery-coordinator",
        job_record=record,
        evidence_source_class="ENGINE_JOURNAL_ATTESTED",
    )
    return UnrealRenderReceipt.issue(
        evidence,
        atlas_job_id=record.atlas_job_id,
        attempt_ordinal=record.attempt_ordinal,
        authorization_id=record.authorization_id,
        canonical_digital_twin_id=record.canonical_digital_twin_id,
        config_digest=record.config_digest,
        output_directory=record.output_directory,
        lease_token=lease_token,
        coordinator_id=coordinator_id,
    )