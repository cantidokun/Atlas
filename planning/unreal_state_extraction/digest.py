"""The extraction boundary: validation, reconstruction, canonical bytes, SHA-256.

Design source: Revision 3.1 §2 (authority and trust boundary), §4.2 (boundary),
§6.5 (digest boundary), §8.2 (fail-closed rules), §9 (bounds).

The C++ extraction result is **untrusted input**. This module is the only place that
turns a transport response into authoritative extraction material, and it does so in one
order: hardened parse → closed-schema validation → field-by-field reconstruction →
RFC 8785 canonical bytes → SHA-256.

A digest is an identity/integrity value and never a verdict: it MUST NOT set, imply or
substitute ``UnrealEvidence.verified``, and it declares no invariants. Extraction is not
a second verification authority (§2.3–§2.4).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, Mapping

from planning.unreal_state_extraction.errors import (
    ERR_EXTRACTION_ERROR_CODE_UNKNOWN,
    ERR_EXTRACTION_SCHEMA,
    PRODUCER_ERROR_CODES,
    UnrealStateExtractionError,
)
from planning.unreal_state_extraction.jcs import canonical_bytes
from planning.unreal_state_extraction.schema import EXTRACTION_NODE_KEY, validate_value_tree
from planning.unreal_state_extraction.strict_json import loads_strict

#: The transport's message bound, recorded here because it is the extraction's bound too
#: (§9.1). v1 does not redesign the transport: an oversize extraction fails closed on the
#: producer side and is never truncated, chunked or partially returned.
TRANSPORT_MESSAGE_SIZE_LIMIT = 1024 * 1024

#: The augmentation marker injected by the legacy adapter path
#: (``planning/unreal_adapter_production.py``). Its presence is a hard failure: the
#: remedy is to stop augmenting, never to strip the key (§4.2.8).
AUGMENTATION_MARKER = "_session_identity"

_DIGEST_PATTERN = re.compile(r"\A[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class ExtractionResult:
    """A validated extraction: the reconstructed tree, its canonical bytes, its digest."""

    value_tree: Mapping[str, Any]
    canonical_bytes: bytes
    digest: str

    def __post_init__(self) -> None:
        if not _DIGEST_PATTERN.match(self.digest):
            raise UnrealStateExtractionError(
                ERR_EXTRACTION_SCHEMA, f"digest {self.digest!r} is not 64 lowercase hex digits"
            )
        if hashlib.sha256(self.canonical_bytes).hexdigest() != self.digest:
            raise UnrealStateExtractionError(
                ERR_EXTRACTION_SCHEMA,
                "digest does not match the canonical bytes it is presented with",
            )


def canonical_bytes_for_tree(tree: Any) -> bytes:
    """Return the canonical bytes of a validated (reconstructed) value tree."""
    return canonical_bytes(validate_value_tree(tree))


def digest_value_tree(tree: Any) -> str:
    """Return ``sha256(canonical_bytes)`` for a value tree, after validation."""
    return hashlib.sha256(canonical_bytes_for_tree(tree)).hexdigest()


def canonical_size(tree: Any) -> int:
    """Return the canonical byte length of a tree (for gate measurement, §11.3)."""
    return len(canonical_bytes_for_tree(tree))


def _require_success_flag(response: Mapping[str, Any]) -> bool:
    if "success" not in response:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA, "transport response carries no 'success' flag"
        )
    success = response["success"]
    if type(success) is not bool:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"transport response 'success' must be a boolean, got {type(success).__name__}",
        )
    return success


def _reject_augmented_boundary(observed_state: Any) -> None:
    """Refuse a payload that passed through the session-augmenting adapter path."""
    if isinstance(observed_state, Mapping) and AUGMENTATION_MARKER in observed_state:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            "observed_state carries "
            f"{AUGMENTATION_MARKER!r}: the extraction boundary runs un-augmented and the "
            "remedy is to stop augmenting, never to strip the key",
        )


def _failure_code(response: Mapping[str, Any]) -> str:
    """Map a failed response to the closed vocabulary.

    A producer code that is in the extraction vocabulary is reported as itself. Anything
    else — an absent code, an empty code, or a code from another class such as a
    transport timeout — is reported as :data:`ERR_EXTRACTION_ERROR_CODE_UNKNOWN`, with
    the raw value kept in the detail so the caller can still see what arrived. A timeout
    therefore never becomes an empty or partial payload (§8.2, §9.5).
    """
    raw = response.get("error_code")
    if isinstance(raw, str) and raw in PRODUCER_ERROR_CODES:
        return raw
    raise UnrealStateExtractionError(
        ERR_EXTRACTION_ERROR_CODE_UNKNOWN,
        f"failed extraction with unrecognised error_code {raw!r}",
    )


def validate_extraction_response(response: Any) -> Dict[str, Any]:
    """Validate a transport response and return the reconstructed value tree.

    Fail-closed rules (§8.2): ``success == false``; a missing
    ``unreal_state_extraction`` node; a schema violation; an unknown producer code; an
    empty ``error_code`` on failure. The construction marker of the legacy augmenting
    adapter is refused explicitly.
    """
    if not isinstance(response, Mapping):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"transport response must be an object, got {type(response).__name__}",
        )
    _reject_augmented_boundary(response.get("observed_state"))
    if not _require_success_flag(response):
        code = _failure_code(response)
        detail = response.get("error")
        raise UnrealStateExtractionError(
            code,
            f"extraction failed: {detail!r}" if detail else "extraction failed",
        )
    observed_state = response.get("observed_state")
    if not isinstance(observed_state, Mapping):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA, "successful response carries no observed_state object"
        )
    keys = set(observed_state.keys())
    if keys != {EXTRACTION_NODE_KEY}:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"observed_state must contain exactly {EXTRACTION_NODE_KEY!r}, got {sorted(keys)!r}",
        )
    return validate_value_tree(observed_state[EXTRACTION_NODE_KEY])


def extract(response: Any) -> ExtractionResult:
    """Validate a response and return the value tree, its canonical bytes and its digest."""
    tree = validate_extraction_response(response)
    payload = canonical_bytes(tree)
    return ExtractionResult(
        value_tree=tree,
        canonical_bytes=payload,
        digest=hashlib.sha256(payload).hexdigest(),
    )


def parse_and_extract(text: str) -> ExtractionResult:
    """Decode untrusted payload text under the hardened policy, then extract."""
    return extract(loads_strict(text))
