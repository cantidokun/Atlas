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
    start_frame: int | None = None
    end_frame: int | None = None
    output_directory: str | None = None
    output_format: str | None = None

    def __post_init__(self) -> None:
        _validate_identity("job_id", self.job_id)
        _validate_identity("sequence_asset_path", self.sequence_asset_path)
        _validate_identity("evidence_digest", self.evidence_digest)
        for name, value in (
            ("output_directory", self.output_directory),
            ("output_format", self.output_format),
        ):
            if value is not None:
                _validate_identity(name, value)
        for name, value in (("start_frame", self.start_frame), ("end_frame", self.end_frame)):
            if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                raise TypeError(f"{name} must be an integer when supplied")
        if (self.start_frame is None) != (self.end_frame is None):
            raise ValueError("start_frame and end_frame must be supplied together")
        if self.start_frame is not None and self.start_frame > self.end_frame:
            raise ValueError("start_frame must not exceed end_frame")

    @property
    def receipt_digest(self) -> str:
        continuity = (
            "" if self.start_frame is None else str(self.start_frame),
            "" if self.end_frame is None else str(self.end_frame),
            "" if self.output_directory is None else self.output_directory,
            "" if self.output_format is None else self.output_format,
        )
        return hashlib.sha256(
            _canonical_material(
                (
                    self.job_id,
                    self.sequence_asset_path,
                    self.evidence_digest,
                    *continuity,
                )
            )
        ).hexdigest()

    def snapshot(self) -> dict[str, Any]:
        """Return a detached JSON-compatible receipt snapshot."""
        snapshot = {
            "job_id": self.job_id,
            "sequence_asset_path": self.sequence_asset_path,
            "evidence_digest": self.evidence_digest,
        }
        if self.start_frame is not None:
            snapshot.update(
                {
                    "start_frame": self.start_frame,
                    "end_frame": self.end_frame,
                    "output_directory": self.output_directory,
                    "output_format": self.output_format,
                }
            )
        return snapshot

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any]) -> "UnrealRenderReceipt":
        """Reconstruct a receipt from an exact persisted snapshot, fail-closed."""
        if not isinstance(snapshot, Mapping):
            raise TypeError("Unreal render receipt snapshot must be a mapping")
        base = {"job_id", "sequence_asset_path", "evidence_digest"}
        extended = base | {"start_frame", "end_frame", "output_directory", "output_format"}
        if set(snapshot) not in (base, extended):
            raise ValueError("Unreal render receipt snapshot fields are invalid")
        kwargs = {
            "job_id": snapshot["job_id"],
            "sequence_asset_path": snapshot["sequence_asset_path"],
            "evidence_digest": snapshot["evidence_digest"],
        }
        if set(snapshot) == extended:
            kwargs.update(
                {
                    "start_frame": snapshot["start_frame"],
                    "end_frame": snapshot["end_frame"],
                    "output_directory": snapshot["output_directory"],
                    "output_format": snapshot["output_format"],
                }
            )
        return cls(**kwargs)

    @classmethod
    def issue(cls, evidence: UnrealEvidence) -> "UnrealRenderReceipt":
        if not isinstance(evidence, UnrealEvidence):
            raise TypeError("evidence must be a UnrealEvidence instance")

        if evidence.operation_name != "inspect_render_job":
            raise ValueError(
                "render receipt must be issued from inspect_render_job evidence"
            )

        if not evidence.verified:
            raise ValueError(
                "render receipt requires verified render-job evidence"
            )

        state = evidence.observed_state
        if not isinstance(state, Mapping):
            raise ValueError(
                "render-job evidence observed_state must be a mapping"
            )
        _require_completed_render_state(state)

        job_id = state.get("job_id")
        sequence_asset_path = state.get("sequence_asset_path")

        _validate_identity("job_id", job_id)
        _validate_identity("sequence_asset_path", sequence_asset_path)

        continuity_keys = {"start_frame", "end_frame", "output_directory", "output_format"}
        if continuity_keys.issubset(state):
            return cls(
                job_id=job_id,
                sequence_asset_path=sequence_asset_path,
                evidence_digest=digest_evidence(evidence),
                start_frame=state["start_frame"],
                end_frame=state["end_frame"],
                output_directory=state["output_directory"],
                output_format=state["output_format"],
            )

        return cls(
            job_id=job_id,
            sequence_asset_path=sequence_asset_path,
            evidence_digest=digest_evidence(evidence),
        )

    def matches(self, evidence: UnrealEvidence) -> bool:
        try:
            candidate = self.issue(evidence)
        except (TypeError, ValueError):
            return False

        return (
            hmac.compare_digest(self.job_id, candidate.job_id)
            and hmac.compare_digest(
                self.sequence_asset_path,
                candidate.sequence_asset_path,
            )
            and hmac.compare_digest(
                self.evidence_digest,
                candidate.evidence_digest,
            )
            and self.start_frame == candidate.start_frame
            and self.end_frame == candidate.end_frame
            and self.output_directory == candidate.output_directory
            and self.output_format == candidate.output_format
        )
