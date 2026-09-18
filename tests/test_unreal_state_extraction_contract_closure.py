"""Cross-language closure: the C++ producer and the Python boundary must agree.

The two halves of this contract are written in different languages, so the places where
they must agree exactly are asserted mechanically rather than by review:

* the closed error vocabulary (design §8.1) — every code the producer can emit must be a
  code Python recognises, and every producer code Python knows must be emittable;
* the closed schema key sets (§4) — every JSON key Python requires must be written by the
  C++ producer, and the producer must not invent keys the schema rejects (the prefix and
  the contract's own field names are checked by construction below).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from planning.unreal_state_extraction import PRODUCER_ERROR_CODES
from planning.unreal_state_extraction.schema import (
    ACTOR_KEYS,
    LEVEL_KEYS,
    MATERIAL_KEYS,
    OMITTED_KEYS,
    PARENT_KEYS,
    PLAYBACK_RANGE_KEYS,
    RATE_KEYS,
    ROTATION_KEYS,
    SEQUENCE_KEYS,
    SLOT_KEYS,
    TRANSFORM_KEYS,
    VISIBILITY_KEYS,
    WORLD_KEYS,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR_CPP = (
    REPO_ROOT
    / "unreal"
    / "AtlasUnrealHarness"
    / "Source"
    / "AtlasUnrealTransport"
    / "Private"
    / "AtlasStateExtraction.cpp"
)
EXTRACTOR_H = EXTRACTOR_CPP.with_suffix(".h")
SERVER_CPP = EXTRACTOR_CPP.parent / "AtlasTransportServer.cpp"

ALL_SCHEMA_KEYS = sorted(
    set(WORLD_KEYS)
    | set(LEVEL_KEYS)
    | set(ACTOR_KEYS)
    | set(PARENT_KEYS)
    | set(VISIBILITY_KEYS)
    | set(TRANSFORM_KEYS)
    | set(ROTATION_KEYS)
    | set(MATERIAL_KEYS)
    | set(SLOT_KEYS)
    | set(OMITTED_KEYS)
    | set(SEQUENCE_KEYS)
    | set(PLAYBACK_RANGE_KEYS)
    | set(RATE_KEYS)
    | {
        "extraction_schema_version",
        "extraction_kind",
        "world",
        "actors",
        "sequences",
        "level_scope",
        "levels",
        "coordinate_frame",
    }
)


def _read(path: Path) -> str:
    assert path.is_file(), f"missing source file: {path}"
    return path.read_text(encoding="utf-8", errors="replace")


@pytest.mark.parametrize("key", ALL_SCHEMA_KEYS)
def test_cpp_producer_writes_every_schema_key(key: str) -> None:
    source = _read(EXTRACTOR_CPP)
    assert f'TEXT("{key}")' in source, f"the producer never writes the schema key {key!r}"


def test_cpp_error_vocabulary_matches_python_exactly() -> None:
    declared = set(re.findall(r'TEXT\("(ERR_EXTRACTION_[A-Z_]+)"\)', _read(EXTRACTOR_CPP)))
    assert declared, "the extractor defines no error codes"
    assert declared == set(PRODUCER_ERROR_CODES), {
        "missing_in_cpp": sorted(set(PRODUCER_ERROR_CODES) - declared),
        "unknown_to_python": sorted(declared - set(PRODUCER_ERROR_CODES)),
    }


def test_every_declared_code_is_actually_used() -> None:
    source = _read(EXTRACTOR_CPP)
    declared_names = set(
        re.findall(
            r'const TCHAR\* const (\w+) = TEXT\("ERR_EXTRACTION_[A-Z_]+"\);', source
        )
    )
    used_names = set(re.findall(r"ErrorCodes::(\w+)", source))
    assert declared_names, "no error codes are defined in the extractor"
    assert declared_names == used_names, {
        "never_used": sorted(declared_names - used_names),
        "used_but_undeclared": sorted(used_names - declared_names),
    }
    header_names = set(re.findall(r"extern const TCHAR\* const (\w+);", _read(EXTRACTOR_H)))
    assert header_names == declared_names, {
        "missing_in_header": sorted(declared_names - header_names),
        "extra_in_header": sorted(header_names - declared_names),
    }


def test_python_never_accepts_a_code_the_producer_cannot_emit() -> None:
    from planning.unreal_state_extraction.errors import VALIDATOR_ERROR_CODES

    assert not (set(PRODUCER_ERROR_CODES) & set(VALIDATOR_ERROR_CODES))
    for code in PRODUCER_ERROR_CODES:
        assert code.startswith("ERR_EXTRACTION_")


def test_the_server_envelope_field_names_match_the_contract() -> None:
    server = _read(SERVER_CPP)
    for field in ("success", "error", "error_code", "observed_state", "session_identity", "entity_ids"):
        assert f'TEXT("{field}")' in server, field
