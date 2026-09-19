"""RFC 8785 (JCS) canonicalization over the restricted extraction domain.

Design source: Revision 3.1 §6.1–§6.4.

This is the *only* canonicalizer for the extraction contract. It implements RFC 8785 for
the domain this payload actually occupies — closed-schema objects with string keys,
strings, integers, booleans, ``null`` and arrays — and **fails closed** on anything else
instead of falling back to ``json.dumps``. ``json.dumps(sort_keys=True)`` is explicitly
not an oracle: it sorts by Unicode *code point* where JCS orders object names by *UTF-16
code units*, and its escaping is not the ECMAScript escaping JCS mandates (§6.3).

Rules implemented (RFC 8785 §3.2):

* object names are sorted by UTF-16 code units, ascending, ordinal (never locale aware);
* strings use ECMAScript ``JSON.stringify`` escaping: short escapes for
  ``\\b \\t \\n \\f \\r \\" \\\\``, ``\\u00xx`` (lowercase hex) for the remaining control
  characters, and **no** escaping of non-ASCII characters;
* array order is preserved as given (canonical *array* order is the producer's
  obligation, validated separately in :mod:`planning.unreal_state_extraction.schema`);
* integers serialize as their decimal form, which is the ECMAScript Number::toString
  result for every value in the safe range;
* output is UTF-8, no BOM, no trailing newline.
"""

from __future__ import annotations

from typing import Any, List, Sequence, Tuple

from planning.unreal_state_extraction.errors import (
    ERR_EXTRACTION_SCHEMA,
    UnrealStateExtractionError,
)

#: Integers outside this range are not exactly representable by the ECMAScript number
#: model JCS numbers are defined against, so the domain refuses them. The schema layer
#: is stricter still (int32 per field).
ES_SAFE_INTEGER = 2**53 - 1

_SHORT_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\u0008": "\\b",
    "\u0009": "\\t",
    "\u000a": "\\n",
    "\u000c": "\\f",
    "\u000d": "\\r",
}


def _escape(text: str) -> str:
    """ECMAScript ``JSON.stringify`` string escaping (RFC 8785 §3.2.2.2)."""
    out: List[str] = ['"']
    for char in text:
        escape = _SHORT_ESCAPES.get(char)
        if escape is not None:
            out.append(escape)
        elif char < "\u0020":
            out.append(f"\\u{ord(char):04x}")
        elif "\ud800" <= char <= "\udfff":
            raise UnrealStateExtractionError(
                ERR_EXTRACTION_SCHEMA,
                "string contains a lone surrogate, which has no canonical form",
            )
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def _utf16_sort_key(name: str) -> bytes:
    """Sort key ordering object names by UTF-16 code units.

    Comparing ``utf-16-be`` byte sequences is equivalent to comparing unsigned 16-bit
    code units in order, and it is the property the contract fixes for object keys and
    for object-path arrays (§7.3). A lone surrogate cannot be encoded and would have no
    canonical form, so it is refused here as well.
    """
    try:
        return name.encode("utf-16-be")
    except UnicodeEncodeError as exc:  # pragma: no cover - guarded by _escape too
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA, "object name contains a lone surrogate"
        ) from exc


def _serialize(value: Any) -> str:
    # ``bool`` is checked before ``int`` because ``isinstance(True, int)`` is True.
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        if abs(value) > ES_SAFE_INTEGER:
            raise UnrealStateExtractionError(
                ERR_EXTRACTION_SCHEMA,
                f"integer {value} exceeds the exact-number domain of JCS",
            )
        return str(value)
    if isinstance(value, float):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            "floating-point values are outside the restricted canonicalization domain",
        )
    if isinstance(value, str):
        return _escape(value)
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise UnrealStateExtractionError(
                    ERR_EXTRACTION_SCHEMA, "object names must be strings"
                )
        parts: List[str] = []
        for key in sorted(value.keys(), key=_utf16_sort_key):
            parts.append(f"{_escape(key)}:{_serialize(value[key])}")
        return "{" + ",".join(parts) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_serialize(item) for item in value) + "]"
    if isinstance(value, (bytes, bytearray)):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA, "binary values are outside the canonicalization domain"
        )
    raise UnrealStateExtractionError(
        ERR_EXTRACTION_SCHEMA,
        f"unsupported canonicalization value type: {type(value).__name__}",
    )


def canonicalize(value: Any) -> str:
    """Return the RFC 8785 canonical text for ``value``."""
    return _serialize(value)


def canonical_bytes(value: Any) -> bytes:
    """Return the canonical UTF-8 bytes of ``value`` (no BOM, no trailing newline)."""
    return canonicalize(value).encode("utf-8")


# ---------------------------------------------------------------------------
# Vectors
# ---------------------------------------------------------------------------

#: In-domain vectors. Values lie inside the restricted domain and MUST canonicalize
#: byte-exactly.
#:
#: The four ``published_*`` vectors are the RFC 8785 test data committed by the
#: reference implementation
#: (``git:cyberphone/json-canonicalization`` — ``testdata/input/<name>.json`` versus
#: ``testdata/output/<name>.json``, fetched and transcribed verbatim). They are the
#: vectors that carry the rules this contract depends on: object-name ordering by UTF-16
#: code units (``weird``, ``french``, ``structures``), ECMAScript string escaping
#: (``weird``), no Unicode normalization (``unicode``) and no locale awareness
#: (``french``).
#:
#: The ``derived_*`` vectors are this contract's own, labelled as such.
JCS_IN_DOMAIN_VECTORS: Sequence[Tuple[str, Any, str]] = (
    ("empty_object", {}, "{}"),
    ("empty_array", [], "[]"),
    ("literals", [None, True, False, "", {}, []], '[null,true,false,"",{},[]]'),
    (
        "published_arrays",
        [56, {"d": True, "10": None, "1": []}],
        '[56,{"1":[],"10":null,"d":true}]',
    ),
    (
        "published_unicode",
        {"Unnormalized Unicode": "A\u030a"},
        '{"Unnormalized Unicode":"A\u030a"}',
    ),
    (
        "published_french",
        {
            "peach": "This sorting order",
            "p\u00e9ch\u00e9": "is wrong according to French",
            "p\u00eache": "but canonicalization MUST",
            "sin": "ignore locale",
        },
        '{"peach":"This sorting order","p\u00e9ch\u00e9":"is wrong according to French",'
        '"p\u00eache":"but canonicalization MUST","sin":"ignore locale"}',
    ),
    (
        # ``testdata/input/weird.json``: the escaping and UTF-16 ordering vector. Note
        # that U+0080 is written *literally* (EMCAScript escaping covers U+0000-U+001F
        # only) and that the emoji (surrogates D83D DE02) sorts **before** the Hebrew
        # letter U+FB33, which is exactly where code-unit and code-point order differ.
        "published_weird",
        {
            "\u20ac": "Euro Sign",
            "\r": "Carriage Return",
            "\u000a": "Newline",
            "1": "One",
            "\u0080": "Control\u007f",
            "\U0001f602": "Smiley",
            "\u00f6": "Latin Small Letter O With Diaeresis",
            "\ufb33": "Hebrew Letter Dalet With Dagesh",
            "</script>": "Browser Challenge",
        },
        '{"\\n":"Newline","\\r":"Carriage Return","1":"One","</script>":"Browser Challenge",'
        '"\u0080":"Control\u007f","\u00f6":"Latin Small Letter O With Diaeresis",'
        '"\u20ac":"Euro Sign","\U0001f602":"Smiley",'
        '"\ufb33":"Hebrew Letter Dalet With Dagesh"}',
    ),
    (
        # The published ``structures`` vector with the float ``56.0`` replaced by the
        # integer ``56``, because floats are outside this contract's domain (see the
        # rejection vector of the same name below).
        "derived_structures_integers",
        {
            "1": {"f": {"f": "hi", "F": 5}, "\n": 56},
            "10": {},
            "": "empty",
            "a": {},
            "111": [{"e": "yes", "E": "no"}],
            "A": {},
        },
        '{"":"empty","1":{"\\n":56,"f":{"F":5,"f":"hi"}},"10":{},"111":[{"E":"no","e":"yes"}],'
        '"A":{},"a":{}}',
    ),
    ("short_escapes", {"\u0008\u0009\u000a\u000c\u000d": "x"}, '{"\\b\\t\\n\\f\\r":"x"}'),
    ("quote_and_backslash", {'"': "\\"}, '{"\\"":"\\\\"}'),
    ("lowercase_control_hex", {"\u0000": "\u001f"}, '{"\\u0000":"\\u001f"}'),
    ("no_escape_for_del", {"\u007f": "\u007f"}, '{"\u007f":"\u007f"}'),
    ("solidus_is_not_escaped", {"</script>": "</script>"}, '{"</script>":"</script>"}'),
    ("no_escape_for_non_ascii", {"\u00f6": "\u20ac"}, '{"\u00f6":"\u20ac"}'),
    ("integers", {"b": 1, "a": 0, "c": -2, "d": 2147483647}, '{"a":0,"b":1,"c":-2,"d":2147483647}'),
    ("array_order_preserved", [3, 1, 2], "[3,1,2]"),
    ("nested", {"a": [{"z": 0, "y": None}]}, '{"a":[{"y":null,"z":0}]}'),
)

#: Out-of-domain vectors. Each MUST be rejected rather than canonicalized: a
#: canonicalizer that "passes" a float vector has silently acquired a number-formatting
#: behaviour this contract forbids (§6.4).
JCS_OUT_OF_DOMAIN_VECTORS: Sequence[Tuple[str, Any]] = (
    # The published ``structures`` vector, rejected *because* it carries ``56.0``.
    (
        "published_structures_with_float",
        {
            "1": {"f": {"f": "hi", "F": 5}, "\n": 56.0},
            "10": {},
            "": "empty",
            "a": {},
            "111": [{"e": "yes", "E": "no"}],
            "A": {},
        },
    ),
    ("float_value", {"a": 1.5}),
    ("float_zero", {"a": 0.0}),
    ("exponent_form_parsed", {"a": 100.0}),
    ("non_finite", {"a": float("inf")}),
    ("non_string_key", {1: "a"}),
    ("bytes_value", {"a": b"x"}),
    ("unsupported_type", {"a": object()}),
)
