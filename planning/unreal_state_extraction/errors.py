"""Closed error vocabulary for the Unreal state extraction boundary.

Design source: ``docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_DESIGN.md`` (Revision 3.1,
PR #106) §8.1. The vocabulary is closed: a failure is reported with exactly one of the
codes below and never as a generic operation failure.

Two families are distinguished deliberately:

``PRODUCER_ERROR_CODES``
    Codes the C++ extraction producer may set in a transport response. Python treats an
    unknown code on a failed response as a hard failure
    (:data:`ERR_EXTRACTION_ERROR_CODE_UNKNOWN`).

``VALIDATOR_ERROR_CODES``
    Codes raised by this package when the *untrusted* producer output violates the
    contract. They are never returned by the producer.
"""

from __future__ import annotations

from typing import FrozenSet

# ---------------------------------------------------------------------------
# Producer codes (C++ → Atlas)
# ---------------------------------------------------------------------------

ERR_EXTRACTION_REQUEST_INVALID = "ERR_EXTRACTION_REQUEST_INVALID"
ERR_EXTRACTION_WORLD_UNAVAILABLE = "ERR_EXTRACTION_WORLD_UNAVAILABLE"
ERR_EXTRACTION_WORLD_NOT_EDITOR = "ERR_EXTRACTION_WORLD_NOT_EDITOR"
ERR_EXTRACTION_WORLD_PARTITION_UNSUPPORTED = "ERR_EXTRACTION_WORLD_PARTITION_UNSUPPORTED"
ERR_EXTRACTION_LEVEL_SCOPE_INCOMPLETE = "ERR_EXTRACTION_LEVEL_SCOPE_INCOMPLETE"
ERR_EXTRACTION_LEVEL_SCOPE_INVALID = "ERR_EXTRACTION_LEVEL_SCOPE_INVALID"
ERR_EXTRACTION_SCOPE_CHANGED = "ERR_EXTRACTION_SCOPE_CHANGED"
ERR_EXTRACTION_ENTITY_NOT_FOUND = "ERR_EXTRACTION_ENTITY_NOT_FOUND"
ERR_EXTRACTION_ENTITY_AMBIGUOUS = "ERR_EXTRACTION_ENTITY_AMBIGUOUS"
ERR_EXTRACTION_ENTITY_TAG_CONFLICT = "ERR_EXTRACTION_ENTITY_TAG_CONFLICT"
ERR_EXTRACTION_UNSUPPORTED_COMPONENT_TYPE = "ERR_EXTRACTION_UNSUPPORTED_COMPONENT_TYPE"
ERR_EXTRACTION_ENGINE_IDENTITY_UNAVAILABLE = "ERR_EXTRACTION_ENGINE_IDENTITY_UNAVAILABLE"
ERR_EXTRACTION_PARENT_TAG_CONFLICT = "ERR_EXTRACTION_PARENT_TAG_CONFLICT"
ERR_EXTRACTION_NON_FINITE = "ERR_EXTRACTION_NON_FINITE"
ERR_EXTRACTION_MESH_COMPILING = "ERR_EXTRACTION_MESH_COMPILING"
ERR_EXTRACTION_MESH_ASSET_UNSTABLE = "ERR_EXTRACTION_MESH_ASSET_UNSTABLE"
ERR_EXTRACTION_MATERIAL_UNRESOLVED = "ERR_EXTRACTION_MATERIAL_UNRESOLVED"
ERR_EXTRACTION_UNSUPPORTED_MATERIAL_SOURCE = "ERR_EXTRACTION_UNSUPPORTED_MATERIAL_SOURCE"
ERR_EXTRACTION_SEQUENCE_ACTOR_TYPE = "ERR_EXTRACTION_SEQUENCE_ACTOR_TYPE"
ERR_EXTRACTION_SEQUENCE_ASSET_UNRESOLVED = "ERR_EXTRACTION_SEQUENCE_ASSET_UNRESOLVED"
ERR_EXTRACTION_UNSUPPORTED_SEQUENCE_SOURCE = "ERR_EXTRACTION_UNSUPPORTED_SEQUENCE_SOURCE"
ERR_EXTRACTION_SEQUENCE_RANGE_OPEN = "ERR_EXTRACTION_SEQUENCE_RANGE_OPEN"
ERR_EXTRACTION_SEQUENCE_RANGE_INVALID = "ERR_EXTRACTION_SEQUENCE_RANGE_INVALID"
ERR_EXTRACTION_SEQUENCE_RATE_INVALID = "ERR_EXTRACTION_SEQUENCE_RATE_INVALID"
ERR_EXTRACTION_PAYLOAD_TOO_LARGE = "ERR_EXTRACTION_PAYLOAD_TOO_LARGE"

# ---------------------------------------------------------------------------
# Validator codes (this package)
# ---------------------------------------------------------------------------

ERR_EXTRACTION_SCHEMA = "ERR_EXTRACTION_SCHEMA"
ERR_EXTRACTION_NON_CANONICAL_ORDER = "ERR_EXTRACTION_NON_CANONICAL_ORDER"
ERR_EXTRACTION_ERROR_CODE_UNKNOWN = "ERR_EXTRACTION_ERROR_CODE_UNKNOWN"

PRODUCER_ERROR_CODES: FrozenSet[str] = frozenset(
    code
    for name, code in globals().items()
    if name.startswith("ERR_EXTRACTION_") and isinstance(code, str) and code not in {
        ERR_EXTRACTION_SCHEMA,
        ERR_EXTRACTION_NON_CANONICAL_ORDER,
        ERR_EXTRACTION_ERROR_CODE_UNKNOWN,
    }
)

VALIDATOR_ERROR_CODES: FrozenSet[str] = frozenset(
    {
        ERR_EXTRACTION_SCHEMA,
        ERR_EXTRACTION_NON_CANONICAL_ORDER,
        ERR_EXTRACTION_ERROR_CODE_UNKNOWN,
    }
)

ALL_ERROR_CODES: FrozenSet[str] = PRODUCER_ERROR_CODES | VALIDATOR_ERROR_CODES


class UnrealStateExtractionError(ValueError):
    """One contract failure, carrying a code from the closed vocabulary.

    The code is part of the contract: callers must branch on it rather than on the
    message, and the vocabulary is closed so an unrecognised code is itself a
    failure (:data:`ERR_EXTRACTION_ERROR_CODE_UNKNOWN`).
    """

    def __init__(self, code: str, detail: str) -> None:
        if code not in ALL_ERROR_CODES:
            raise AssertionError(
                f"{code!r} is not in the closed extraction error vocabulary"
            )
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
