"""Canonical journal attestation (Contract V1 §Per-Attempt Nonce and Witness Authentication).

Defines the shared canonical serialization and HMAC-SHA256 witness attestation
used by BOTH Atlas Python and the Unreal C++ engine, so that identical logical
journal payloads produce byte-identical canonical messages and therefore
identical HMAC digests.

Canonical message format
-----------------------
The canonical journal payload is a sequence of the 10 signed fields in a fixed
order, encoded as UTF-8 and concatenated with the ASCII unit separator (\\x1f)
between fields and terminated with the record separator (\\x1e):

    schema_version
    atlas_job_id
    unreal_job_id
    attempt_ordinal
    phase
    phase_sequence
    editor_session_id
    process_creation_time_utc
    output_directory
    output_manifest

Field encoding rules
--------------------
- schema_version     : integer, decimal ASCII (no sign, no leading zeros).
- atlas_job_id       : UTF-8 string, verbatim.
- unreal_job_id      : UTF-8 string, verbatim (the digest covers the value; any
                       embedded separator would change the message and the digest).
- attempt_ordinal    : integer, decimal ASCII.
- phase              : UTF-8 string, verbatim (ACCEPTED/STARTED/FINISHED/FAILED).
- phase_sequence     : integer, decimal ASCII.
- editor_session_id  : UTF-8 string, verbatim.
- process_creation_time_utc : UTF-8 string, verbatim.
- output_directory   : UTF-8 string, verbatim.
- output_manifest    : 0..N entries. Each entry is serialized as:
      path \\x1c size \\x1c sha256 \\x1d
  entries concatenated (no separator between entries beyond \\x1d). An empty
  manifest serializes to the empty string.

The whole message is `field(\\x1f field)*\\x1e` (fields joined by U+001F, then a
trailing U+001E). This is locale-independent, deterministic, and unambiguous
because the separator characters are control codes that never appear in the
length-prefixed field serializations produced by either side.

HMAC
----
    entry_digest = HMAC-SHA256(
        key = UTF8(attempt_nonce),
        message = canonical_message_bytes
    )
    hexdigest (lowercase, 64 chars).

The attempt_nonce is an Atlas-generated 256-bit secret. It is used ONLY as the
HMAC key and is never written to journals/receipts/manifests/logs.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any, Mapping, Sequence


_UF = "\x1f"  # unit separator: between fields
_UR = "\x1e"  # record separator: terminates the message
_CI = "\x1c"  # component separator: within a manifest entry
_CR = "\x1d"  # component record separator: between manifest entries

_SIGNED_FIELDS = (
    "schema_version",
    "atlas_job_id",
    "unreal_job_id",
    "attempt_ordinal",
    "phase",
    "phase_sequence",
    "editor_session_id",
    "process_creation_time_utc",
    "output_directory",
    "output_manifest",
)


def _int_ascii(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"expected integer, got {type(value).__name__}")
    return str(value)


def _manifest_entry_canonical(entry: Mapping[str, Any]) -> str:
    """Serialize one output-manifest entry to canonical UTF-8 string form."""
    path = entry.get("path")
    size = entry.get("size")
    sha256 = entry.get("sha256")
    if not isinstance(path, str):
        raise TypeError("manifest entry 'path' must be a string")
    if isinstance(size, bool) or not isinstance(size, int):
        raise TypeError("manifest entry 'size' must be an integer")
    if not isinstance(sha256, str):
        raise TypeError("manifest entry 'sha256' must be a string")
    return f"{path}{_CI}{_int_ascii(size)}{_CI}{sha256}{_CR}"


def _manifest_canonical(manifest: Any) -> str:
    if manifest is None:
        return ""
    if not isinstance(manifest, Sequence) or isinstance(manifest, (str, bytes)):
        raise TypeError("output_manifest must be a sequence")
    return "".join(_manifest_entry_canonical(e) for e in manifest)


def canonical_attestation_payload(payload: Mapping[str, Any]) -> bytes:
    """Build the canonical UTF-8 message bytes for a journal attestation payload.

    ``payload`` must contain the 10 signed keys (missing ``output_manifest`` is
    treated as an empty manifest; any other missing field fails closed with a
    KeyError/TypeError).
    """
    parts = []
    for key in _SIGNED_FIELDS:
        if key == "output_manifest":
            parts.append(_manifest_canonical(payload.get(key)))
            continue
        if key not in payload:
            raise KeyError(f"canonical attestation payload missing required field: {key!r}")
        value = payload[key]
        if key in ("schema_version", "attempt_ordinal", "phase_sequence"):
            parts.append(_int_ascii(value))
        else:
            if not isinstance(value, str):
                raise TypeError(f"field {key!r} must be a string")
            parts.append(value)
    # Fields joined by unit separator, then a trailing record separator.
    message = _UF.join(parts) + _UR
    return message.encode("utf-8")


def compute_attestation_digest(
    attempt_nonce: str,
    canonical_message: bytes,
) -> str:
    """Compute HMAC-SHA256 over canonical_message keyed by UTF8(attempt_nonce).

    Returns the lowercase 64-char hexdigest.
    """
    if not isinstance(attempt_nonce, str):
        raise TypeError("attempt_nonce must be a string")
    key_bytes = attempt_nonce.encode("utf-8")
    return hmac.new(key_bytes, canonical_message, hashlib.sha256).hexdigest()


def compute_journal_attestation_digest(
    attempt_nonce: str,
    payload: Mapping[str, Any],
) -> str:
    """One-shot helper: canonicalize a payload dict and return its HMAC hexdigest."""
    message = canonical_attestation_payload(payload)
    return compute_attestation_digest(attempt_nonce, message)