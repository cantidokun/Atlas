"""The extraction boundary: envelope handling, session-metadata exclusion, digest.

Contract obligations exercised here: Revision 3.1 §2 (untrusted input), §4.1/§4.2
(boundary, no session contamination, no stripping), §6.5 (digest boundary), §8.2
(fail-closed rules), §9 (bounds) and the mandatory obligations D8 and D10.
"""

from __future__ import annotations

import json

import pytest

from planning.unreal_state_extraction import (
    TRANSPORT_MESSAGE_SIZE_LIMIT,
    UnrealStateExtractionError,
    canonical_bytes_for_tree,
    canonical_size,
    digest_value_tree,
    extract,
    parse_and_extract,
    validate_extraction_response,
)
from planning.unreal_state_extraction.errors import (
    ERR_EXTRACTION_ENTITY_NOT_FOUND,
    ERR_EXTRACTION_ERROR_CODE_UNKNOWN,
    ERR_EXTRACTION_SCHEMA,
)
from tests.extraction_payload_fixtures import (
    actor,
    actor_state_tree,
    response,
    sequencer_state_tree,
    world,
)

SESSION_IDENTITY = {
    "editor_session_id": "e0f0c9a2-0000-4000-8000-000000000001",
    "process_id": 4242,
    "process_creation_time_utc": "2026-09-18T00:00:00Z",
    "server_start_time_utc": "2026-09-18T00:00:01Z",
    "engine_version": "5.6",
    "project_identity": "Atlas",
}


def _expect(callable_, code: str) -> str:
    with pytest.raises(UnrealStateExtractionError) as excinfo:
        callable_()
    assert excinfo.value.code == code, excinfo.value
    return str(excinfo.value)


# ---------------------------------------------------------------------------
# D8 — envelope session metadata never reaches the digest
# ---------------------------------------------------------------------------

def test_d8_envelope_session_metadata_does_not_change_the_digest() -> None:
    bare = extract(response())
    with_session = extract(response(session_identity=SESSION_IDENTITY))
    other_session = extract(
        response(session_identity=dict(SESSION_IDENTITY, process_id=9999, editor_session_id="x"))
    )
    assert bare.digest == with_session.digest == other_session.digest
    assert bare.canonical_bytes == other_session.canonical_bytes


def test_d8_request_identity_does_not_change_the_digest() -> None:
    first = extract(response(request_id="req-1"))
    second = extract(response(request_id="req-2"))
    third = extract(response(request_id="req-3", entity_ids=["FIELD_SURFACE", "CAM01"]))
    assert first.digest == second.digest == third.digest


def test_d8_no_request_or_session_value_appears_in_the_canonical_bytes() -> None:
    result = extract(
        response(
            request_id="req-SECRET",
            authorization_id="auth-SECRET",
            session_identity=SESSION_IDENTITY,
        )
    )
    text = result.canonical_bytes.decode("utf-8")
    for forbidden in (
        "req-SECRET",
        "auth-SECRET",
        "e0f0c9a2-0000-4000-8000-000000000001",
        "4242",
        "2026-09-18T00:00:00Z",
        "server_start_time_utc",
        "process_id",
        "session_identity",
        "editor_session_id",
        "project_identity",
    ):
        assert forbidden not in text, forbidden


def test_d8_augmented_observed_state_is_rejected_not_stripped() -> None:
    """§4.2.8: the remedy is to stop augmenting, never to delete the key."""
    observed = actor_state_tree()
    augmented = {"unreal_state_extraction": observed, "_session_identity": SESSION_IDENTITY}
    detail = _expect(
        lambda: validate_extraction_response(response(**{"observed_state": augmented})),
        ERR_EXTRACTION_SCHEMA,
    )
    assert "un-augmented" in detail
    # And inside the tree, where a session key could hide at any depth.
    nested = actor_state_tree()
    nested["actors"][0]["_session_identity"] = SESSION_IDENTITY
    _expect(
        lambda: validate_extraction_response(
            response(**{"observed_state": {"unreal_state_extraction": nested}})
        ),
        ERR_EXTRACTION_SCHEMA,
    )


def test_observed_state_must_contain_exactly_the_extraction_node() -> None:
    extra = {
        "unreal_state_extraction": actor_state_tree(),
        "engine_session_identity": SESSION_IDENTITY,
    }
    _expect(
        lambda: validate_extraction_response(response(**{"observed_state": extra})),
        ERR_EXTRACTION_SCHEMA,
    )
    _expect(
        lambda: validate_extraction_response(response(**{"observed_state": {}})),
        ERR_EXTRACTION_SCHEMA,
    )


# ---------------------------------------------------------------------------
# D10 — digested fields are digested, not silently dropped
# ---------------------------------------------------------------------------

def test_d10_engine_identity_changes_the_digest() -> None:
    base = digest_value_tree(actor_state_tree())
    other_version = digest_value_tree(
        actor_state_tree(world=world(engine_version="5.7.0-1+++UE5+Release-5.7"))
    )
    other_build = digest_value_tree(
        actor_state_tree(world=world(engine_build_version="++UE5+Release-5.7-CL-1"))
    )
    assert len({base, other_version, other_build}) == 3


def test_world_identity_and_scope_changes_alter_the_digest() -> None:
    base = digest_value_tree(actor_state_tree())
    renamed_world = digest_value_tree(actor_state_tree(world=world(world_name="Other")))
    assert base != renamed_world


def test_actor_state_and_sequencer_state_trees_differ() -> None:
    assert digest_value_tree(actor_state_tree()) != digest_value_tree(sequencer_state_tree())


def test_same_logical_tree_yields_the_same_digest_across_calls() -> None:
    first = extract(response())
    second = extract(response())
    assert first.digest == second.digest
    assert first.canonical_bytes == second.canonical_bytes


def test_digest_is_sha256_of_the_canonical_bytes() -> None:
    import hashlib

    result = extract(response())
    assert result.digest == hashlib.sha256(result.canonical_bytes).hexdigest()
    assert len(result.digest) == 64
    assert result.digest == result.digest.lower()


def test_result_rejects_a_digest_with_a_trailing_newline() -> None:
    """``$``-anchored lexical checks would accept a newline-suffixed digest."""
    from planning.unreal_state_extraction import ExtractionResult

    result = extract(response())
    _expect(
        lambda: ExtractionResult(
            value_tree=result.value_tree,
            canonical_bytes=result.canonical_bytes,
            digest=result.digest + "\n",
        ),
        ERR_EXTRACTION_SCHEMA,
    )


def test_result_rejects_tampered_bytes() -> None:
    from planning.unreal_state_extraction import ExtractionResult

    result = extract(response())
    _expect(
        lambda: ExtractionResult(
            value_tree=result.value_tree,
            canonical_bytes=result.canonical_bytes + b" ",
            digest=result.digest,
        ),
        ERR_EXTRACTION_SCHEMA,
    )
    _expect(
        lambda: ExtractionResult(
            value_tree=result.value_tree,
            canonical_bytes=result.canonical_bytes,
            digest="ABC",
        ),
        ERR_EXTRACTION_SCHEMA,
    )


# ---------------------------------------------------------------------------
# §8.2 — fail-closed failure handling
# ---------------------------------------------------------------------------

def test_failed_extraction_reports_its_producer_code() -> None:
    detail = _expect(
        lambda: extract(
            response(success=False, error_code=ERR_EXTRACTION_ENTITY_NOT_FOUND, error="no actor")
        ),
        ERR_EXTRACTION_ENTITY_NOT_FOUND,
    )
    assert "no actor" in detail


@pytest.mark.parametrize(
    "error_code",
    ["", "ERR_OPERATION_FAILED", "ERR_OPERATION_TIMED_OUT", "NOT_A_CODE", None],
)
def test_unknown_or_empty_error_code_is_a_hard_failure(error_code) -> None:
    _expect(
        lambda: extract(response(success=False, error_code=error_code, error="boom")),
        ERR_EXTRACTION_ERROR_CODE_UNKNOWN,
    )


def test_transport_timeout_is_a_failure_never_an_empty_payload() -> None:
    detail = _expect(
        lambda: extract(
            response(success=False, error_code="ERR_OPERATION_TIMED_OUT", error="timed out")
        ),
        ERR_EXTRACTION_ERROR_CODE_UNKNOWN,
    )
    assert "ERR_OPERATION_TIMED_OUT" in detail


def test_failed_extraction_never_returns_a_tree() -> None:
    with pytest.raises(UnrealStateExtractionError):
        validate_extraction_response(
            response(success=False, error_code=ERR_EXTRACTION_ENTITY_NOT_FOUND)
        )


def test_missing_or_non_boolean_success_flag_is_a_schema_failure() -> None:
    payload = response()
    del payload["success"]
    _expect(lambda: extract(payload), ERR_EXTRACTION_SCHEMA)
    _expect(lambda: extract(response(success="true")), ERR_EXTRACTION_SCHEMA)
    _expect(lambda: extract(response(success=1)), ERR_EXTRACTION_SCHEMA)


def test_missing_observed_state_is_a_schema_failure() -> None:
    payload = response()
    del payload["observed_state"]
    _expect(lambda: extract(payload), ERR_EXTRACTION_SCHEMA)


def test_response_must_be_an_object() -> None:
    for bad in ([], "x", 1, None):
        _expect(lambda: extract(bad), ERR_EXTRACTION_SCHEMA)


# ---------------------------------------------------------------------------
# Text-level boundary and bounds
# ---------------------------------------------------------------------------

def test_parse_and_extract_round_trips_through_hardened_json() -> None:
    payload = response(session_identity=SESSION_IDENTITY)
    text = json.dumps(payload)
    first = parse_and_extract(text)
    second = extract(payload)
    assert first.digest == second.digest


def test_parse_and_extract_rejects_a_float_anywhere_in_the_envelope() -> None:
    text = json.dumps(response()).replace('"schema_version": 1', '"schema_version": 1.0')
    _expect(lambda: parse_and_extract(text), ERR_EXTRACTION_SCHEMA)


def test_canonical_size_is_measured_and_the_transport_bound_is_recorded() -> None:
    assert TRANSPORT_MESSAGE_SIZE_LIMIT == 1024 * 1024
    size = canonical_size(actor_state_tree())
    assert size == len(canonical_bytes_for_tree(actor_state_tree()))
    assert 0 < size < TRANSPORT_MESSAGE_SIZE_LIMIT


def test_digest_is_not_a_field_of_the_value_tree() -> None:
    validated = validate_extraction_response(response())
    text = canonical_bytes_for_tree(validated).decode("utf-8")
    assert "digest" not in text
    assert "sha256" not in text
