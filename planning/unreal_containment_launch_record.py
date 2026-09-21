"""Atlas containment launch record (Contract V1 §9 and §10 *Containment Launch Record*).

The containment keeper creates the attempt's Job Object, launches the engine inside it
(CREATE_SUSPENDED -> assign -> resume) and MUST durably record the launch identity of
that object BEFORE the engine is resumed. The resulting artifact is the *identity
claim* that lets a later recovery pass attribute §9 quiescence to THIS attempt's
containment object:

    <store root>/containment/<atlas_job_id>__<attempt_ordinal>.json

Why a separate artifact
-----------------------
* It is Atlas-side identity evidence for the containment object, while the engine
  journal is the engine's witness of the render. Keeping them apart prevents the
  journal (engine-authored) from becoming the only authority, and keeps the launch
  record out of the §10 witness directory.
* It is **identity evidence, never an authority**: it cannot authorize execution,
  cannot by itself satisfy quiescence, cannot produce a receipt, and never replaces
  the durable journal.

Authentication (and nonce custody)
----------------------------------
``launch_record_digest = HMAC-SHA256(key=UTF8(attempt_nonce), message=canonical payload)``

The ``attempt_nonce`` is the per-attempt Atlas-generated secret that already keys the
journal's ``entry_digest``. Custody rules enforced here:

* the nonce is supplied to the keeper only through the authorized in-process launch
  boundary (:func:`build_launch_record` takes it as an argument - never argv, env,
  file, log, or transport);
* it is never serialized: :func:`write_launch_record` refuses to persist a payload
  that contains the nonce, and the nonce is not a field of the record;
* it is never reused: :func:`write_launch_record` refuses to overwrite an existing
  attempt record;
* it cannot be replaced: verification recomputes the digest from the *durable render
  record's* persisted ``attempt_nonce``, so a keeper-minted substitute fails closed.

Fail-closed semantics: a missing/empty/unverifiable nonce, a missing or tampered
record, an attempt-identity mismatch, or a project-identity mismatch all return a
refusal - callers must treat the attempt's containment as unprovable.
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple

from planning.unreal_render_job_record import validate_canonical_atlas_job_id

#: Directory (under the durable store root) holding launch records.
CONTAINMENT_DIRECTORY_NAME = "containment"

#: Launch-record schema version.
LAUNCH_RECORD_SCHEMA_VERSION = 1

#: Deployment mode this artifact is defined for (Contract V1 §9.272).
DEPLOYMENT_MODE_CONTAINED_JOB_OBJECT = "CONTAINED_JOB_OBJECT"

#: Fields covered by the authenticated digest (everything except the digest itself).
SIGNED_LAUNCH_FIELDS: Tuple[str, ...] = (
    "record_schema_version",
    "atlas_job_id",
    "attempt_ordinal",
    "deployment_mode",
    "job_identity_descriptor",
    "engine_pid",
    "process_creation_time_utc",
    "launch_composition_processes",
    "project_identity",
    "uproject_digest",
    "keeper_identity",
    "editor_session_id",
    "written_at_utc",
)

#: Uppercase hex-ASCII pattern for digests.
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class ContainmentLaunchRecordError(RuntimeError):
    """Base error for containment launch-record handling."""


class ContainmentNonceCustodyError(ContainmentLaunchRecordError):
    """Raised when the per-attempt nonce cannot be held within its custody rules."""


def require_attempt_nonce(attempt_nonce: Any) -> str:
    """Return the attempt nonce, or fail closed if it is missing/not a secret.

    The nonce is a per-attempt Atlas-generated 256-bit hex secret (Contract V1 §10).
    An absent, empty, non-string, or malformed nonce means no authenticated launch
    record can be produced, which means the attempt's containment is unprovable.
    """
    if not isinstance(attempt_nonce, str) or not attempt_nonce.strip():
        raise ContainmentNonceCustodyError(
            "attempt_nonce is missing or empty: no authenticated launch record can be "
            "produced for this attempt (fail closed)"
        )
    return attempt_nonce


def assert_nonce_belongs_to_record(attempt_nonce: Any, job_record: Any) -> None:
    """Fail closed unless ``attempt_nonce`` is the durable record's own nonce.

    This is what stops a keeper from *creating a replacement* nonce for an attempt:
    the keeper-held secret must be byte-identical to the nonce the authorized
    submitter persisted in the durable record.
    """
    supplied = require_attempt_nonce(attempt_nonce)
    persisted = getattr(job_record, "attempt_nonce", None)
    if not isinstance(persisted, str) or not persisted:
        raise ContainmentNonceCustodyError(
            "durable render record carries no attempt_nonce: the containment launch "
            "record cannot be authenticated (fail closed)"
        )
    if not hmac.compare_digest(supplied, persisted):
        raise ContainmentNonceCustodyError(
            "supplied attempt_nonce does not match the durable render record: the keeper "
            "may not create or replace an attempt nonce (fail closed)"
        )


def canonical_launch_payload_bytes(payload: Mapping[str, Any]) -> bytes:
    """Deterministic canonical UTF-8 bytes for a launch-record payload.

    Compact separators, sorted keys, ASCII-escaped: byte-identical for identical
    logical content regardless of dict insertion order or frozen wrappers.
    """
    return json.dumps(
        {k: payload[k] for k in sorted(payload)},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def compute_launch_record_digest(attempt_nonce: str, payload: Mapping[str, Any]) -> str:
    """HMAC-SHA256 over the canonical launch payload, keyed by UTF8(attempt_nonce)."""
    key = require_attempt_nonce(attempt_nonce).encode("utf-8")
    return hmac.new(key, canonical_launch_payload_bytes(payload), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class ContainmentLaunchRecord:
    """Durable, attempt-bound launch identity of one containment Job Object."""

    atlas_job_id: str
    attempt_ordinal: int
    deployment_mode: str
    engine_pid: int
    process_creation_time_utc: str
    launch_composition_processes: int
    project_identity: str
    uproject_digest: str
    keeper_identity: str
    written_at_utc: str
    launch_record_digest: str
    job_identity_descriptor: Optional[str] = None
    editor_session_id: Optional[str] = None
    record_schema_version: int = LAUNCH_RECORD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        validate_canonical_atlas_job_id(self.atlas_job_id)
        if isinstance(self.attempt_ordinal, bool) or not isinstance(self.attempt_ordinal, int) \
                or self.attempt_ordinal < 1:
            raise ContainmentLaunchRecordError("attempt_ordinal must be a positive integer >= 1")
        if self.deployment_mode != DEPLOYMENT_MODE_CONTAINED_JOB_OBJECT:
            raise ContainmentLaunchRecordError(
                f"launch records exist only for {DEPLOYMENT_MODE_CONTAINED_JOB_OBJECT!r}; "
                f"got {self.deployment_mode!r}"
            )
        if isinstance(self.launch_composition_processes, bool) \
                or not isinstance(self.launch_composition_processes, int) \
                or self.launch_composition_processes < 1:
            raise ContainmentLaunchRecordError(
                "launch_composition_processes must be an integer >= 1 (a launch that "
                "contained nothing is not a containment)"
            )
        if isinstance(self.engine_pid, bool) or not isinstance(self.engine_pid, int) \
                or self.engine_pid < 1:
            raise ContainmentLaunchRecordError("engine_pid must be a positive integer")
        for name in ("process_creation_time_utc", "project_identity", "uproject_digest",
                     "keeper_identity", "written_at_utc"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ContainmentLaunchRecordError(f"{name} must be a non-empty string")
        if not _HEX64_RE.match(self.uproject_digest):
            raise ContainmentLaunchRecordError("uproject_digest must be a 64-char lowercase hex digest")
        if not _HEX64_RE.match(self.launch_record_digest):
            raise ContainmentLaunchRecordError(
                "launch_record_digest must be a 64-char lowercase hex HMAC digest"
            )

    # -- serialization -----------------------------------------------------
    def signed_payload(self) -> dict:
        """The authenticated payload (every field except the digest)."""
        return {name: getattr(self, name) for name in SIGNED_LAUNCH_FIELDS}

    def to_dict(self) -> dict:
        payload = self.signed_payload()
        payload["launch_record_digest"] = self.launch_record_digest
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ContainmentLaunchRecord":
        if not isinstance(data, Mapping):
            raise ContainmentLaunchRecordError("launch record must be a JSON object")
        unknown = set(data) - set(SIGNED_LAUNCH_FIELDS) - {"launch_record_digest"}
        if unknown:
            raise ContainmentLaunchRecordError(
                f"launch record carries unknown fields: {sorted(unknown)}"
            )
        missing = [name for name in SIGNED_LAUNCH_FIELDS if name not in data]
        if missing:
            raise ContainmentLaunchRecordError(
                f"launch record is missing required fields: {missing}"
            )
        digest = data.get("launch_record_digest")
        if not isinstance(digest, str):
            raise ContainmentLaunchRecordError("launch record is missing launch_record_digest")
        return cls(
            atlas_job_id=data["atlas_job_id"],
            attempt_ordinal=data["attempt_ordinal"],
            deployment_mode=data["deployment_mode"],
            job_identity_descriptor=data.get("job_identity_descriptor"),
            engine_pid=data["engine_pid"],
            process_creation_time_utc=data["process_creation_time_utc"],
            launch_composition_processes=data["launch_composition_processes"],
            project_identity=data["project_identity"],
            uproject_digest=data["uproject_digest"],
            keeper_identity=data["keeper_identity"],
            editor_session_id=data.get("editor_session_id"),
            written_at_utc=data["written_at_utc"],
            launch_record_digest=digest,
            record_schema_version=data["record_schema_version"],
        )

    # -- verification ------------------------------------------------------
    def verify_digest(self, attempt_nonce: Any) -> bool:
        """True only when the digest verifies against this attempt's nonce."""
        try:
            expected = compute_launch_record_digest(attempt_nonce, self.signed_payload())
        except ContainmentLaunchRecordError:
            return False
        return hmac.compare_digest(expected, self.launch_record_digest)

    def verify_against_job_record(self, job_record: Any) -> Tuple[bool, str]:
        """Contract V1 §9 conjunct 4: bind the launch record to the durable render record.

        Establishes launch record <-> durable record agreement on ``atlas_job_id``,
        ``attempt_ordinal`` and the authenticated attempt nonce. Returns
        ``(True, "")`` only when every binding holds.
        """
        if job_record is None:
            return False, "no durable render record supplied to bind the launch record against"
        stored_atlas_job_id = getattr(job_record, "atlas_job_id", None)
        if stored_atlas_job_id != self.atlas_job_id:
            return False, (
                f"launch record atlas_job_id {self.atlas_job_id!r} does not match the durable "
                f"render record {stored_atlas_job_id!r}"
            )
        stored_ordinal = getattr(job_record, "attempt_ordinal", None)
        if stored_ordinal != self.attempt_ordinal:
            return False, (
                f"launch record attempt_ordinal {self.attempt_ordinal} does not match the durable "
                f"render record {stored_ordinal}"
            )
        if self.record_schema_version != LAUNCH_RECORD_SCHEMA_VERSION:
            return False, (
                f"unsupported launch-record schema version {self.record_schema_version}"
            )
        try:
            prefix = require_attempt_nonce(getattr(job_record, "attempt_nonce", None))
        except ContainmentNonceCustodyError as exc:
            return False, str(exc)
        expected = compute_launch_record_digest(prefix, self.signed_payload())
        if not hmac.compare_digest(expected, self.launch_record_digest):
            return False, (
                "launch record HMAC authentication failed against the durable record's "
                "attempt_nonce (UNTRUSTED_LAUNCH_RECORD)"
            )
        return True, ""


def build_launch_record(
    *,
    atlas_job_id: str,
    attempt_ordinal: int,
    attempt_nonce: str,
    engine_pid: int,
    process_creation_time_utc: str,
    launch_composition_processes: int,
    project_identity: str,
    uproject_digest: str,
    keeper_identity: str,
    job_identity_descriptor: Optional[str] = None,
    editor_session_id: Optional[str] = None,
    written_at_utc: Optional[str] = None,
    deployment_mode: str = DEPLOYMENT_MODE_CONTAINED_JOB_OBJECT,
) -> ContainmentLaunchRecord:
    """Build (and authenticate) the launch record for one attempt.

    ``editor_session_id`` MUST be left ``None`` unless it is genuinely known before the
    engine is resumed; the engine-minted session identity arrives later through the
    journal. No field is fabricated.
    """
    written = written_at_utc or datetime.datetime.now(datetime.timezone.utc).isoformat()
    payload = {
        "record_schema_version": LAUNCH_RECORD_SCHEMA_VERSION,
        "atlas_job_id": atlas_job_id,
        "attempt_ordinal": attempt_ordinal,
        "deployment_mode": deployment_mode,
        "job_identity_descriptor": job_identity_descriptor,
        "engine_pid": engine_pid,
        "process_creation_time_utc": process_creation_time_utc,
        "launch_composition_processes": launch_composition_processes,
        "project_identity": project_identity,
        "uproject_digest": uproject_digest,
        "keeper_identity": keeper_identity,
        "editor_session_id": editor_session_id,
        "written_at_utc": written,
    }
    digest = compute_launch_record_digest(attempt_nonce, payload)
    return ContainmentLaunchRecord(**payload, launch_record_digest=digest)


# ---------------------------------------------------------------------------
# Durable store
# ---------------------------------------------------------------------------
def containment_dir_for_store(store_root: os.PathLike | str) -> Path:
    """``<store root>/containment`` - beside the durable record/store, not the journal."""
    return Path(store_root) / CONTAINMENT_DIRECTORY_NAME


def launch_record_path(
    containment_dir: os.PathLike | str,
    atlas_job_id: str,
    attempt_ordinal: int,
) -> Path:
    """Deterministic path for one attempt's launch record (identity-keyed)."""
    valid_id = validate_canonical_atlas_job_id(atlas_job_id)
    if isinstance(attempt_ordinal, bool) or not isinstance(attempt_ordinal, int) \
            or attempt_ordinal < 1:
        raise ContainmentLaunchRecordError("attempt_ordinal must be a positive integer >= 1")
    return Path(containment_dir) / f"{valid_id}__{attempt_ordinal}.json"


def write_launch_record(
    containment_dir: os.PathLike | str,
    record: ContainmentLaunchRecord,
    *,
    attempt_nonce: Any = None,
) -> Path:
    """Atomically persist one launch record. Never overwrites an existing attempt record.

    ``attempt_nonce`` is accepted only so the writer can *prove* it is not persisting
    the secret: the serialized payload must not contain it.
    """
    directory = Path(containment_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = launch_record_path(directory, record.atlas_job_id, record.attempt_ordinal)
    serialized = json.dumps(record.to_dict(), sort_keys=True, ensure_ascii=True).encode("utf-8")
    if attempt_nonce is not None and isinstance(attempt_nonce, str) and attempt_nonce:
        if attempt_nonce.encode("utf-8") in serialized:
            raise ContainmentNonceCustodyError(
                "refusing to persist a launch record containing the attempt nonce in plaintext"
            )
    if target.exists():
        raise ContainmentLaunchRecordError(
            f"launch record for attempt ({record.atlas_job_id}, {record.attempt_ordinal}) "
            "already exists: an attempt identity is never reused or overwritten"
        )
    fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=str(directory))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return target


def load_launch_record(
    containment_dir: os.PathLike | str,
    atlas_job_id: str,
    attempt_ordinal: int,
) -> Optional[ContainmentLaunchRecord]:
    """Load one launch record; ``None`` when absent; raises when unreadable/malformed.

    Absence is "unprovable", never "no containment": callers MUST fail closed.
    """
    path = launch_record_path(containment_dir, atlas_job_id, attempt_ordinal)
    if not path.is_file():
        return None
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ContainmentLaunchRecordError(f"launch record could not be read: {path} ({exc})") from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ContainmentLaunchRecordError(
            f"launch record is not parseable JSON: {path} ({exc.__class__.__name__})"
        ) from exc
    return ContainmentLaunchRecord.from_dict(data)


def verify_launch_record_for_job(
    containment_dir: os.PathLike | str,
    job_record: Any,
) -> Tuple[Optional[ContainmentLaunchRecord], str]:
    """Resolve + authenticate the launch record for a durable render record.

    Returns ``(record, "")`` only when the record exists, parses, and every §9
    conjunct-4 binding holds. Every other outcome returns ``(None, reason)`` so the
    caller fails closed with a recorded reason.
    """
    if job_record is None:
        return None, "no durable render record supplied"
    try:
        record = load_launch_record(
            containment_dir,
            getattr(job_record, "atlas_job_id", ""),
            getattr(job_record, "attempt_ordinal", 0),
        )
    except ContainmentLaunchRecordError as exc:
        return None, str(exc)
    if record is None:
        return None, (
            "no containment launch record exists for attempt "
            f"({getattr(job_record, 'atlas_job_id', None)!r}, "
            f"{getattr(job_record, 'attempt_ordinal', None)!r}): the attempt's Job Object "
            "provenance cannot be established (fail closed)"
        )
    ok, reason = record.verify_against_job_record(job_record)
    if not ok:
        return None, reason
    return record, ""
