"""Pure Temporal v1 recovery checkpoint contract.

This module defines checkpoint shape, digest verification, fail-closed validation, and explicit
reinitialization semantics. It does not implement persistence, locking, transport, or recovery
authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from .admission import AdmissionOutcome, AdmissionState, FromIdentity
from .canonical import sha256_digest
from .model import SourceTime, TemporalValidationError


CHECKPOINT_SCHEMA_VERSION = "1"
COMMITTED = "COMMITTED"


class RecoveryCheckpointError(ValueError):
    """Checkpoint is missing, incomplete, non-committed, or fails integrity validation."""


_REQUIRED_FIELDS = (
    "checkpoint_schema_version",
    "checkpoint_generation",
    "checkpoint_commit_state",
    "checkpoint_digest",
    "stream_id",
    "continuity_id",
    "producer_session_id",
    "ordering_epoch",
    "last_accepted_sequence",
    "last_accepted_source_time",
    "last_accepted_scene_id",
    "last_accepted_state_digest",
    "last_accepted_observation_id",
    "last_accepted_admission_identity_digest",
    "accepted_count",
    "duplicate_acknowledged_count",
    "rejected_stale_count",
    "invalid_count",
    "epoch_count",
    "last_admission_identity_digest",
    "last_admission_outcome",
)


def _require_i64(value: Any, label: str, minimum: Optional[int] = None) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise RecoveryCheckpointError(f"{label} must be an exact int")
    if value < -(1 << 63) or value > (1 << 63) - 1:
        raise RecoveryCheckpointError(f"{label} must fit signed int64")
    if minimum is not None and value < minimum:
        raise RecoveryCheckpointError(f"{label} must be >= {minimum}")
    return value


def _require_string(value: Any, label: str, *, nonempty: bool = True) -> str:
    if type(value) is not str or (nonempty and not value.strip()):
        raise RecoveryCheckpointError(f"{label} must be a non-empty string")
    if any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        raise RecoveryCheckpointError(f"{label} contains a Unicode surrogate")
    return value


def _source_time_dict(source_time: SourceTime) -> Dict[str, Any]:
    return source_time.canonical()


def _source_time_from_dict(value: Mapping[str, Any]) -> SourceTime:
    try:
        rate = value["rate"]
        return SourceTime(
            domain=value["domain"],
            value=value["value"],
            rate_num=rate["num"],
            rate_den=rate["den"],
            ordering_epoch=value["ordering_epoch"],
        )
    except (KeyError, TypeError, TemporalValidationError) as exc:
        raise RecoveryCheckpointError("invalid checkpoint last_accepted_source_time") from exc


def _payload_without_digest(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: payload[key] for key in payload if key != "checkpoint_digest"}


def _validate_complete_payload(payload: Mapping[str, Any]) -> None:
    unknown = [key for key in payload if key not in _REQUIRED_FIELDS]
    if unknown:
        raise RecoveryCheckpointError(
            "ADMISSION_STATE_UNAVAILABLE: unknown checkpoint fields: " + ", ".join(sorted(unknown))
        )
    missing = [key for key in _REQUIRED_FIELDS if key not in payload]
    if missing:
        raise RecoveryCheckpointError(
            "ADMISSION_STATE_UNAVAILABLE: incomplete checkpoint; missing " + ", ".join(missing)
        )

    if payload["checkpoint_schema_version"] != CHECKPOINT_SCHEMA_VERSION:
        raise RecoveryCheckpointError("ADMISSION_STATE_UNAVAILABLE: unsupported checkpoint schema")
    _require_i64(payload["checkpoint_generation"], "checkpoint_generation", minimum=0)
    if payload["checkpoint_commit_state"] != COMMITTED:
        raise RecoveryCheckpointError("ADMISSION_STATE_UNAVAILABLE: checkpoint is not COMMITTED")

    _require_string(payload["stream_id"], "stream_id")
    _require_string(payload["continuity_id"], "continuity_id")
    _require_string(payload["producer_session_id"], "producer_session_id")
    _require_i64(payload["ordering_epoch"], "ordering_epoch", minimum=0)
    _require_i64(payload["last_accepted_sequence"], "last_accepted_sequence", minimum=0)
    _require_string(payload["last_accepted_scene_id"], "last_accepted_scene_id")
    _require_string(payload["last_accepted_state_digest"], "last_accepted_state_digest")
    if len(payload["last_accepted_state_digest"]) != 64 or any(ch not in "0123456789abcdef" for ch in payload["last_accepted_state_digest"]):
        raise RecoveryCheckpointError("ADMISSION_STATE_UNAVAILABLE: invalid last_accepted_state_digest")
    _require_string(payload["last_accepted_observation_id"], "last_accepted_observation_id")
    _require_string(
        payload["last_accepted_admission_identity_digest"],
        "last_accepted_admission_identity_digest",
    if len(payload["last_accepted_admission_identity_digest"]) != 64 or any(ch not in "0123456789abcdef" for ch in payload["last_accepted_admission_identity_digest"]):
        raise RecoveryCheckpointError("ADMISSION_STATE_UNAVAILABLE: invalid last_accepted_admission_identity_digest")
    )

    for name in (
        "accepted_count",
        "duplicate_acknowledged_count",
        "rejected_stale_count",
        "invalid_count",
        "epoch_count",
    ):
        _require_i64(payload[name], name, minimum=0)

    if payload["last_admission_outcome"] not in {item.value for item in AdmissionOutcome}:
        raise RecoveryCheckpointError("ADMISSION_STATE_UNAVAILABLE: invalid last_admission_outcome")

    source_time = _source_time_from_dict(payload["last_accepted_source_time"])
    if source_time.ordering_epoch != payload["ordering_epoch"]:
        raise RecoveryCheckpointError(
            "ADMISSION_STATE_UNAVAILABLE: checkpoint source-time epoch mismatch"
        )

    digest = payload["checkpoint_digest"]
    _require_string(digest, "checkpoint_digest")
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise RecoveryCheckpointError("ADMISSION_STATE_UNAVAILABLE: invalid checkpoint_digest")
    expected = sha256_digest(_payload_without_digest(payload))
    if digest != expected:
        raise RecoveryCheckpointError("ADMISSION_STATE_UNAVAILABLE: checkpoint digest mismatch")


@dataclass(frozen=True)
class AdmissionCheckpoint:
    payload: Mapping[str, Any]

    @classmethod
    def from_state(cls, state: AdmissionState, generation: int) -> "AdmissionCheckpoint":
        if not state.has_baseline:
            raise RecoveryCheckpointError(
                "ADMISSION_STATE_UNAVAILABLE: cannot checkpoint without an accepted baseline"
            )
        source_time = state.last_accepted_source_time
        if source_time is None:
            raise RecoveryCheckpointError("ADMISSION_STATE_UNAVAILABLE: missing source-time cursor")

        payload: Dict[str, Any] = {
            "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
            "checkpoint_generation": _require_i64(generation, "checkpoint_generation", minimum=0),
            "checkpoint_commit_state": COMMITTED,
            "checkpoint_digest": "",
            "stream_id": state.stream_id,
            "continuity_id": state.continuity_id,
            "producer_session_id": state.producer_session_id,
            "ordering_epoch": state.ordering_epoch,
            "last_accepted_sequence": state.last_accepted_sequence,
            "last_accepted_source_time": _source_time_dict(source_time),
            "last_accepted_scene_id": state.last_accepted_scene_id,
            "last_accepted_state_digest": state.last_accepted_state_digest,
            "last_accepted_observation_id": state.last_accepted_observation_id,
            "last_accepted_admission_identity_digest": state.last_accepted_admission_identity_digest,
            "accepted_count": state.accepted_count,
            "duplicate_acknowledged_count": state.duplicate_acknowledged_count,
            "rejected_stale_count": state.rejected_stale_count,
            "invalid_count": state.invalid_count,
            "epoch_count": state.epoch_count,
            "last_admission_identity_digest": state.last_admission_identity_digest,
            "last_admission_outcome": (
                state.last_admission_outcome.value
                if state.last_admission_outcome is not None
                else None
            ),
        }
        payload["checkpoint_digest"] = sha256_digest(_payload_without_digest(payload))
        return cls(payload)

    @classmethod
    def restore(cls, payload: Mapping[str, Any]) -> "AdmissionCheckpoint":
        copied = dict(payload)
        _validate_complete_payload(copied)
        return cls(copied)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.payload)

    def restore_state(self) -> AdmissionState:
        _validate_complete_payload(self.payload)
        p = self.payload
        state = AdmissionState(
            stream_id=p["stream_id"],
            continuity_id=p["continuity_id"],
            producer_session_id=p["producer_session_id"],
            ordering_epoch=p["ordering_epoch"],
            last_accepted_sequence=p["last_accepted_sequence"],
            last_accepted_source_time=_source_time_from_dict(p["last_accepted_source_time"]),
            last_accepted_scene_id=p["last_accepted_scene_id"],
            last_accepted_state_digest=p["last_accepted_state_digest"],
            last_accepted_observation_id=p["last_accepted_observation_id"],
            last_accepted_admission_identity_digest=p["last_accepted_admission_identity_digest"],
            accepted_count=p["accepted_count"],
            duplicate_acknowledged_count=p["duplicate_acknowledged_count"],
            rejected_stale_count=p["rejected_stale_count"],
            invalid_count=p["invalid_count"],
            epoch_count=p["epoch_count"],
            last_admission_identity_digest=p["last_admission_identity_digest"],
            last_admission_outcome=AdmissionOutcome(p["last_admission_outcome"]),
        )
        return state


def validate_reinitialization_declaration(
    state: AdmissionState,
    *,
    new_continuity_id: str,
    new_ordering_epoch: int,
) -> None:
    """Validate the external authority's new TemporalEpochKey declaration.

    A successful call does not mutate the state and does not synthesize a boundary record. The
    recovery authority must then establish a fresh admission baseline; the first valid observation
    is INITIAL_ACCEPTED.
    """
    _require_string(new_continuity_id, "new_continuity_id")
    _require_i64(new_ordering_epoch, "new_ordering_epoch", minimum=0)

    if state.ordering_epoch is None:
        raise RecoveryCheckpointError(
            "ADMISSION_STATE_UNAVAILABLE: no established epoch for reinitialization"
        )
    if new_ordering_epoch <= state.ordering_epoch:
        raise RecoveryCheckpointError(
            "REJECTED_INVALID: explicit recovery reinitialization requires a strictly greater ordering_epoch"
        )
    if new_continuity_id == state.continuity_id:
        raise RecoveryCheckpointError(
            "REJECTED_INVALID: explicit recovery reinitialization requires a new continuity_id"
        )
