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
LIVE_GATE_SOURCE = REPO_ROOT / "tests" / "unreal_state_extraction_live_gate.py"

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


def _strip_comments(text: str) -> str:
    """Remove /* */ blocks and // line comments (the contract rules exclude comments)."""
    without_blocks = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return "\n".join(line.split("//", 1)[0] for line in without_blocks.splitlines())


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



# ---------------------------------------------------------------------------
# §9 item 3 capacity: one bound, measured on the response that is actually sent
# ---------------------------------------------------------------------------

def test_the_extraction_response_is_measured_before_it_is_written() -> None:
    """The extraction response path measures the *serialized response* against the limit."""
    server = _read(SERVER_CPP)
    # The extraction operations go through the measured path, not the raw serializer.
    assert "WriteResponse(SerializeExtractionCheckedResponse(Response));" in server
    assert "WriteResponse(SerializeResponse(Response));" not in server
    # The measured path serializes first (the existing response path) and then decides.
    assert "FString FAtlasTransportServer::SerializeExtractionCheckedResponse(FTransportResponse& Response)" in server
    assert "FString Payload = SerializeResponse(Response);" in server
    assert "ExceedsTransportBound(Payload, WireBytes)" in server
    # ... and it is scoped to the extraction operations only.
    assert 'Response.OperationName != TEXT("extract_actor_state")' in server
    assert 'Response.OperationName != TEXT("extract_sequencer_state")' in server


def test_the_bound_is_the_transport_limit_and_the_wire_encoding() -> None:
    """The comparison uses the transport's own limit and the encoding actually written."""
    server = _read(SERVER_CPP)
    assert "OutWireBytes = FTCHARToUTF8(*SerializedResponse).Length();" in server
    assert "return OutWireBytes > MaxMessageSize;" in server
    # WriteResponse writes exactly that conversion, so the measurement is the wire size.
    assert "FTCHARToUTF8 UTF8String(*JsonResponse);" in server


def test_the_refusal_uses_the_extractors_own_payload_code() -> None:
    """Fail-closed uses the closed extraction vocabulary; no second code, no rename."""
    from planning.unreal_state_extraction import PRODUCER_ERROR_CODES

    server = _read(SERVER_CPP)
    extractor = _read(EXTRACTOR_CPP)
    payload_code = "ERR_EXTRACTION_PAYLOAD_TOO_LARGE"
    assert payload_code in PRODUCER_ERROR_CODES
    assert f'TEXT("{payload_code}")' in extractor
    assert f'TEXT("{payload_code}")' in server
    # The refusal clears the observed state rather than emitting a partial tree.
    assert "Response.ObservedState.Reset();" in server
    # No chunking, compression or truncation path was introduced (comments excluded: the
    # comment that forbids those mechanisms is allowed to name them).
    measured_start = server.index("FString FAtlasTransportServer::SerializeExtractionCheckedResponse")
    measured_end = server.index("bool FAtlasTransportServer::ValidateRequest", measured_start)
    measured_code = _strip_comments(server[measured_start:measured_end])
    for banned in ("Compress", "chunk", "Chunk", "Truncate", "truncat", "Zlib", "gzip"):
        assert banned not in measured_code, banned


def test_the_extractor_assumes_no_envelope_allowance() -> None:
    """The early condition is a measurement, not a constant plus headroom."""
    extractor = _read(EXTRACTOR_CPP)
    assert "EnvelopeHeadroomBytes" not in extractor
    assert "4096" not in extractor
    assert "ByteCount >= TransportMessageSizeLimit" in extractor


def test_fixture_status_precondition_requires_exactly_one_valid_ok_version() -> None:
    """The live gate must reject missing, duplicate, or malformed fixture status lines."""
    source = _read(LIVE_GATE_SOURCE)
    assert "len(fixture_statuses) == 1" in source
    assert 're.fullmatch(r"OK version=\\d+", fixture_statuses[0])' in source
