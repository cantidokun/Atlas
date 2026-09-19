"""Entity identity: grammar, canonical representative, request-level rules.

Contract obligations exercised here: Revision 3.1 §3.3.1–§3.3.5, §7.3 (collation) and
the request-side half of D14/D15.

The engine owns the binding (``FName`` equality, §3.3.3); Python owns the request grammar
and the assertion that a reported identity is canonical.
"""

from __future__ import annotations

import pytest

from planning.unreal_state_extraction import (
    UnrealStateExtractionError,
    canonical_representative,
    is_canonical_entity_id,
    is_valid_requested_id,
    require_canonical_entity_id,
    validate_request_entity_ids,
)
from planning.unreal_state_extraction.entity_id import ascii_uppercase
from planning.unreal_state_extraction.errors import (
    ERR_EXTRACTION_REQUEST_INVALID,
    ERR_EXTRACTION_SCHEMA,
)


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value",
    ["a", "A", "0", "_", ".", "-", "cam01", "CAM01", "cam_1", "cam_01", "FIELD_SURFACE",
     "a.b-c_d", "A" * 64],
)
def test_accepted_ids(value: str) -> None:
    assert is_valid_requested_id(value)


@pytest.mark.parametrize(
    "value",
    [
        "",                       # empty
        "A" * 65,                 # too long
        "atlas_entity:CAM01",     # standalone prefix
        "cam 01",                 # whitespace
        "cam/01",                 # path separator
        "cam:01",                 # colon
        "caf\u00e9",              # non-ASCII
        "\u4f60\u597d",           # non-ASCII
        "cam\u0000",              # control character
        "cam01\n",                # trailing newline
        "cam*01",                 # punctuation outside the grammar
        1,                        # not a string
        None,
    ],
)
def test_rejected_ids(value) -> None:
    assert not is_valid_requested_id(value)


# ---------------------------------------------------------------------------
# Canonical representative
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        ("cam01", "CAM01"),
        ("CAM01", "CAM01"),
        ("cAm01", "CAM01"),
        ("cam_1", "CAM_1"),
        ("CAM_1", "CAM_1"),
        ("cam_01", "CAM_01"),
        ("cam", "CAM"),
        ("FIELD_SURFACE", "FIELD_SURFACE"),
        ("a.b-c_d", "A.B-C_D"),
        ("_1", "_1"),
    ],
)
def test_canonical_representative(requested: str, expected: str) -> None:
    assert canonical_representative(requested) == expected


def test_d14_case_variants_share_one_representative() -> None:
    representatives = {
        canonical_representative(spelling) for spelling in ("cam01", "CAM01", "Cam01", "cAm01")
    }
    assert representatives == {"CAM01"}


def test_d14_numbered_variants_share_one_representative_per_class() -> None:
    assert canonical_representative("cam_1") == canonical_representative("CAM_1") == "CAM_1"
    assert (
        canonical_representative("cam_01")
        == canonical_representative("CAM_01")
        == "CAM_01"
    )


def test_d15_numbered_names_are_distinct_classes() -> None:
    """``cam``, ``cam_1`` and ``cam_01`` are three different FName bindings."""
    distinct = {
        canonical_representative("cam"),
        canonical_representative("cam_1"),
        canonical_representative("cam_01"),
    }
    assert distinct == {"CAM", "CAM_1", "CAM_01"}


def test_ascii_uppercasing_only_folds_ascii_letters() -> None:
    # Nothing outside a-z may be transformed, so no locale or Unicode case mapping
    # can enter the contract.
    assert ascii_uppercase("abcxyz_1.-") == "ABCXYZ_1.-"
    assert ascii_uppercase("\u00e4\u00f6\u00fc") == "\u00e4\u00f6\u00fc"
    assert ascii_uppercase("\u0131i") == "\u0131I"


def test_non_canonical_request_is_rejected() -> None:
    for bad in ("", "cam 01", "atlas_entity:CAM01", "A" * 65, 1, None):
        with pytest.raises(UnrealStateExtractionError) as excinfo:
            canonical_representative(bad)  # type: ignore[arg-type]
        assert excinfo.value.code == ERR_EXTRACTION_REQUEST_INVALID


# ---------------------------------------------------------------------------
# Reported identity must be canonical
# ---------------------------------------------------------------------------

def test_reported_identity_must_be_uppercase_canonical() -> None:
    assert is_canonical_entity_id("CAM01")
    for bad in ("cam01", "Cam01", "", "CAM 01", "CAM:", "ATLAS_ENTITY:CAM01"):
        assert not is_canonical_entity_id(bad)
        with pytest.raises(UnrealStateExtractionError) as excinfo:
            require_canonical_entity_id(bad, where="$")
        assert excinfo.value.code == ERR_EXTRACTION_SCHEMA


# ---------------------------------------------------------------------------
# Request-level rules (§3.3.5)
# ---------------------------------------------------------------------------

def test_request_ids_are_returned_in_canonical_form() -> None:
    assert validate_request_entity_ids(["cam01", "field_surface"]) == (
        "CAM01",
        "FIELD_SURFACE",
    )


def test_request_order_is_preserved_by_the_validator() -> None:
    """Order handling is not this layer's decision; canonical ordering is the payload's."""
    assert validate_request_entity_ids(["b_1", "a"]) == ("B_1", "A")


def test_duplicate_ids_are_rejected_not_deduplicated() -> None:
    with pytest.raises(UnrealStateExtractionError) as excinfo:
        validate_request_entity_ids(["cam01", "cam01"])
    assert excinfo.value.code == ERR_EXTRACTION_REQUEST_INVALID


def test_case_variant_duplicates_are_rejected() -> None:
    for pair in (["cam01", "CAM01"], ["cam_1", "Cam_1"], ["CAM", "cam"]):
        with pytest.raises(UnrealStateExtractionError) as excinfo:
            validate_request_entity_ids(pair)
        assert excinfo.value.code == ERR_EXTRACTION_REQUEST_INVALID
        assert "case folding" in excinfo.value.detail


def test_numbered_variants_are_not_duplicates_of_each_other() -> None:
    assert validate_request_entity_ids(["cam", "cam_1", "cam_01"]) == (
        "CAM",
        "CAM_1",
        "CAM_01",
    )


def test_empty_request_is_rejected() -> None:
    for empty in ([], (), set()):
        with pytest.raises(UnrealStateExtractionError) as excinfo:
            validate_request_entity_ids(empty)
        assert excinfo.value.code == ERR_EXTRACTION_REQUEST_INVALID


def test_non_sequence_and_non_string_ids_are_rejected() -> None:
    for bad in ("cam01", b"cam01", None, 1):
        with pytest.raises(UnrealStateExtractionError) as excinfo:
            validate_request_entity_ids(bad)  # type: ignore[arg-type]
        assert excinfo.value.code == ERR_EXTRACTION_REQUEST_INVALID
    with pytest.raises(UnrealStateExtractionError) as excinfo:
        validate_request_entity_ids(["cam01", 42])  # type: ignore[list-item]
    assert excinfo.value.code == ERR_EXTRACTION_REQUEST_INVALID


def test_request_grammar_removes_collation_ambiguity() -> None:
    """ASCII ids: byte order == UTF-16 code-unit order == Python str order."""
    ids = ["b", "A", "a_1", "a.1", "a-1", "0", "_"]
    assert sorted(ids) == sorted(ids, key=lambda value: value.encode("utf-16-be"))
    assert sorted(ids) == sorted(ids, key=lambda value: value.encode("utf-8"))
