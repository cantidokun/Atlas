"""Immutable evidence-bound receipt for a completed Unreal render job."""

from dataclasses import dataclass
import hashlib
import hmac
from typing import Any, Mapping

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_evidence_digest import digest_evidence


def _validate_identity(name: str, value: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f"{name} must be a non-empty canonical string")
    return value


def _canonical_material(values: tuple[str, ...]) -> bytes:
    encoded = []
    for value in values:
        raw = value.encode("utf-8")
        encoded.append(len(raw).to_bytes(8, "big"))
        encoded.append(raw)
    return b"".join(encoded)


def _require_completed_render_state(state: Mapping[str, object]) -> None:
    """Require the evidence to describe a completed successful render."""
    status = state.get("status")
    success = state.get("success")
    failed = state.get("failed")
    if status not in ("completed", "finished"):
        raise ValueError("render receipt requires semantically completed render evidence")
    if success is not True:
        raise ValueError("render receipt requires successful render evidence")
    if failed is not False:
        raise ValueError("render receipt requires non-failed render evidence")


@dataclass(frozen=True)
class UnrealRenderReceipt:
    job_id: str
    sequence_asset_path: str
    evidence_digest: str
    atlas_job_id: str = ""
    attempt_ordinal: int = 1
    authorization_id: str = ""
    canonical_digital_twin_id: str = ""
    config_digest: str = ""
    output_directory: str = ""
    lease_token: int = 0
    coordinator_id: str = ""

    def __post_init__(self) -> None:
        _validate_identity("job_id", self.job_id)
        _validate_identity("sequence_asset_path", self.sequence_asset_path)
        _validate_identity("evidence_digest", self.evidence_digest)

    @property
    def receipt_digest(self) -> str:
        fields = (
            self.job_id,
            self.sequence_asset_path,
            self.evidence_digest,
            self.atlas_job_id,
            str(self.attempt_ordinal),
            self.authorization_id,
            self.canonical_digital_twin_id,
            self.config_digest,
            self.output_directory,
        )
        return hashlib.sha256(_canonical_material(fields)).hexdigest()

    def snapshot(self) -> dict[str, Any]:
        """Return a detached JSON-compatible receipt snapshot."""
        return {
            "job_id": self.job_id,
            "sequence_asset_path": self.sequence_asset_path,
            "evidence_digest": self.evidence_digest,
            "atlas_job_id": self.atlas_job_id,
            "attempt_ordinal": self.attempt_ordinal,
            "authorization_id": self.authorization_id,
            "canonical_digital_twin_id": self.canonical_digital_twin_id,
            "config_digest": self.config_digest,
            "output_directory": self.output_directory,
            "lease_token": self.lease_token,
            "coordinator_id": self.coordinator_id,
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any]) -> "UnrealRenderReceipt":
        """Reconstruct a receipt from an exact persisted snapshot, fail-closed."""
        if not isinstance(snapshot, Mapping):
            raise TypeError("Unreal render receipt snapshot must be a mapping")
        base_required = {"job_id", "sequence_asset_path", "evidence_digest"}
        if not base_required.issubset(set(snapshot)):
            raise ValueError("Unreal render receipt snapshot missing base required fields")
        allowed = {
            "job_id",
            "sequence_asset_path",
            "evidence_digest",
            "atlas_job_id",
            "attempt_ordinal",
            "authorization_id",
            "canonical_digital_twin_id",
            "config_digest",
            "output_directory",
            "lease_token",
            "coordinator_id",
        }
        if not set(snapshot).issubset(allowed):
            raise ValueError("Unreal render receipt snapshot fields are invalid")
        return cls(
            job_id=snapshot["job_id"],
            sequence_asset_path=snapshot["sequence_asset_path"],
            evidence_digest=snapshot["evidence_digest"],
            atlas_job_id=snapshot.get("atlas_job_id", ""),
            attempt_ordinal=snapshot.get("attempt_ordinal", 1),
            authorization_id=snapshot.get("authorization_id", ""),
            canonical_digital_twin_id=snapshot.get("canonical_digital_twin_id", ""),
            config_digest=snapshot.get("config_digest", ""),
            output_directory=snapshot.get("output_directory", ""),
            lease_token=snapshot.get("lease_token", 0),
            coordinator_id=snapshot.get("coordinator_id", ""),
        )

    @classmethod
    def issue(
        cls,
        evidence: UnrealEvidence,
        *,
        atlas_job_id: str = "",
        attempt_ordinal: int = 1,
        authorization_id: str = "",
        canonical_digital_twin_id: str = "",
        config_digest: str = "",
        output_directory: str = "",
        lease_token: int = 0,
        coordinator_id: str = "",
    ) -> "UnrealRenderReceipt":
        if not isinstance(evidence, UnrealEvidence):
            raise TypeError("evidence must be a UnrealEvidence instance")
        if evidence.operation_name != "inspect_render_job":
            raise ValueError("render receipt must be issued from inspect_render_job evidence")
        if not evidence.verified:
            raise ValueError("render receipt requires verified render-job evidence")
        state = evidence.observed_state
        if not isinstance(state, Mapping):
            raise ValueError("render-job evidence observed_state must be a mapping")
        _require_completed_render_state(state)
        job_id = state.get("job_id")
        sequence_asset_path = state.get("sequence_asset_path")
        _validate_identity("job_id", job_id)
        _validate_identity("sequence_asset_path", sequence_asset_path)
        return cls(
            job_id=job_id,
            sequence_asset_path=sequence_asset_path,
            evidence_digest=digest_evidence(evidence),
            atlas_job_id=atlas_job_id,
            attempt_ordinal=attempt_ordinal,
            authorization_id=authorization_id,
            canonical_digital_twin_id=canonical_digital_twin_id,
            config_digest=config_digest,
            output_directory=output_directory,
            lease_token=lease_token,
            coordinator_id=coordinator_id,
        )

    def matches(self, evidence: UnrealEvidence) -> bool:
        try:
            candidate = self.issue(evidence)
        except (TypeError, ValueError):
            return False
        return (
            hmac.compare_digest(self.job_id, candidate.job_id)
            and hmac.compare_digest(self.sequence_asset_path, candidate.sequence_asset_path)
            and hmac.compare_digest(self.evidence_digest, candidate.evidence_digest)
        )
