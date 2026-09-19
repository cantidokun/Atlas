"""Parser hardening: the measured hazard table of Revision 3.1 §6.4 and D19.

A canonicalizer that validates its input is not sufficient if the parser already changed
the input, so each hazard below is asserted at the parser boundary *and*, where the
schema is the responsible layer, at the schema boundary.
"""

from __future__ import annotations

import json

import pytest

from planning.unreal_state_extraction import (
    UnrealStateExtractionError,
    digest_value_tree,
    loads_strict,
    validate_value_tree,
)
from planning.unreal_state_extraction.errors import ERR_EXTRACTION_SCHEMA
from planning.unreal_state_extraction.strict_json import find_lone_surrogates
from tests.extraction_payload_fixtures import (
    actor,
    actor_state_tree,
    material_component,
    response,
)


def _payload_text(tree) -> str:
    return json.dumps(response(tree), sort_keys=True)


# ---------------------------------------------------------------------------
# §6.4 hazard table
# ---------------------------------------------------------------------------

def test_duplicate_object_keys_are_rejected_not_last_wins() -> None:
    # Measured default: json.loads silently keeps the last value.
    assert json.loads('{"entity_id":"a","entity_id":"b"}') == {"entity_id": "b"}
    with pytest.raises(UnrealStateExtractionError) as excinfo:
        loads_strict('{"entity_id":"a","entity_id":"b"}')
    assert excinfo.value.code == ERR_EXTRACTION_SCHEMA


def test_nan_and_infinity_tokens_are_rejected() -> None:
    for text in ('{"a":NaN}', '{"a":Infinity}', '{"a":-Infinity}'):
        with pytest.raises(UnrealStateExtractionError) as excinfo:
            loads_strict(text)
        assert excinfo.value.code == ERR_EXTRACTION_SCHEMA


def test_float_lexemes_are_rejected() -> None:
    for text in ('{"a":1.5}', '{"a":1e3}', '{"a":0.0}', '{"a":-0.5}', '{"a":1E2}'):
        with pytest.raises(UnrealStateExtractionError) as excinfo:
            loads_strict(text)
        assert excinfo.value.code == ERR_EXTRACTION_SCHEMA


def test_integers_are_accepted() -> None:
    assert loads_strict('{"a":0,"b":-1,"c":2147483647}') == {
        "a": 0,
        "b": -1,
        "c": 2147483647,
    }


def test_malformed_json_is_a_schema_failure() -> None:
    for text in ("{", "", "not json", "{'a':1}"):
        with pytest.raises(UnrealStateExtractionError) as excinfo:
            loads_strict(text)
        assert excinfo.value.code == ERR_EXTRACTION_SCHEMA


def test_payload_text_must_be_a_string() -> None:
    with pytest.raises(UnrealStateExtractionError) as excinfo:
        loads_strict(b"{}")  # type: ignore[arg-type]
    assert excinfo.value.code == ERR_EXTRACTION_SCHEMA


# ---------------------------------------------------------------------------
# Surrogates
# ---------------------------------------------------------------------------

def test_lone_surrogate_is_rejected_before_canonicalization() -> None:
    payload = {"a": "\ud800"}
    assert find_lone_surrogates(payload) == ["$.a"]
    with pytest.raises(UnrealStateExtractionError) as excinfo:
        validate_value_tree(
            actor_state_tree(actors=[actor(actor_class="\ud800")])
        )
    assert excinfo.value.code == ERR_EXTRACTION_SCHEMA


def test_surrogate_pair_in_json_text_decodes_to_one_astral_character() -> None:
    decoded = loads_strict('{"a":"\\ud83d\\ude00"}')
    assert decoded == {"a": "\U0001f600"}
    assert find_lone_surrogates(decoded) == []


def test_astral_character_in_an_object_path_is_accepted_and_digests_reproducibly() -> None:
    tree = actor_state_tree(
        actors=[actor(actor_object_path="/Game/Test.Level:Actor_\U0001f600")]
    )
    first = digest_value_tree(tree)
    second = digest_value_tree(
        actor_state_tree(actors=[actor(actor_object_path="/Game/Test.Level:Actor_\U0001f600")])
    )
    assert first == second


def test_lone_surrogate_in_a_key_is_rejected() -> None:
    tree = actor_state_tree()
    tree["world"]["world_name"] = "ok"
    with pytest.raises(UnrealStateExtractionError):
        validate_value_tree({"a\ud800": 1})


# ---------------------------------------------------------------------------
# bool vs int, integer range
# ---------------------------------------------------------------------------

def test_bool_is_not_an_integer_where_an_integer_is_required() -> None:
    assert isinstance(True, int) and type(True) is not int
    with pytest.raises(UnrealStateExtractionError) as excinfo:
        validate_value_tree(
            actor_state_tree(actors=[actor(materials=[material_component(slot_count=True, slots=[])])])
        )
    assert excinfo.value.code == ERR_EXTRACTION_SCHEMA


def test_boolean_markers_require_real_booleans() -> None:
    tree = actor_state_tree()
    tree["world"]["is_partitioned_world"] = 0
    with pytest.raises(UnrealStateExtractionError) as excinfo:
        validate_value_tree(tree)
    assert excinfo.value.code == ERR_EXTRACTION_SCHEMA


@pytest.mark.parametrize("value", [2**31, -(2**31) - 1, 2**63, 10**24])
def test_out_of_int32_integers_are_rejected(value: int) -> None:
    with pytest.raises(UnrealStateExtractionError) as excinfo:
        validate_value_tree(
            actor_state_tree(
                actors=[actor(materials=[material_component(slot_count=value, slots=[])])]
            )
        )
    assert excinfo.value.code == ERR_EXTRACTION_SCHEMA


def test_unbounded_python_integers_do_not_slip_through_the_parser() -> None:
    # Measured: Python parses an integer of any size. The schema is what bounds it.
    parsed = loads_strict('{"a":100000000000000000000000}')
    assert parsed == {"a": 10**23}
    with pytest.raises(UnrealStateExtractionError):
        validate_value_tree(
            actor_state_tree(
                actors=[actor(materials=[material_component(slot_count=10**23, slots=[])])]
            )
        )


def test_int32_bounds_are_accepted_at_the_edges() -> None:
    tree = actor_state_tree(
        actors=[
            actor(
                omitted_material_components={"count": 2147483647, "classes": ["ADecalActor"]},
            )
        ]
    )
    validated = validate_value_tree(tree)
    assert validated["actors"][0]["omitted_material_components"]["count"] == 2147483647


# ---------------------------------------------------------------------------
# D19 — the composite rejection obligation
# ---------------------------------------------------------------------------

def test_d19_each_hazard_is_rejected_through_the_boundary() -> None:
    good = _payload_text(actor_state_tree())
    assert json.loads(good)["success"] is True

    hazards = {
        "duplicate_key": good.replace(
            '"success": true', '"success": true, "success": false', 1
        ),
        "nan_token": good.replace('"success": true', '"success": NaN', 1),
        "float_lexeme": good.replace('"success": true', '"success": 1.0', 1),
        "trailing_garbage": good + "{}",
    }
    for name, text in hazards.items():
        with pytest.raises(UnrealStateExtractionError) as excinfo:
            from planning.unreal_state_extraction import parse_and_extract

            parse_and_extract(text)
        assert excinfo.value.code == ERR_EXTRACTION_SCHEMA, name


def test_d19_astral_character_payload_is_accepted_and_canonicalizes_reproducibly() -> None:
    from planning.unreal_state_extraction import parse_and_extract

    tree = actor_state_tree(actors=[actor(actor_name="Actor_\U0001f600")])
    text = json.dumps(response(tree), ensure_ascii=True)
    first = parse_and_extract(text)
    second = parse_and_extract(text)
    assert first.digest == second.digest
    assert b"\xf0\x9f\x98\x80" in first.canonical_bytes  # UTF-8, not ASCII escaped
