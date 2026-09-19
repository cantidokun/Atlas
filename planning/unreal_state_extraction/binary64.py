"""Canonical binary64 encoding for transform scalars.

Design source: Revision 3.1 §5.1–§5.6.

The canonical value is the **bit pattern** of the double the engine returned, rendered
as exactly 16 lowercase hexadecimal digits::

    P(v) = (sign << 63) | (biased_exponent << 52) | significand
    canonical(v) = lowercase hex of P(v), zero padded to 16 digits

The mapping is stated over the *pattern*, not over memory, so no byte order, host
property or language-specific step participates in the contract value. Non-finite
values are refused **before** encoding, at the source representation, so no ordering
exists in which NaN or ±Inf can reach the bit cast.

The endianness trap this module documents: ``struct.unpack(">Q", struct.pack("<d", v))``
is a mismatched pair that reinterprets the byte order; it yields ``000000000000f03f`` for
``1.0`` where the contract requires ``3ff0000000000000``. The paired little-endian codes
below are an implementation detail for recovering the same integer the double denotes.
"""

from __future__ import annotations

import math
import re
import struct
from typing import Any, Dict

from planning.unreal_state_extraction.errors import (
    ERR_EXTRACTION_NON_FINITE,
    ERR_EXTRACTION_SCHEMA,
    UnrealStateExtractionError,
)

#: A canonical transform scalar is exactly 16 lowercase hex digits (§5.2 rule 2). The
#: lexical form is part of the schema: a decimal lexeme, a short hex string, an 8-digit
#: binary32 pattern or a JSON number in a scalar position is a hard failure.
#:
#: Anchored with ``\A``/``\Z``: Python's ``$`` would also match before a trailing
#: newline and let ``"3ff0000000000000\n"`` pass a lexical-shape check.
CANONICAL_SCALAR_PATTERN = re.compile(r"\A[0-9a-f]{16}\Z")

#: Hardening limit for the *safe* integer domain: every integer in the value tree is an
#: exact JSON integer within its declared int32 source type (§5.3).
INT32_MIN = -(2**31)
INT32_MAX = 2**31 - 1

#: Fixed vector table (Revision 3.1 §7.4 D20, §5.5). Both the Python validator and the
#: C++ producer assert against these, so a byte-order or precision regression is caught
#: at the boundary rather than by inspection.
BINARY64_VECTORS: Dict[str, str] = {
    "1.0": "3ff0000000000000",
    "-1.0": "bff0000000000000",
    "+0.0": "0000000000000000",
    "-0.0": "8000000000000000",
    "smallest_positive_subnormal": "0000000000000001",
    "smallest_positive_normal": "0010000000000000",
    "largest_finite": "7fefffffffffffff",
    "float_max_widened": "47efffffe0000000",
    "1e300": "7e37e43c8800759c",
}


def _pattern_of(value: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", value))[0]


def encode_pattern(value: float) -> str:
    """Return the canonical 16-digit hex pattern for ``value``.

    Raises :data:`ERR_EXTRACTION_NON_FINITE` for NaN or ±Inf: the check runs on the
    returned double and precedes the encoding, so no non-finite value can ever reach
    ``struct.pack``.
    """
    if not isinstance(value, float):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"transform scalar must be a float, got {type(value).__name__}",
        )
    if not math.isfinite(value):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_NON_FINITE,
            f"non-finite transform scalar ({value!r}) is refused before encoding",
        )
    return f"{_pattern_of(value):016x}"


def decode_pattern(pattern: str) -> float:
    """Return the double denoted by a canonical 16-digit hex pattern."""
    if not is_canonical_pattern(pattern):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"transform scalar {pattern!r} is not 16 lowercase hex digits",
        )
    return struct.unpack("<d", struct.pack("<Q", int(pattern, 16)))[0]


def is_canonical_pattern(value: Any) -> bool:
    """True when ``value`` is a legal canonical scalar (and not a bool or a number)."""
    return isinstance(value, str) and CANONICAL_SCALAR_PATTERN.match(value) is not None


def require_canonical_pattern(value: Any, *, where: str) -> str:
    """Assert a scalar field is a canonical pattern, else fail closed."""
    if not is_canonical_pattern(value):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"{where} must be 16 lowercase hex digits (binary64 pattern), got {value!r}",
        )
    return value


def is_int32(value: Any) -> bool:
    """True for an exact ``int`` (never ``bool``) inside the int32 source range.

    ``isinstance(True, int)`` is ``True`` and ``type(True) is int`` is ``False`` in
    Python, so integer fields are validated with ``type(x) is int`` (§6.4).
    """
    return type(value) is int and INT32_MIN <= value <= INT32_MAX
