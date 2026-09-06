"""Durable Atlas render job record for cross-process Unreal recovery.

Authoritative specification: docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md §4, §5.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Optional

from planning.unreal_render_job_states import (
    TERMINAL_LIFECYCLE_STATES,
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)


class AtlasRenderJobRecordError(ValueError):
    """Raised when an AtlasRenderJobRecord fails validation or invariant checks."""


# Strict canonical identifier format: atlas-render-job-<uuid> or standard UUIDv4 lowercase
_CANONICAL_ID_PATTERN = re.compile(
    r"^(?:atlas-render-job-)?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def validate_canonical_atlas_job_id(job_id: str) -> str:
    """Validate atlas_job_id format against canonical pattern without path traversal."""
    if not isinstance(job_id, str) or not job_id.strip():
        raise AtlasRenderJobRecordError("atlas_job_id must be a non-empty string")
    normalized = job_id.strip()
    if "/" in normalized or "\\" in normalized or ".." in normalized:
        raise AtlasRenderJobRecordError(f"atlas_job_id contains illegal path characters: {job_id!r}")
    if not _CANONICAL_ID_PATTERN.match(normalized):
        raise AtlasRenderJobRecordError(
            f"atlas_job_id does not match canonical identifier format: {job_id!r}"
        )
    return normalized


def _freeze_dict(val: Any) -> Any:
    if isinstance(val, Mapping):
        return MappingProxyType({k: _freeze_dict(v) for k, v in val.items()})
    if isinstance(val, (list, tuple)):
        return tuple(_freeze_dict(v) for v in val)
    return val


def _thaw_dict(val: Any) -> Any:
    if isinstance(val, (Mapping, MappingProxyType)):
        return {k: _thaw_dict(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_thaw_dict(v) for v in val]
    return val


def compute_authoritative_digest(
    schema_version: int,
    atlas_job_id: str,
    attempt_ordinal: int,
    authorization_id: str,
    canonical_digital_twin_id: str,
    sequence_asset_path: str,
    request_digest: str,
    config_digest: str,
    output_parent_directory: str,
    output_directory: str,
    expected_output_spec: Mapping[str, Any],
) -> str:
    """Compute deterministic SHA-256 over canonicalized authoritative fields."""
    authoritative_payload = {
        "schema_version": schema_version,
        "atlas_job_id": atlas_job_id,
        "attempt_ordinal": attempt_ordinal,
        "authorization_id": authorization_id,
        "canonical_digital_twin_id": canonical_digital_twin_id,
        "sequence_asset_path": sequence_asset_path,
        "request_digest": request_digest,
        "config_digest": config_digest,
        "output_parent_directory": output_parent_directory,
        "output_directory": output_directory,
        "expected_output_spec": _thaw_dict(expected_output_spec),
    }
    encoded = json.dumps(
        authoritative_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class AtlasRenderJobRecord:
    """Versioned immutable record representing one Atlas execution attempt.
    
    Fields are strictly partitioned into:
    - authoritative: Atlas-resolved/authorized intent and plan (immutable root)
    - observed: facts received from Unreal / independent inspection
    - derived: computed values (e.g., authoritative_digest)
    - operational: timestamps, status bookkeeping, references, quarantine
    """

    # --- Authoritative Fields ---
    schema_version: int
    atlas_job_id: str
    attempt_ordinal: int
    authorization_id: str
    canonical_digital_twin_id: str
    sequence_asset_path: str
    request_digest: str
    config_digest: str
    output_parent_directory: str
    output_directory: str
    expected_output_spec: Mapping[str, Any]

    # --- Operational / Lifecycle Fields ---
    lifecycle_state: RenderJobLifecycleState
    recovery_status: RenderJobRecoveryStatus
    created_at: str
    atlas_submitted_at: Optional[str]
    engine_accepted_at: Optional[str]
    execution_deadline: Optional[str]
    submission_deadline: Optional[str]

    # --- Observed Fields (from Unreal / worker) ---
    unreal_job_id: Optional[str]
    origin_editor_session_id: Optional[str]
    origin_process_id: Optional[int]
    origin_process_creation_time: Optional[str]
    last_observed_revision: int
    last_observed_at: Optional[str]

    # --- Operational Bookkeeping & References ---
    recovery_attempts_or_ambiguity_count: int
    failure_reason: Optional[str]
    quarantine_path: Optional[str]
    receipt_reference: Optional[str]
    manifest_reference: Optional[str]

    # --- Derived Integrity Field ---
    authoritative_digest: str

    # --- Operational Extensions (M4) ---
    attempt_nonce: Optional[str] = None
    last_accepted_lease_token: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.schema_version, int) or isinstance(self.schema_version, bool):
            raise TypeError("schema_version must be an integer")
        if self.schema_version != 1:
            raise AtlasRenderJobRecordError(f"unsupported schema_version: {self.schema_version}")

        # Validate ID & path safety
        validate_canonical_atlas_job_id(self.atlas_job_id)

        if not isinstance(self.attempt_ordinal, int) or isinstance(self.attempt_ordinal, bool) or self.attempt_ordinal < 1:
            raise AtlasRenderJobRecordError("attempt_ordinal must be a positive integer >= 1")

        for name, val in [
            ("authorization_id", self.authorization_id),
            ("canonical_digital_twin_id", self.canonical_digital_twin_id),
            ("sequence_asset_path", self.sequence_asset_path),
            ("request_digest", self.request_digest),
            ("config_digest", self.config_digest),
            ("output_parent_directory", self.output_parent_directory),
            ("output_directory", self.output_directory),
            ("created_at", self.created_at),
        ]:
            if not isinstance(val, str) or not val.strip():
                raise AtlasRenderJobRecordError(f"{name} must be a non-empty string")

        if not isinstance(self.expected_output_spec, Mapping):
            raise TypeError("expected_output_spec must be a mapping")

        # Freeze expected_output_spec
        object.__setattr__(self, "expected_output_spec", _freeze_dict(self.expected_output_spec))

        # Enforce output directory isolation: output_directory must be inside output_parent_directory
        # and contain atlas_job_id
        if self.atlas_job_id not in self.output_directory:
            raise AtlasRenderJobRecordError(
                f"output_directory {self.output_directory!r} must contain atlas_job_id {self.atlas_job_id!r}"
            )

        # Lifecycle and recovery status validation
        if not isinstance(self.lifecycle_state, RenderJobLifecycleState):
            raise TypeError(f"lifecycle_state must be a RenderJobLifecycleState, got {type(self.lifecycle_state)}")
        if not isinstance(self.recovery_status, RenderJobRecoveryStatus):
            raise TypeError(f"recovery_status must be a RenderJobRecoveryStatus, got {type(self.recovery_status)}")

        # Authoritative digest verification
        expected_digest = compute_authoritative_digest(
            schema_version=self.schema_version,
            atlas_job_id=self.atlas_job_id,
            attempt_ordinal=self.attempt_ordinal,
            authorization_id=self.authorization_id,
            canonical_digital_twin_id=self.canonical_digital_twin_id,
            sequence_asset_path=self.sequence_asset_path,
            request_digest=self.request_digest,
            config_digest=self.config_digest,
            output_parent_directory=self.output_parent_directory,
            output_directory=self.output_directory,
            expected_output_spec=self.expected_output_spec,
        )
        if self.authoritative_digest != expected_digest:
            raise AtlasRenderJobRecordError(
                f"authoritative_digest mismatch: expected {expected_digest}, got {self.authoritative_digest}"
            )

    @classmethod
    def create_intent(
        cls,
        *,
        atlas_job_id: str,
        attempt_ordinal: int,
        authorization_id: str,
        canonical_digital_twin_id: str,
        sequence_asset_path: str,
        request_digest: str,
        config_digest: str,
        output_parent_directory: str,
        output_directory: str,
        expected_output_spec: Mapping[str, Any],
        created_at: str,
        submission_deadline: Optional[str] = None,
        execution_deadline: Optional[str] = None,
        attempt_nonce: Optional[str] = None,
        last_accepted_lease_token: int = 0,
    ) -> "AtlasRenderJobRecord":
        """Factory for a fresh PENDING_SUBMISSION execution intent record."""
        validate_canonical_atlas_job_id(atlas_job_id)
        schema_version = 1
        digest = compute_authoritative_digest(
            schema_version=schema_version,
            atlas_job_id=atlas_job_id,
            attempt_ordinal=attempt_ordinal,
            authorization_id=authorization_id,
            canonical_digital_twin_id=canonical_digital_twin_id,
            sequence_asset_path=sequence_asset_path,
            request_digest=request_digest,
            config_digest=config_digest,
            output_parent_directory=output_parent_directory,
            output_directory=output_directory,
            expected_output_spec=expected_output_spec,
        )
        return cls(
            schema_version=schema_version,
            atlas_job_id=atlas_job_id,
            attempt_ordinal=attempt_ordinal,
            authorization_id=authorization_id,
            canonical_digital_twin_id=canonical_digital_twin_id,
            sequence_asset_path=sequence_asset_path,
            request_digest=request_digest,
            config_digest=config_digest,
            output_parent_directory=output_parent_directory,
            output_directory=output_directory,
            expected_output_spec=expected_output_spec,
            lifecycle_state=RenderJobLifecycleState.PENDING_SUBMISSION,
            recovery_status=RenderJobRecoveryStatus.NONE,
            created_at=created_at,
            atlas_submitted_at=None,
            engine_accepted_at=None,
            execution_deadline=execution_deadline,
            submission_deadline=submission_deadline,
            unreal_job_id=None,
            origin_editor_session_id=None,
            origin_process_id=None,
            origin_process_creation_time=None,
            last_observed_revision=0,
            last_observed_at=None,
            recovery_attempts_or_ambiguity_count=0,
            failure_reason=None,
            quarantine_path=None,
            receipt_reference=None,
            manifest_reference=None,
            authoritative_digest=digest,
            attempt_nonce=attempt_nonce,
            last_accepted_lease_token=last_accepted_lease_token,
        )

    def transition(
        self,
        *,
        lifecycle_state: Optional[RenderJobLifecycleState] = None,
        recovery_status: Optional[RenderJobRecoveryStatus] = None,
        atlas_submitted_at: Optional[str] = None,
        engine_accepted_at: Optional[str] = None,
        unreal_job_id: Optional[str] = None,
        origin_editor_session_id: Optional[str] = None,
        origin_process_id: Optional[int] = None,
        origin_process_creation_time: Optional[str] = None,
        last_observed_at: Optional[str] = None,
        failure_reason: Optional[str] = None,
        quarantine_path: Optional[str] = None,
        receipt_reference: Optional[str] = None,
        manifest_reference: Optional[str] = None,
        attempt_nonce: Optional[str] = None,
        last_accepted_lease_token: Optional[int] = None,
        increment_ambiguity: bool = False,
    ) -> "AtlasRenderJobRecord":
        """Produce an updated record with validated state transitions.
        
        Authoritative plan fields cannot be modified.
        Terminal states cannot regress.
        """
        new_lifecycle = lifecycle_state or self.lifecycle_state

        # Enforce terminal state non-regression
        if self.lifecycle_state in TERMINAL_LIFECYCLE_STATES:
            if new_lifecycle != self.lifecycle_state:
                raise AtlasRenderJobRecordError(
                    f"illegal terminal state regression from {self.lifecycle_state} to {new_lifecycle}"
                )

        # Enforce no synthetic success from disk artifacts
        if (
            new_lifecycle in (RenderJobLifecycleState.VERIFIED, RenderJobLifecycleState.FINALIZED)
            and not self.unreal_job_id
            and not unreal_job_id
        ):
            raise AtlasRenderJobRecordError(
                "cannot transition to verified/finalized without an attributable engine job identity"
            )

        new_revision = self.last_observed_revision + 1
        new_ambiguity = (
            self.recovery_attempts_or_ambiguity_count + 1
            if increment_ambiguity
            else self.recovery_attempts_or_ambiguity_count
        )

        return AtlasRenderJobRecord(
            schema_version=self.schema_version,
            atlas_job_id=self.atlas_job_id,
            attempt_ordinal=self.attempt_ordinal,
            authorization_id=self.authorization_id,
            canonical_digital_twin_id=self.canonical_digital_twin_id,
            sequence_asset_path=self.sequence_asset_path,
            request_digest=self.request_digest,
            config_digest=self.config_digest,
            output_parent_directory=self.output_parent_directory,
            output_directory=self.output_directory,
            expected_output_spec=self.expected_output_spec,
            lifecycle_state=new_lifecycle,
            recovery_status=recovery_status or self.recovery_status,
            created_at=self.created_at,
            atlas_submitted_at=atlas_submitted_at or self.atlas_submitted_at,
            engine_accepted_at=engine_accepted_at or self.engine_accepted_at,
            execution_deadline=self.execution_deadline,
            submission_deadline=self.submission_deadline,
            unreal_job_id=unreal_job_id or self.unreal_job_id,
            origin_editor_session_id=origin_editor_session_id or self.origin_editor_session_id,
            origin_process_id=origin_process_id if origin_process_id is not None else self.origin_process_id,
            origin_process_creation_time=origin_process_creation_time or self.origin_process_creation_time,
            last_observed_revision=new_revision,
            last_observed_at=last_observed_at or self.last_observed_at,
            recovery_attempts_or_ambiguity_count=new_ambiguity,
            failure_reason=failure_reason or self.failure_reason,
            quarantine_path=quarantine_path or self.quarantine_path,
            receipt_reference=receipt_reference or self.receipt_reference,
            manifest_reference=manifest_reference or self.manifest_reference,
            authoritative_digest=self.authoritative_digest,
            attempt_nonce=attempt_nonce or self.attempt_nonce,
            last_accepted_lease_token=last_accepted_lease_token if last_accepted_lease_token is not None else self.last_accepted_lease_token,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to detached JSON-serializable dictionary."""
        return {
            "schema_version": self.schema_version,
            "atlas_job_id": self.atlas_job_id,
            "attempt_ordinal": self.attempt_ordinal,
            "authorization_id": self.authorization_id,
            "canonical_digital_twin_id": self.canonical_digital_twin_id,
            "sequence_asset_path": self.sequence_asset_path,
            "request_digest": self.request_digest,
            "config_digest": self.config_digest,
            "output_parent_directory": self.output_parent_directory,
            "output_directory": self.output_directory,
            "expected_output_spec": _thaw_dict(self.expected_output_spec),
            "lifecycle_state": self.lifecycle_state.value,
            "recovery_status": self.recovery_status.value,
            "created_at": self.created_at,
            "atlas_submitted_at": self.atlas_submitted_at,
            "engine_accepted_at": self.engine_accepted_at,
            "execution_deadline": self.execution_deadline,
            "submission_deadline": self.submission_deadline,
            "unreal_job_id": self.unreal_job_id,
            "origin_editor_session_id": self.origin_editor_session_id,
            "origin_process_id": self.origin_process_id,
            "origin_process_creation_time": self.origin_process_creation_time,
            "last_observed_revision": self.last_observed_revision,
            "last_observed_at": self.last_observed_at,
            "recovery_attempts_or_ambiguity_count": self.recovery_attempts_or_ambiguity_count,
            "failure_reason": self.failure_reason,
            "quarantine_path": self.quarantine_path,
            "receipt_reference": self.receipt_reference,
            "manifest_reference": self.manifest_reference,
            "attempt_nonce": self.attempt_nonce,
            "last_accepted_lease_token": self.last_accepted_lease_token,
            "authoritative_digest": self.authoritative_digest,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AtlasRenderJobRecord":
        """Reconstruct record from dictionary with fail-closed schema validation."""
        if not isinstance(data, Mapping):
            raise TypeError("record payload must be a mapping")

        base_required_keys = {
            "schema_version",
            "atlas_job_id",
            "attempt_ordinal",
            "authorization_id",
            "canonical_digital_twin_id",
            "sequence_asset_path",
            "request_digest",
            "config_digest",
            "output_parent_directory",
            "output_directory",
            "expected_output_spec",
            "lifecycle_state",
            "recovery_status",
            "created_at",
            "atlas_submitted_at",
            "engine_accepted_at",
            "execution_deadline",
            "submission_deadline",
            "unreal_job_id",
            "origin_editor_session_id",
            "origin_process_id",
            "origin_process_creation_time",
            "last_observed_revision",
            "last_observed_at",
            "recovery_attempts_or_ambiguity_count",
            "failure_reason",
            "quarantine_path",
            "receipt_reference",
            "manifest_reference",
            "authoritative_digest",
        }
        actual_keys = set(data.keys())
        missing = base_required_keys - actual_keys
        if missing:
            raise AtlasRenderJobRecordError(f"missing required fields in record: {sorted(missing)}")
        allowed_keys = base_required_keys | {"attempt_nonce", "last_accepted_lease_token"}
        extra = actual_keys - allowed_keys
        if extra:
            raise AtlasRenderJobRecordError(f"extra unknown fields in record: {sorted(extra)}")

        try:
            lifecycle = RenderJobLifecycleState(data["lifecycle_state"])
        except ValueError as exc:
            raise AtlasRenderJobRecordError(f"invalid lifecycle_state: {data['lifecycle_state']!r}") from exc

        try:
            recovery = RenderJobRecoveryStatus(data["recovery_status"])
        except ValueError as exc:
            raise AtlasRenderJobRecordError(f"invalid recovery_status: {data['recovery_status']!r}") from exc

        return cls(
            schema_version=data["schema_version"],
            atlas_job_id=data["atlas_job_id"],
            attempt_ordinal=data["attempt_ordinal"],
            authorization_id=data["authorization_id"],
            canonical_digital_twin_id=data["canonical_digital_twin_id"],
            sequence_asset_path=data["sequence_asset_path"],
            request_digest=data["request_digest"],
            config_digest=data["config_digest"],
            output_parent_directory=data["output_parent_directory"],
            output_directory=data["output_directory"],
            expected_output_spec=data["expected_output_spec"],
            lifecycle_state=lifecycle,
            recovery_status=recovery,
            created_at=data["created_at"],
            atlas_submitted_at=data["atlas_submitted_at"],
            engine_accepted_at=data["engine_accepted_at"],
            execution_deadline=data["execution_deadline"],
            submission_deadline=data["submission_deadline"],
            unreal_job_id=data["unreal_job_id"],
            origin_editor_session_id=data["origin_editor_session_id"],
            origin_process_id=data["origin_process_id"],
            origin_process_creation_time=data["origin_process_creation_time"],
            last_observed_revision=data["last_observed_revision"],
            last_observed_at=data["last_observed_at"],
            recovery_attempts_or_ambiguity_count=data["recovery_attempts_or_ambiguity_count"],
            failure_reason=data["failure_reason"],
            quarantine_path=data["quarantine_path"],
            receipt_reference=data["receipt_reference"],
            manifest_reference=data["manifest_reference"],
            attempt_nonce=data.get("attempt_nonce"),
            last_accepted_lease_token=data.get("last_accepted_lease_token", 0),
            authoritative_digest=data["authoritative_digest"],
        )
