"""Canonical entity-ID grammar and canonical representative.

Design source: Revision 3.1 §3.3.2 (grammar), §3.3.4 (canonical representative),
§3.3.5 (request-level rules).

The Python side never binds tags — binding happens in the engine through ``FName``
equality (§3.3.3). What Python owns is (a) rejecting a request whose IDs are not
canonical and (b) asserting that the ``entity_id`` a producer reports is the canonical
representative, so that a payload can never carry the caller's spelling.
"""

from __future__ import annotations

import re
from typing import Iterable, Tuple

from planning.unreal_state_extraction.errors import (
    ERR_EXTRACTION_REQUEST_INVALID,
    ERR_EXTRACTION_SCHEMA,
    UnrealStateExtractionError,
)

#: The v1 canonical entity-ID grammar (Revision 3.1 §3.3.2).
#:
#: Anchored with ``\A``/``\Z`` rather than ``^``/``$``: in Python ``$`` also matches
#: *before* a trailing newline, which would let ``"cam01\n"`` pass the grammar and reach
#: ``FName("atlas_entity:cam01\n")`` — a whitespace hazard the grammar exists to remove.
ENTITY_ID_PATTERN = re.compile(r"\A[A-Za-z0-9_.-]{1,64}\Z")

#: A reported ``entity_id`` must already be the canonical representative, i.e. the
#: ASCII-uppercase form of its comparison class (§3.3.4). Lowercase letters are
#: therefore illegal in a reported identity.
CANONICAL_ENTITY_ID_PATTERN = re.compile(r"\A[A-Z0-9_.-]{1,64}\Z")

_LOWER_TO_UPPER = {ord(c): ord(c.upper()) for c in "abcdefghijklmnopqrstuvwxyz"}


def ascii_uppercase(value: str) -> str:
    """Return the ASCII-uppercase form of ``value``.

    Only ``a``-``z`` are folded (the grammar admits no other cased character), so no
    locale- or Unicode-dependent case mapping can enter the contract (§17: locale
    sensitive or Unicode case folding must not be used).
    """
    return value.translate(_LOWER_TO_UPPER)


def is_valid_requested_id(value: object) -> bool:
    """True when ``value`` matches the canonical entity-ID grammar."""
    return isinstance(value, str) and ENTITY_ID_PATTERN.match(value) is not None


def is_canonical_entity_id(value: object) -> bool:
    """True when ``value`` is a legal *reported* entity identity."""
    return isinstance(value, str) and CANONICAL_ENTITY_ID_PATTERN.match(value) is not None


def canonical_representative(requested_id: str) -> str:
    """Return the canonical representative of the binding ``requested_id`` selects.

    The representative is the ASCII-uppercase spelling of the request's comparison
    class. It is legitimate to compute it from the request *only because* the engine
    only reports a binding whose ``FName`` equals ``FName("atlas_entity:" + this
    string)`` (Revision 3.1 §3.3.4). Any two requests that bind the same tag uppercase
    to the same string: ``FName`` equality forces the two spellings to share a
    case-folded base and number, and uppercasing affects letters only, leaving the
    number and its ``_`` separator untouched.
    """
    if not is_valid_requested_id(requested_id):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_REQUEST_INVALID,
            f"entity id {requested_id!r} is not canonical (^[A-Za-z0-9_.-]{{1,64}}$)",
        )
    return ascii_uppercase(requested_id)


def require_canonical_entity_id(value: object, *, where: str) -> str:
    """Assert a producer-reported identity is canonical, else fail closed."""
    if not is_canonical_entity_id(value):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"{where} must be the canonical (ASCII-uppercase) entity identity, got {value!r}",
        )
    return value


def validate_request_entity_ids(entity_ids: Iterable[str]) -> Tuple[str, ...]:
    """Validate a request's entity IDs and return them in canonical form.

    Rules (Revision 3.1 §3.3.2, §3.3.5.2): every ID must match the grammar, and no two
    IDs may be equal *case-insensitively* — case variants select the same ``FName``
    comparison class, so accepting both would be a duplicate binding, and the contract
    rejects duplicates rather than deduplicating them.
    """
    if isinstance(entity_ids, (str, bytes)) or not isinstance(entity_ids, Iterable):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_REQUEST_INVALID, "entity_ids must be a sequence of strings"
        )
    requested = list(entity_ids)
    if not requested:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_REQUEST_INVALID, "entity_ids must contain at least one id"
        )
    seen: set[str] = set()
    canonical: list[str] = []
    for raw in requested:
        if not is_valid_requested_id(raw):
            raise UnrealStateExtractionError(
                ERR_EXTRACTION_REQUEST_INVALID,
                f"entity id {raw!r} is not canonical (^[A-Za-z0-9_.-]{{1,64}}$)",
            )
        representative = ascii_uppercase(raw)
        if representative in seen:
            raise UnrealStateExtractionError(
                ERR_EXTRACTION_REQUEST_INVALID,
                f"duplicate entity id after case folding: {raw!r}",
            )
        seen.add(representative)
        canonical.append(representative)
    return tuple(canonical)
