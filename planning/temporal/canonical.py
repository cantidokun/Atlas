"""Normative TemporalCanonicalBytes encoder for Atlas Temporal v1.

This module owns digest canonicalization only. General transport serialization remains outside
the temporal v1 contract.
"""

from __future__ import annotations

import hashlib
import math
import struct
from typing import Any


class CanonicalValueError(ValueError):
    """A value is outside the TemporalCanonicalBytes domain."""


_I64_MIN = -(1 << 63)
_I64_MAX = (1 << 63) - 1
_U64_MAX = (1 << 64) - 1


def _validate_unicode_scalar_string(value: str, label: str = "string") -> bytes:
    if type(value) is not str:
        raise CanonicalValueError(f"{label} must be an exact built-in string")
    if any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        raise CanonicalValueError(f"{label} contains a Unicode surrogate")
    try:
        return value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CanonicalValueError(f"{label} is not a valid Unicode scalar sequence") from exc


def _pack_u64(value: int, label: str) -> bytes:
    if type(value) is not int or isinstance(value, bool) or not 0 <= value <= _U64_MAX:
        raise CanonicalValueError(f"{label} is outside unsigned-64 range")
    return struct.pack(">Q", value)


def _pack_i64(value: int, label: str) -> bytes:
    if type(value) is not int or isinstance(value, bool) or not _I64_MIN <= value <= _I64_MAX:
        raise CanonicalValueError(f"{label} is outside signed-64 range")
    return struct.pack(">q", value)


def _pack_f64(value: float, label: str) -> bytes:
    if type(value) is not float:
        raise CanonicalValueError(f"{label} must be an exact built-in float")
    if not math.isfinite(value):
        raise CanonicalValueError(f"{label} must be finite")
    return struct.pack(">Q", struct.unpack(">Q", struct.pack(">d", value))[0])


def temporal_canonical_bytes(value: Any, *, _path: str = "$") -> bytes:
    """Encode one value according to the normative TemporalCanonicalBytes rules."""
    if value is None:
        return b"\x00"

    if type(value) is str:
        raw = _validate_unicode_scalar_string(value, _path)
        return b"\x01" + _pack_u64(len(raw), f"{_path}.length") + raw

    if type(value) is bool:
        return b"\x02" + (b"\x01" if value else b"\x00")

    if type(value) is int:
        return b"\x03" + _pack_i64(value, _path)

    if type(value) is float:
        return b"\x04" + _pack_f64(value, _path)

    if type(value) is list:
        encoded = [temporal_canonical_bytes(item, _path=f"{_path}[{i}]") for i, item in enumerate(value)]
        return b"\x05" + _pack_u64(len(value), f"{_path}.count") + b"".join(encoded)

    if type(value) is dict:
        items = []
        seen = set()
        for key, item in value.items():
            key_bytes = _validate_unicode_scalar_string(key, f"{_path}.key")
            if key in seen:
                raise CanonicalValueError(f"{_path} contains duplicate key {key!r}")
            seen.add(key)
            items.append((key, key_bytes, item))
        items.sort(key=lambda row: row[0])
        encoded = []
        for key, key_bytes, item in items:
            encoded.append(
                b"\x01"
                + _pack_u64(len(key_bytes), f"{_path}.{key}.length")
                + key_bytes
                + temporal_canonical_bytes(item, _path=f"{_path}[{key!r}]")
            )
        return b"\x06" + _pack_u64(len(items), f"{_path}.count") + b"".join(encoded)

    raise CanonicalValueError(f"{_path} has unsupported canonical value type {type(value).__name__}")


def sha256_digest(value: Any) -> str:
    """Return lowercase SHA-256 over TemporalCanonicalBytes(value)."""
    return hashlib.sha256(temporal_canonical_bytes(value)).hexdigest()
