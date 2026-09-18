"""Unreal State Extraction Fidelity v1 — Python contract boundary.

Design source: ``docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_DESIGN.md`` (Revision 3.1,
PR #106) — cleared for implementation.

Scope of this package: the *Atlas side* of the extraction contract. It validates the
untrusted C++ value tree against a closed schema, reconstructs the digest input field by
field, canonicalizes it with RFC 8785 (JCS), and computes the SHA-256 identity. It
contains no Unreal access, no transport redesign, and no verification authority: a
digest is an identity/integrity value, never a verdict (§2.3).

What the package deliberately does *not* do:

* it never repairs, coerces or partially accepts a payload (§8.2);
* it never strips a field — in particular it refuses the legacy session-augmenting
  adapter path instead of deleting ``_session_identity`` (§4.2.8);
* it never falls back to ``json.dumps`` for canonicalization (§6.4).
"""

from __future__ import annotations

from planning.unreal_state_extraction.binary64 import (
    BINARY64_VECTORS,
    decode_pattern,
    encode_pattern,
    is_canonical_pattern,
    require_canonical_pattern,
)
from planning.unreal_state_extraction.digest import (
    TRANSPORT_MESSAGE_SIZE_LIMIT,
    ExtractionResult,
    canonical_bytes_for_tree,
    canonical_size,
    digest_value_tree,
    extract,
    parse_and_extract,
    validate_extraction_response,
)
from planning.unreal_state_extraction.entity_id import (
    canonical_representative,
    is_canonical_entity_id,
    is_valid_requested_id,
    require_canonical_entity_id,
    validate_request_entity_ids,
)
from planning.unreal_state_extraction.errors import (
    ALL_ERROR_CODES,
    PRODUCER_ERROR_CODES,
    VALIDATOR_ERROR_CODES,
    UnrealStateExtractionError,
)
from planning.unreal_state_extraction.jcs import canonical_bytes, canonicalize
from planning.unreal_state_extraction.schema import (
    EXTRACTION_NODE_KEY,
    EXTRACTION_SCHEMA_VERSION,
    RESERVED_KEYS,
    validate_value_tree,
)
from planning.unreal_state_extraction.strict_json import loads_strict

__all__ = [
    "ALL_ERROR_CODES",
    "BINARY64_VECTORS",
    "EXTRACTION_NODE_KEY",
    "EXTRACTION_SCHEMA_VERSION",
    "ExtractionResult",
    "PRODUCER_ERROR_CODES",
    "RESERVED_KEYS",
    "TRANSPORT_MESSAGE_SIZE_LIMIT",
    "UnrealStateExtractionError",
    "VALIDATOR_ERROR_CODES",
    "canonical_bytes",
    "canonical_bytes_for_tree",
    "canonical_representative",
    "canonical_size",
    "canonicalize",
    "decode_pattern",
    "digest_value_tree",
    "encode_pattern",
    "extract",
    "is_canonical_entity_id",
    "is_canonical_pattern",
    "is_valid_requested_id",
    "loads_strict",
    "parse_and_extract",
    "require_canonical_entity_id",
    "require_canonical_pattern",
    "validate_extraction_response",
    "validate_request_entity_ids",
    "validate_value_tree",
]
