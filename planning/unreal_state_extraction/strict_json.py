"""Hardened JSON parsing for untrusted producer output.

Design source: Revision 3.1 §6.4 (the measured hazard table).

A canonicalizer that validates its input is not sufficient if the *parser* already
changed the input, so the C++-produced JSON text is decoded under a policy that refuses
every construct the contract does not admit:

======================  ====================================================
Hazard                  Required policy (measured default in parentheses)
======================  ====================================================
duplicate object keys   raise (``json.loads`` silently keeps the **last** value)
``NaN``/``Infinity``    raise (accepted by default through ``parse_constant``)
float lexemes           raise (parsed into binary floats by default)
lone surrogates         raise (they survive parsing and then break UTF-8 encoding)
surrogate pairs         accepted (they decode to one astral character)
``bool`` vs ``int``     distinguished in the schema layer with ``type(x) is int``
integer range           bounded per field in the schema layer (int32)
======================  ====================================================

The parser is deliberately dumb about the *tree*; structural validation belongs to
:mod:`planning.unreal_state_extraction.schema`.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, List, Tuple

from planning.unreal_state_extraction.errors import (
    ERR_EXTRACTION_SCHEMA,
    UnrealStateExtractionError,
)

#: Code points that may never appear in a decoded string.
_SURROGATE_MIN = 0xD800
_SURROGATE_MAX = 0xDFFF


def _reject_constant(token: str) -> Any:
    raise UnrealStateExtractionError(
        ERR_EXTRACTION_SCHEMA,
        f"non-JSON constant {token!r} is outside the restricted domain (no NaN/Infinity)",
    )


def _reject_float(lexeme: str) -> Any:
    raise UnrealStateExtractionError(
        ERR_EXTRACTION_SCHEMA,
        f"floating-point lexeme {lexeme!r} is forbidden; the value tree is integer-only",
    )


def _pairs_without_duplicates(pairs: Iterable[Tuple[str, Any]]) -> dict:
    material: dict = {}
    for key, value in pairs:
        if key in material:
            raise UnrealStateExtractionError(
                ERR_EXTRACTION_SCHEMA,
                f"duplicate object key {key!r}: a payload whose key set depends on "
                "position is not a value tree",
            )
        material[key] = value
    return material


def loads_strict(text: str) -> Any:
    """Decode ``text`` under the hardened policy of Revision 3.1 §6.4."""
    if not isinstance(text, str):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA, "payload text must be a string"
        )
    try:
        return json.loads(
            text,
            object_pairs_hook=_pairs_without_duplicates,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
        )
    except UnrealStateExtractionError:
        raise
    except ValueError as exc:  # malformed JSON text
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA, f"payload is not valid JSON: {exc}"
        ) from exc


def find_lone_surrogates(value: Any, *, where: str = "$") -> List[str]:
    """Return the paths of every string containing a surrogate code point.

    A lone surrogate is rejected during validation, before canonicalization, because
    ``json.dumps(..., ensure_ascii=False)`` would render it and the subsequent UTF-8
    encoding would raise ``UnicodeEncodeError``. Surrogate *pairs* have already been
    combined by the parser and are therefore not reported here.
    """
    found: List[str] = []
    if isinstance(value, str):
        if any(_SURROGATE_MIN <= ord(ch) <= _SURROGATE_MAX for ch in value):
            found.append(where)
    elif isinstance(value, dict):
        for key, item in value.items():
            found.extend(find_lone_surrogates(key, where=f"{where}.<key>"))
            found.extend(find_lone_surrogates(item, where=f"{where}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(find_lone_surrogates(item, where=f"{where}[{index}]"))
    return found
