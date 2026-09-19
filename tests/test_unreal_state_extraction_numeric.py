"""Numeric policy: binary64 bit-pattern encoding, non-finite refusal, exactness.

Contract obligations exercised here: Revision 3.1 §5.1–§5.6 and the mandatory vectors
D11 (above FLT_MAX), D12 (denormal floor), D13 (lexical shape), D20 (bit-encoding
vectors) and D22 (non-finite vectors must be constructed from the *pattern*).
"""

from __future__ import annotations

import math
import struct

import pytest

from planning.unreal_state_extraction import (
    BINARY64_VECTORS,
    UnrealStateExtractionError,
    decode_pattern,
    encode_pattern,
    is_canonical_pattern,
    require_canonical_pattern,
)
from planning.unreal_state_extraction.errors import (
    ERR_EXTRACTION_NON_FINITE,
    ERR_EXTRACTION_SCHEMA,
)
from planning.unreal_state_extraction.schema import validate_value_tree
from tests.extraction_payload_fixtures import actor, actor_state_tree, transform, vector3

FLT_MAX_AS_DOUBLE = 3.4028234663852886e38


def pattern_to_float(pattern: int) -> float:
    """Build a double from its *pattern*, never from hex bytes (D22)."""
    return struct.unpack("<d", struct.pack("<Q", pattern))[0]


# ---------------------------------------------------------------------------
# D20 — the fixed vector table
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("1.0", 1.0),
        ("-1.0", -1.0),
        ("+0.0", 0.0),
        ("-0.0", -0.0),
        ("smallest_positive_subnormal", 5e-324),
        ("smallest_positive_normal", 2.0**-1022),
        ("largest_finite", 1.7976931348623157e308),
        ("float_max_widened", FLT_MAX_AS_DOUBLE),
        ("1e300", 1e300),
    ],
)
def test_bit_encoding_vectors(name: str, value: float) -> None:
    assert encode_pattern(value) == BINARY64_VECTORS[name]


def test_encoding_round_trips_through_the_pattern() -> None:
    for value in (0.0, -0.0, 1.0, -1.0, 5e-324, 1e300, FLT_MAX_AS_DOUBLE, 12345.6789):
        assert decode_pattern(encode_pattern(value)) == value


def test_encoding_is_byte_order_independent() -> None:
    """The contract value is the integer, so no packing order can change it."""
    assert encode_pattern(1.0) == "3ff0000000000000"
    wrong_mismatched_pair = struct.unpack(">Q", struct.pack("<d", 1.0))[0]
    assert f"{wrong_mismatched_pair:016x}" == "000000000000f03f"
    for fmt in ("<", ">", "="):
        bits = struct.unpack(f"{fmt}Q", struct.pack(f"{fmt}d", 1.0))[0]
        assert f"{bits:016x}" == "3ff0000000000000"


def test_encoding_never_hex_dumps_memory() -> None:
    """A little-endian memory dump of 1.0 is the wrong value; the pattern is the contract."""
    assert struct.pack("<d", 1.0).hex() == "000000000000f03f"
    assert encode_pattern(1.0) == "3ff0000000000000"


# ---------------------------------------------------------------------------
# D11 / D12 — exactness above FLT_MAX and at the denormal floor
# ---------------------------------------------------------------------------

def test_d11_value_above_float_max_is_exact() -> None:
    assert encode_pattern(FLT_MAX_AS_DOUBLE) == "47efffffe0000000"
    assert encode_pattern(1e300) == "7e37e43c8800759c"
    assert math.isfinite(FLT_MAX_AS_DOUBLE)


def test_d12_denormal_floor_is_nonzero() -> None:
    encoded = encode_pattern(5e-324)
    assert encoded == "0000000000000001"
    assert int(encoded, 16) != 0


# ---------------------------------------------------------------------------
# D13 — lexical shape
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad",
    [
        "1.0",                      # decimal lexeme
        "3ff00000",                 # 8-digit binary32 pattern
        "3FF0000000000000",         # uppercase hex
        "3ff000000000000",          # 15 digits
        "3ff00000000000000",        # 17 digits
        "3ff000000000000g",         # non-hex character
        "",                         # empty
        "3ff0000000000000\n",       # trailing newline ($-anchor hazard)
        " 3ff0000000000000",        # leading whitespace
        1.0,                        # JSON number in a scalar position
        1,                          # integer in a scalar position
        None,                       # null where a scalar is required
    ],
)
def test_d13_scalar_lexical_shape_is_enforced(bad: object) -> None:
    assert not is_canonical_pattern(bad)
    with pytest.raises(UnrealStateExtractionError) as excinfo:
        require_canonical_pattern(bad, where="$")
    assert excinfo.value.code == ERR_EXTRACTION_SCHEMA


def test_a_decimal_scalar_in_a_transform_is_rejected_by_the_schema() -> None:
    tree = actor_state_tree(
        actors=[actor(transform=transform(location_cm=vector3("1.0", "0", "0")))]
    )
    with pytest.raises(UnrealStateExtractionError) as excinfo:
        validate_value_tree(tree)
    assert excinfo.value.code == ERR_EXTRACTION_SCHEMA


def test_a_json_number_in_a_transform_is_rejected_by_the_schema() -> None:
    tree = actor_state_tree(actors=[actor(transform=transform(location_cm=vector3(0.0, 0.0, 0.0)))])
    with pytest.raises(UnrealStateExtractionError) as excinfo:
        validate_value_tree(tree)
    assert excinfo.value.code == ERR_EXTRACTION_SCHEMA


# ---------------------------------------------------------------------------
# §5.5 / D22 — non-finite dispositions, patterns built from patterns
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "pattern",
    [
        0x7FF0000000000000,  # +Inf
        0xFFF0000000000000,  # -Inf
        0x7FF8000000000000,  # quiet NaN
        0x7FF8000000000001,  # quiet NaN with payload
        0x7FF0000000000001,  # signaling NaN
        0xFFF8000000000000,  # negative NaN
        0x7FFFFFFFFFFFFFFF,  # NaN, all payload bits set
    ],
)
def test_d22_non_finite_patterns_are_refused_before_encoding(pattern: int) -> None:
    value = pattern_to_float(pattern)
    assert not math.isfinite(value)
    with pytest.raises(UnrealStateExtractionError) as excinfo:
        encode_pattern(value)
    assert excinfo.value.code == ERR_EXTRACTION_NON_FINITE


def test_d22_hex_byte_construction_is_the_trap_this_contract_documents() -> None:
    """``bytes.fromhex`` writes byte order, not the pattern: that is a finite subnormal."""
    not_a_nan = struct.unpack("<d", bytes.fromhex("7ff8000000000001"))[0]
    assert math.isfinite(not_a_nan)
    assert encode_pattern(not_a_nan) == "010000000000f87f"
    real_nan = pattern_to_float(0x7FF8000000000001)
    assert not math.isfinite(real_nan)


def test_quiet_and_signaling_nan_are_indistinguishable_to_the_contract() -> None:
    both = (pattern_to_float(0x7FF8000000000000), pattern_to_float(0x7FF0000000000001))
    for value in both:
        with pytest.raises(UnrealStateExtractionError) as excinfo:
            encode_pattern(value)
        assert excinfo.value.code == ERR_EXTRACTION_NON_FINITE


# ---------------------------------------------------------------------------
# §5.5.1 — signed zero is a source fact
# ---------------------------------------------------------------------------

def test_signed_zero_is_not_canonicalized_together() -> None:
    assert encode_pattern(0.0) == "0000000000000000"
    assert encode_pattern(-0.0) == "8000000000000000"
    assert encode_pattern(0.0) != encode_pattern(-0.0)


def test_signed_zero_changes_the_digest() -> None:
    from planning.unreal_state_extraction import digest_value_tree

    positive = actor_state_tree(actors=[actor(transform=transform(location_cm=vector3("0000000000000000", "0000000000000000", "0000000000000000")))])
    negative = actor_state_tree(actors=[actor(transform=transform(location_cm=vector3("8000000000000000", "0000000000000000", "0000000000000000")))])
    assert digest_value_tree(positive) != digest_value_tree(negative)


def test_quaternion_sign_is_a_source_fact() -> None:
    from planning.unreal_state_extraction import digest_value_tree

    def with_rotation(w: str, x: str) -> dict:
        rot = transform()["rotation"] | {"w": w, "x": x}
        return actor_state_tree(actors=[actor(transform=transform(rotation=rot))])

    q = with_rotation("3ff0000000000000", "0000000000000000")
    minus_q = with_rotation("bff0000000000000", "8000000000000000")
    assert digest_value_tree(q) != digest_value_tree(minus_q)


# ---------------------------------------------------------------------------
# Type discipline
# ---------------------------------------------------------------------------

def test_encode_pattern_rejects_non_floats() -> None:
    for bad in (1, True, "1.0", None):
        with pytest.raises(UnrealStateExtractionError) as excinfo:
            encode_pattern(bad)  # type: ignore[arg-type]
        assert excinfo.value.code == ERR_EXTRACTION_SCHEMA
