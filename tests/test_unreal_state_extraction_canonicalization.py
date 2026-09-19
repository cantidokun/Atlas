"""Canonicalization: RFC 8785 (JCS) over the restricted domain, and determinism.

Contract obligations exercised here: Revision 3.1 §6.1–§6.4 and D9 (JCS vectors, split
into in-domain assertions and out-of-domain rejections), §6.3 (why
``json.dumps(sort_keys=True)`` is not an oracle) and D1/D2 (process hash seed and
construction-sequence independence).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from planning.unreal_state_extraction import (
    UnrealStateExtractionError,
    canonical_bytes,
    canonicalize,
    digest_value_tree,
    loads_strict,
)
from planning.unreal_state_extraction.errors import ERR_EXTRACTION_SCHEMA
from planning.unreal_state_extraction.jcs import (
    ES_SAFE_INTEGER,
    JCS_IN_DOMAIN_VECTORS,
    JCS_OUT_OF_DOMAIN_VECTORS,
)
from tests.extraction_payload_fixtures import (
    actor,
    actor_state_tree,
    material_component,
    slot,
)


# ---------------------------------------------------------------------------
# D9 — in-domain vectors must pass byte-exactly
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("name", "value", "expected"), JCS_IN_DOMAIN_VECTORS, ids=[v[0] for v in JCS_IN_DOMAIN_VECTORS]
)
def test_d9_in_domain_vectors_canonicalize_byte_exactly(name: str, value, expected: str) -> None:
    assert canonicalize(value) == expected
    assert canonical_bytes(value) == expected.encode("utf-8")


def test_d9_ordering_vector_discriminates_utf16_from_code_point_order() -> None:
    """The vector only has value if the two orderings actually differ."""
    value = next(item[1] for item in JCS_IN_DOMAIN_VECTORS if item[0] == "published_weird")
    expected = next(item[2] for item in JCS_IN_DOMAIN_VECTORS if item[0] == "published_weird")
    code_point_order = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert code_point_order != expected
    # In code-point order the Hebrew letter (U+FB33) precedes the emoji (U+1F602); in
    # UTF-16 code-unit order the emoji's high surrogate (U+D83D) precedes it.
    assert code_point_order.index("\ufb33") < code_point_order.index("\U0001f602")
    assert expected.index("\U0001f602") < expected.index("\ufb33")


def test_d9_escaping_covers_only_the_control_range() -> None:
    """U+007F and U+0080 are *not* escaped, which is where naive escaping diverges."""
    weird = next(item[1] for item in JCS_IN_DOMAIN_VECTORS if item[0] == "published_weird")
    expected = next(item[2] for item in JCS_IN_DOMAIN_VECTORS if item[0] == "published_weird")
    assert canonicalize(weird) == expected
    assert "\u0080" in expected and "\\u0080" not in expected
    assert "Control\u007f" in expected and "\\u007f" not in expected


def test_string_escaping_follows_ecmascript_rules() -> None:
    assert canonicalize({"a": "\u0000\u001f"}) == '{"a":"\\u0000\\u001f"}'
    assert canonicalize({"a": "\u007f"}) == '{"a":"\u007f"}'          # DEL is not escaped
    assert canonicalize({"a": "\u00f6"}) == '{"a":"\u00f6"}'          # non-ASCII is not escaped
    assert canonicalize({"a": "\b\t\n\f\r"}) == '{"a":"\\b\\t\\n\\f\\r"}'
    assert canonicalize({"a": '"\\'}) == '{"a":"\\"\\\\"}'
    assert canonicalize({"a": "/"}) == '{"a":"/"}'                    # solidus is not escaped


def test_output_has_no_whitespace_no_bom_no_trailing_newline() -> None:
    payload = canonical_bytes({"b": 1, "a": [1, 2]})
    assert payload == b'{"a":[1,2],"b":1}'
    assert not payload.startswith(b"\xef\xbb\xbf")
    assert not payload.endswith(b"\n")


def test_output_is_utf8() -> None:
    assert canonical_bytes({"\u00f6": "\u20ac"}) == '{"\u00f6":"\u20ac"}'.encode("utf-8")


# ---------------------------------------------------------------------------
# D9 — out-of-domain vectors must be rejected, never passed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("name", "value"), JCS_OUT_OF_DOMAIN_VECTORS, ids=[v[0] for v in JCS_OUT_OF_DOMAIN_VECTORS]
)
def test_d9_out_of_domain_vectors_are_rejected(name: str, value) -> None:
    with pytest.raises(UnrealStateExtractionError) as excinfo:
        canonicalize(value)
    assert excinfo.value.code == ERR_EXTRACTION_SCHEMA


def test_float_lexeme_in_text_is_rejected_before_canonicalization() -> None:
    with pytest.raises(UnrealStateExtractionError):
        loads_strict('{"a":1.5}')


def test_integers_beyond_the_exact_number_domain_are_rejected() -> None:
    assert canonicalize({"a": ES_SAFE_INTEGER}) == f'{{"a":{ES_SAFE_INTEGER}}}'
    with pytest.raises(UnrealStateExtractionError) as excinfo:
        canonicalize({"a": ES_SAFE_INTEGER + 1})
    assert excinfo.value.code == ERR_EXTRACTION_SCHEMA


def test_non_string_object_names_are_rejected() -> None:
    with pytest.raises(UnrealStateExtractionError):
        canonicalize({1: "a"})


def test_lone_surrogate_in_a_string_is_rejected_by_the_canonicalizer() -> None:
    with pytest.raises(UnrealStateExtractionError) as excinfo:
        canonicalize({"a": "\ud800"})
    assert excinfo.value.code == ERR_EXTRACTION_SCHEMA


# ---------------------------------------------------------------------------
# §6.3 — json.dumps is not an oracle
# ---------------------------------------------------------------------------

def test_json_dumps_is_not_equivalent_to_jcs_for_reachable_payloads() -> None:
    payload = {"\u20ac": 1, "\ufb33": 2, "\U0001f600": 3}
    jcs = canonicalize(payload)
    python_sort = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert jcs != python_sort
    # ensure_ascii=True diverges even more, and the repository's call sites disagree with
    # each other on it, which is why the contract owns one canonicalizer.
    assert json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) != jcs


# ---------------------------------------------------------------------------
# D2 — construction sequence independence
# ---------------------------------------------------------------------------

def test_d2_dictionary_insertion_order_does_not_change_the_bytes() -> None:
    forward = {"a": 1, "b": 2, "c": {"d": 3, "e": [4, 5]}}
    backward = {"c": {"e": [4, 5], "d": 3}, "b": 2, "a": 1}
    assert canonical_bytes(forward) == canonical_bytes(backward)
    assert digest_value_tree(
        actor_state_tree(actors=[actor(entity_id="CAM01")])
    ) == digest_value_tree(actor_state_tree(actors=[actor(entity_id="CAM01")]))


def test_d2_nested_construction_order_does_not_change_payload_bytes() -> None:
    tree = actor_state_tree(
        actors=[
            actor(
                materials=[
                    material_component(
                        component_object_path="/Game/Test.Level:Actor.Mesh0",
                        slots=[slot(0)],
                    )
                ]
            )
        ]
    )
    # Rebuild the same logical structure with reversed insertion order at every level.
    reversed_tree = _reverse_order(tree)
    assert canonical_bytes(tree) == canonical_bytes(reversed_tree)
    assert digest_value_tree(tree) == digest_value_tree(reversed_tree)


def _reverse_order(value):
    if isinstance(value, dict):
        return {key: _reverse_order(value[key]) for key in reversed(list(value.keys()))}
    if isinstance(value, list):
        return [_reverse_order(item) for item in value]
    return value


# ---------------------------------------------------------------------------
# D1 — process independence under a deliberately different PYTHONHASHSEED
# ---------------------------------------------------------------------------

_HASH_SEED_SCRIPT = """
import json, sys
from planning.unreal_state_extraction import canonical_bytes_for_tree, digest_value_tree

tree = json.loads(sys.stdin.read())
sys.stdout.write(canonical_bytes_for_tree(tree).hex() + ":" + digest_value_tree(tree))
"""


def test_d1_two_processes_with_different_hash_seeds_agree() -> None:
    tree = actor_state_tree(
        actors=[
            actor(entity_id="CAM01"),
            actor(entity_id="FIELD_SURFACE", actor_name="Second"),
        ]
    )
    text = json.dumps(tree, sort_keys=True)
    results = []
    for seed in ("0", "1", "424242"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        completed = subprocess.run(
            [sys.executable, "-c", _HASH_SEED_SCRIPT],
            input=text,
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        results.append(completed.stdout.strip())
    assert len(set(results)) == 1, results
    assert results[0].endswith(digest_value_tree(tree))
