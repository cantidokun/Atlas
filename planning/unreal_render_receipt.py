"""Immutable evidence-bound receipt for a completed Unreal render job."""

from dataclasses import dataclass
import hashlib
import hmac
from typing import Mapping

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

    def __post_init__(self) -> None:
        _validate_identity("job_id", self.job_id)
        _validate_identity("sequence_asset_path", self.sequence_asset_path)
        _validate_identity("evidence_digest", self.evidence_digest)

    @property
    def receipt_digest(self) -> str:
        return hashlib.sha256(_canonical_material((self.job_id, self.sequence_asset_path, self.evidence_digest))).hexdigest()

    @classmethod
    def issue(cls, evidence: UnrealEvidence) -> "UnrealRenderReceipt":
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
        return cls(job_id=job_id, sequence_asset_path=sequence_asset_path, evidence_digest=digest_evidence(evidence))

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
