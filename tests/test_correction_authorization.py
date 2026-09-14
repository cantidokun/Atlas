"""Deterministic tests for the Wave-2 authorization contract layer.

Covers ONLY the authorization contract implemented in
``planning/blender/correction_authorization.py`` (design §1, §6/§6.1, §8): strict canonical
parsing, the artifact contract, the binding gate, the optional redundant tuple assertion, the
``WC-P17`` recorded-edge/counterpart contract, and authority isolation.

There is NO bpy, NO Blender, NO live run and NO mutation in this suite — the winding mutation
itself is deliberately not implemented yet, so nothing here can execute one.

Negative cases assert the STRUCTURED failure contract: every declared error carries its
``AuthorizationFailureCode`` as an attribute, so assertions compare values exactly. They do not
match on the error text, and they cannot be satisfied by an unrelated error that happens to mention
the same code (see ``test_structured_code_assertion_cannot_be_satisfied_by_message_text``).
"""
import ast
import hashlib
import inspect
import json

import pytest

from planning.blender.correction_authorization import (
    ACCEPTED_AUTHORIZATION_POLICY_VERSIONS,
    AUTHORIZATION_VERSION,
    WINDING_CORRECTION_TYPE,
    AuthorizationArtifact,
    AuthorizationContractError,
    AuthorizationError,
    AuthorizationFailureCode,
    AuthorizationInputError,
    AuthorizationOutcome,
    PresentedWork,
    parse_authorization,
    resolve_designated_face_index,
    validate_recorded_edges,
    verify_authorization,
    verify_recorded_set_agreement,
)

PLAN_ID = "a" * 64
SOURCE_DIGEST = "b" * 64
CORRECTION_ID = "MESH_WINDING_INCONSISTENT-pitch-4339c3a7"


def _artifact(**overrides):
    """A valid D2-style authorization mapping; ``overrides`` tweak fields."""
    payload = {
        "authorization_version": AUTHORIZATION_VERSION,
        "authorization_policy_version": "1",
        "decision": "APPROVED",
        "correction_type": WINDING_CORRECTION_TYPE,
        "correction_id": CORRECTION_ID,
        "plan_id": PLAN_ID,
        "source_report_digest": SOURCE_DIGEST,
        "authorized_by": "operator@atlas",
        "authorized_at_utc": "2026-09-11T12:00:00Z",
        "designated_face_index": 1,
    }
    payload.update(overrides)
    return payload


def _parsed(**overrides):
    return parse_authorization(_artifact(**overrides))


def _work(**overrides):
    payload = {
        "correction_type": WINDING_CORRECTION_TYPE,
        "correction_id": CORRECTION_ID,
        "plan_id": PLAN_ID,
        "source_report_digest": SOURCE_DIGEST,
        "selection_mode": "D2",
        "plan_designated_face_index": None,
        "candidate_pair": (0, 1),
    }
    payload.update(overrides)
    return PresentedWork(**payload)


# ---------------------------------------------------------------------------
# A. parsing / canonical form
# ---------------------------------------------------------------------------


def test_parse_from_mapping_accepts_valid_artifact():
    artifact = _parsed()
    assert type(artifact) is AuthorizationArtifact
    assert artifact.decision == "APPROVED"
    assert artifact.correction_type == WINDING_CORRECTION_TYPE
    assert artifact.designated_face_index == 1
    assert artifact.expected_face_tuple is None
    assert artifact.scope_note is None


def test_parse_from_canonical_json_text():
    text = json.dumps(_artifact(), sort_keys=True, separators=(",", ":"))
    artifact = parse_authorization(text)
    assert artifact.digest() == _parsed().digest()


def test_parse_accepts_key_order_and_whitespace_but_canonicalizes_output():
    shuffled = {"decision": "APPROVED"}
    for key, value in reversed(list(_artifact().items())):
        shuffled.setdefault(key, value)
    text = json.dumps(shuffled, indent=2, sort_keys=False)
    artifact = parse_authorization(text)
    assert artifact.canonical_json() == _parsed().canonical_json()


def test_duplicate_json_keys_are_rejected():
    text = '{"decision":"REJECTED","decision":"APPROVED","authorization_version":"1"}'
    with pytest.raises(AuthorizationInputError) as excinfo:
        parse_authorization(text)
    assert excinfo.value.failure_code == AuthorizationFailureCode.DUPLICATE_JSON_KEY


def test_nan_and_infinity_literals_are_rejected():
    for literal in ("NaN", "Infinity", "-Infinity"):
        text = json.dumps(_artifact()).replace('"1"', literal, 1)
        with pytest.raises(AuthorizationInputError) as excinfo:
            parse_authorization(text)
        assert excinfo.value.failure_code == AuthorizationFailureCode.NON_FINITE_NUMBER


@pytest.mark.parametrize("text,code", [
    ("[1,2]", AuthorizationFailureCode.NOT_A_MAPPING),
    ('"text"', AuthorizationFailureCode.NOT_A_MAPPING),
    ("null", AuthorizationFailureCode.NOT_A_MAPPING),
    ("{", AuthorizationFailureCode.MALFORMED_JSON),
])
def test_non_object_and_malformed_json_are_rejected(text, code):
    with pytest.raises(AuthorizationInputError) as excinfo:
        parse_authorization(text)
    assert excinfo.value.failure_code == code


def test_non_str_non_dict_input_is_rejected():
    for bad in (None, 5, 5.0, True, ["x"], object()):
        with pytest.raises(AuthorizationInputError) as excinfo:
            parse_authorization(bad)
        assert excinfo.value.failure_code == AuthorizationFailureCode.NOT_A_MAPPING


def test_unknown_field_is_rejected():
    with pytest.raises(AuthorizationInputError) as excinfo:
        _parsed(is_admin=True)
    assert excinfo.value.failure_code == AuthorizationFailureCode.UNKNOWN_FIELD


@pytest.mark.parametrize("field", [
    "authorization_version", "authorization_policy_version", "decision", "correction_type",
    "correction_id", "plan_id", "source_report_digest", "authorized_by", "authorized_at_utc",
])
def test_missing_required_field_is_rejected(field):
    payload = _artifact()
    payload.pop(field)
    with pytest.raises(AuthorizationInputError) as excinfo:
        parse_authorization(payload)
    assert excinfo.value.failure_code == AuthorizationFailureCode.MISSING_FIELD


def test_wrong_field_types_are_rejected():
    for kwargs in ({"authorized_by": 123}, {"decision": None}, {"designated_face_index": True},
                   {"designated_face_index": "1"}, {"designated_face_index": -1}):
        with pytest.raises(AuthorizationInputError) as excinfo:
            _parsed(**kwargs)
        assert excinfo.value.failure_code == AuthorizationFailureCode.FIELD_TYPE_INVALID


def test_empty_string_fields_are_rejected():
    with pytest.raises(AuthorizationInputError) as excinfo:
        _parsed(authorized_by="   ")
    assert excinfo.value.failure_code == AuthorizationFailureCode.FIELD_EMPTY


def test_non_json_native_values_are_rejected():
    with pytest.raises(AuthorizationInputError) as excinfo:
        _parsed(scope_note={"nested": object()})
    assert excinfo.value.failure_code == AuthorizationFailureCode.FIELD_TYPE_INVALID
    with pytest.raises(AuthorizationInputError) as excinfo:
        _parsed(scope_note={1: "int key"})
    assert excinfo.value.failure_code == AuthorizationFailureCode.FIELD_TYPE_INVALID


def test_expected_face_tuple_shape_is_validated():
    assert _parsed(expected_face_tuple=[0, 1, 2]).expected_face_tuple == (0, 1, 2)
    for bad in ([0, 1], [0, 1, 1], [0, 1, "2"], [0, 1, True], [-1, 0, 1], "012"):
        with pytest.raises(AuthorizationInputError) as excinfo:
            _parsed(expected_face_tuple=bad)
        assert excinfo.value.failure_code == AuthorizationFailureCode.FIELD_TYPE_INVALID


# ---------------------------------------------------------------------------
# B. token / version validation
# ---------------------------------------------------------------------------


def test_authorization_version_must_be_exact():
    assert _parsed().authorization_version == AUTHORIZATION_VERSION
    for bad in ("2", "1.0", " 1", "1 "):
        with pytest.raises(AuthorizationInputError) as excinfo:
            _parsed(authorization_version=bad)
        assert excinfo.value.failure_code == AuthorizationFailureCode.UNSUPPORTED_AUTHORIZATION_VERSION


def test_policy_version_must_be_in_the_accepted_set():
    assert ACCEPTED_AUTHORIZATION_POLICY_VERSIONS == frozenset({"1"})
    assert _parsed(authorization_policy_version="1").authorization_policy_version == "1"
    for bad in ("0", "2", "1.0", " 1", "1 "):
        with pytest.raises(AuthorizationInputError) as excinfo:
            _parsed(authorization_policy_version=bad)
        assert excinfo.value.failure_code == AuthorizationFailureCode.UNSUPPORTED_POLICY_VERSION


@pytest.mark.parametrize("bad,code", [
    ("approved", AuthorizationFailureCode.DECISION_NOT_APPROVED),
    ("Approved", AuthorizationFailureCode.DECISION_NOT_APPROVED),
    ("REJECTED", AuthorizationFailureCode.DECISION_NOT_APPROVED),
    ("YES", AuthorizationFailureCode.DECISION_NOT_APPROVED),
    ("", AuthorizationFailureCode.FIELD_EMPTY),
])
def test_decision_must_be_exactly_APPROVED(bad, code):
    with pytest.raises(AuthorizationInputError) as excinfo:
        _parsed(decision=bad)
    assert excinfo.value.failure_code == code


@pytest.mark.parametrize("bad,code", [
    ("RENAME_OBJECT", AuthorizationFailureCode.CORRECTION_TYPE_NOT_AUTHORIZABLE),
    ("REMOVE_DUPLICATE_FACE", AuthorizationFailureCode.CORRECTION_TYPE_NOT_AUTHORIZABLE),
    ("repair_face_winding", AuthorizationFailureCode.CORRECTION_TYPE_NOT_AUTHORIZABLE),
    ("REPAIR_FACE_WINDING ", AuthorizationFailureCode.CORRECTION_TYPE_NOT_AUTHORIZABLE),
    ("", AuthorizationFailureCode.FIELD_EMPTY),
])
def test_correction_type_must_be_the_winding_token(bad, code):
    with pytest.raises(AuthorizationInputError) as excinfo:
        _parsed(correction_type=bad)
    assert excinfo.value.failure_code == code


def test_digest_fields_require_64_lowercase_hex():
    for bad in ("A" * 64, "a" * 63, "a" * 65, "z" * 64, " " + "a" * 64):
        for field in ("plan_id", "source_report_digest"):
            with pytest.raises(AuthorizationInputError) as excinfo:
                _parsed(**{field: bad})
            assert excinfo.value.failure_code == AuthorizationFailureCode.DIGEST_FORMAT_INVALID


# ---------------------------------------------------------------------------
# C. canonical serialization / digest
# ---------------------------------------------------------------------------


def test_canonical_json_is_sorted_compact_ascii():
    text = _parsed().canonical_json()
    assert text == json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"),
                              ensure_ascii=True)
    assert ", " not in text and ": " not in text


def test_digest_is_sha256_of_the_canonical_form():
    artifact = _parsed()
    expected = hashlib.sha256(artifact.canonical_json().encode("utf-8")).hexdigest()
    assert artifact.digest() == expected
    assert len(artifact.digest()) == 64 and artifact.digest() == artifact.digest().lower()


def test_digest_is_stable_across_input_ordering():
    first = _parsed(scope_note="a", expected_face_tuple=[2, 1, 0])
    shuffled = dict(reversed(list(_artifact(scope_note="a", expected_face_tuple=[2, 1, 0]).items())))
    second = parse_authorization(shuffled)
    assert first.digest() == second.digest()


def test_round_trip_through_json_keeps_identity():
    artifact = _parsed(expected_face_tuple=[3, 4, 5], scope_note="reviewed")
    reparsed = parse_authorization(artifact.to_json_compatible())
    assert reparsed.digest() == artifact.digest()


def test_to_json_compatible_serializes_tuples_as_lists():
    payload = _parsed(expected_face_tuple=[3, 4, 5]).to_json_compatible()
    assert payload["expected_face_tuple"] == [3, 4, 5]
    assert payload["designated_face_index"] == 1
    assert payload["scope_note"] is None
    json.dumps(payload)  # must be JSON-serializable


# ---------------------------------------------------------------------------
# D. binding gate
# ---------------------------------------------------------------------------


def test_d2_happy_path_verifies():
    verdict = verify_authorization(_parsed(), _work())
    assert verdict.ok is True
    assert verdict.outcome == AuthorizationOutcome.VERIFIED
    assert verdict.failure_code is None
    assert verdict.to_json_compatible() == {
        "authorization_verified": True, "outcome": AuthorizationOutcome.VERIFIED,
        "failure_code": None,
    }


def test_d1_happy_path_verifies_and_uses_the_evidence_designation():
    artifact = _parsed(designated_face_index=None)
    work = _work(selection_mode="D1", plan_designated_face_index=0, candidate_pair=None)
    assert verify_authorization(artifact, work).ok is True
    index, failure = resolve_designated_face_index(artifact, work)
    assert failure is None and index == 0


@pytest.mark.parametrize("override,code", [
    ({"correction_id": "MESH_WINDING_INCONSISTENT-pitch-deadbeef"},
     AuthorizationFailureCode.CORRECTION_ID_MISMATCH),
    ({"plan_id": "c" * 64}, AuthorizationFailureCode.PLAN_ID_MISMATCH),
    ({"source_report_digest": "d" * 64}, AuthorizationFailureCode.SOURCE_DIGEST_MISMATCH),
])
def test_binding_mismatches_fail_closed_with_scope_mismatch(override, code):
    verdict = verify_authorization(_parsed(**override), _work())
    assert verdict.ok is False
    assert verdict.outcome == AuthorizationOutcome.SCOPE_MISMATCH
    assert verdict.failure_code == code


def test_correction_type_mismatch_fails_closed():
    work = _work()
    object.__setattr__(work, "correction_type", "REMOVE_DEGENERATE_FACE")
    verdict = verify_authorization(_parsed(), work)
    assert verdict.outcome == AuthorizationOutcome.SCOPE_MISMATCH
    assert verdict.failure_code == AuthorizationFailureCode.CORRECTION_TYPE_MISMATCH


def test_d2_without_designation_requires_authorization():
    verdict = verify_authorization(_parsed(designated_face_index=None), _work())
    assert verdict.outcome == AuthorizationOutcome.REQUIRED
    assert verdict.failure_code == AuthorizationFailureCode.DESIGNATION_REQUIRED


def test_d2_designation_must_be_a_member_of_the_candidate_pair():
    verdict = verify_authorization(_parsed(designated_face_index=7), _work(candidate_pair=(0, 1)))
    assert verdict.outcome == AuthorizationOutcome.SCOPE_MISMATCH
    assert verdict.failure_code == AuthorizationFailureCode.DESIGNATION_NOT_IN_CANDIDATE_PAIR


def test_d2_candidate_pair_is_required():
    verdict = verify_authorization(_parsed(), _work(candidate_pair=None))
    assert verdict.outcome == AuthorizationOutcome.SCOPE_MISMATCH
    assert verdict.failure_code == AuthorizationFailureCode.CANDIDATE_PAIR_MISSING


def test_candidate_pair_must_be_two_distinct_faces():
    with pytest.raises(AuthorizationInputError) as excinfo:
        _work(candidate_pair=(3, 3))
    assert excinfo.value.failure_code == AuthorizationFailureCode.CANDIDATE_PAIR_INVALID
    with pytest.raises(AuthorizationInputError) as excinfo:
        _work(candidate_pair=(1,))
    assert excinfo.value.failure_code == AuthorizationFailureCode.CANDIDATE_PAIR_INVALID


def test_d1_must_not_supply_a_designation():
    work = _work(selection_mode="D1", plan_designated_face_index=0)
    verdict = verify_authorization(_parsed(designated_face_index=1), work)
    assert verdict.outcome == AuthorizationOutcome.SCOPE_MISMATCH
    assert verdict.failure_code == AuthorizationFailureCode.DESIGNATION_SUPPLIED_FOR_D1


def test_d1_requires_a_plan_side_designation():
    work = _work(selection_mode="D1", plan_designated_face_index=None)
    verdict = verify_authorization(_parsed(designated_face_index=None), work)
    assert verdict.outcome == AuthorizationOutcome.SCOPE_MISMATCH
    assert verdict.failure_code == AuthorizationFailureCode.PLAN_DESIGNATION_MISSING


def test_selection_mode_must_be_known():
    with pytest.raises(AuthorizationInputError) as excinfo:
        PresentedWork(correction_type=WINDING_CORRECTION_TYPE, correction_id=CORRECTION_ID,
                      plan_id=PLAN_ID, source_report_digest=SOURCE_DIGEST, selection_mode="D9")
    assert excinfo.value.failure_code == AuthorizationFailureCode.SELECTION_MODE_INVALID


def test_presented_work_validates_its_own_identity_fields():
    with pytest.raises(AuthorizationInputError) as excinfo:
        _work(correction_id="")
    assert excinfo.value.failure_code == AuthorizationFailureCode.FIELD_EMPTY
    with pytest.raises(AuthorizationInputError) as excinfo:
        _work(plan_id="not-a-digest")
    assert excinfo.value.failure_code == AuthorizationFailureCode.DIGEST_FORMAT_INVALID


# ---------------------------------------------------------------------------
# E. optional expected_face_tuple (redundant assertion, never authority)
# ---------------------------------------------------------------------------


def test_expected_face_tuple_absent_is_fine():
    assert verify_authorization(_parsed(), _work()).ok is True


def test_expected_face_tuple_matching_is_accepted():
    artifact = _parsed(expected_face_tuple=[2, 1, 0])
    verdict = verify_authorization(artifact, _work(execution_face_tuple=(2, 1, 0)))
    assert verdict.ok is True


def test_expected_face_tuple_mismatch_fails_closed():
    artifact = _parsed(expected_face_tuple=[2, 1, 0])
    verdict = verify_authorization(artifact, _work(execution_face_tuple=(0, 1, 3)))
    assert verdict.outcome == AuthorizationOutcome.SCOPE_MISMATCH
    assert verdict.failure_code == AuthorizationFailureCode.EXPECTED_FACE_TUPLE_MISMATCH


def test_expected_face_tuple_present_without_execution_tuple_fails_closed():
    verdict = verify_authorization(_parsed(expected_face_tuple=[2, 1, 0]), _work())
    assert verdict.outcome == AuthorizationOutcome.INVALID
    assert verdict.failure_code == AuthorizationFailureCode.EXECUTION_FACE_TUPLE_UNAVAILABLE


def test_expected_face_tuple_is_not_mandatory_and_is_not_the_authority():
    # the field is optional; a caller cannot use it to assert a different target's identity,
    # because the target itself is re-derived from the authorized plan + fresh source
    assert _parsed().expected_face_tuple is None
    artifact = _parsed(expected_face_tuple=[9, 8, 7])
    assert verify_authorization(artifact, _work(execution_face_tuple=(0, 1, 3))).ok is False


def test_verdict_is_deterministic_and_never_wraps_mismatches_in_exceptions():
    artifact, work = _parsed(), _work()
    first, second = verify_authorization(artifact, work), verify_authorization(artifact, work)
    assert first == second
    bad = verify_authorization(_parsed(plan_id="c" * 64), work)
    assert bad == verify_authorization(_parsed(plan_id="c" * 64), work)


# ---------------------------------------------------------------------------
# F. WC-P17: recorded-edge / counterpart contract
# ---------------------------------------------------------------------------


def test_valid_recorded_set_is_returned_canonical():
    edges, counterparts = validate_recorded_edges(
        [[0, 1], [1, 2]], [1, 2], designated_face_index=0
    )
    assert edges == ((0, 1), (1, 2))
    assert counterparts == (1, 2)


@pytest.mark.parametrize("bad,code", [
    (None, AuthorizationFailureCode.RECORDED_EDGES_MISSING),
    ([], AuthorizationFailureCode.RECORDED_EDGES_EMPTY),
    ("01", AuthorizationFailureCode.RECORDED_EDGES_MISSING),
])
def test_missing_or_empty_recorded_edges_are_rejected(bad, code):
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_recorded_edges(bad, [1], designated_face_index=0)
    assert excinfo.value.failure_code == code


@pytest.mark.parametrize("edge,code", [
    ([0], AuthorizationFailureCode.RECORDED_EDGE_ARITY),
    ([0, 1, 2], AuthorizationFailureCode.RECORDED_EDGE_ARITY),
    ([0, "1"], AuthorizationFailureCode.RECORDED_EDGE_NON_INTEGER),
    ([0, True], AuthorizationFailureCode.RECORDED_EDGE_NON_INTEGER),
    ([0, -1], AuthorizationFailureCode.RECORDED_EDGE_NON_INTEGER),
    ([1, 1], AuthorizationFailureCode.RECORDED_EDGE_SELF_LOOP),
])
def test_malformed_edges_are_rejected_with_deterministic_codes(edge, code):
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_recorded_edges([edge], [9], designated_face_index=0)
    assert excinfo.value.failure_code == code


def test_non_canonical_edge_order_is_rejected():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_recorded_edges([[1, 0]], [1], designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.RECORDED_EDGE_NOT_CANONICAL


def test_unsorted_edges_are_rejected():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_recorded_edges([[1, 2], [0, 1]], [2, 1], designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.RECORDED_EDGES_NOT_SORTED


def test_duplicated_edges_are_rejected():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_recorded_edges([[0, 1], [0, 1]], [1, 1], designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.RECORDED_EDGES_DUPLICATED


def test_counterpart_list_must_be_positionally_aligned():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_recorded_edges([[0, 1], [1, 2]], [1], designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.COUNTERPART_COUNT_MISMATCH
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_recorded_edges([[0, 1]], None, designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.COUNTERPART_COUNT_MISMATCH


def test_counterparts_must_be_exact_integers():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_recorded_edges([[0, 1]], [True], designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.COUNTERPART_NON_INTEGER


def test_counterpart_must_differ_from_the_designated_face():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_recorded_edges([[0, 1]], [0], designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.COUNTERPART_EQUALS_DESIGNATED_FACE


def test_counterpart_rule_ignored_when_no_designated_face_is_supplied():
    # pure canonical validation is still available without a designation
    edges, counterparts = validate_recorded_edges([[0, 1]], [0])
    assert edges == ((0, 1),) and counterparts == (0,)


def test_valid_recorded_set_requires_no_designated_face_argument():
    assert validate_recorded_edges([[0, 1]], [1]) == (((0, 1),), (1,))


# ---------------------------------------------------------------------------
# G. execute-time WC-P17 agreement (bidirectional)
# ---------------------------------------------------------------------------

FRESH = [
    {"edge": [0, 1], "faces": [0, 1]},
    {"edge": [1, 2], "faces": [0, 2]},
]


def test_bidirectional_agreement_accepts_the_exact_set():
    edges, counterparts = verify_recorded_set_agreement(
        [[0, 1], [1, 2]], [1, 2], FRESH, designated_face_index=0
    )
    assert edges == ((0, 1), (1, 2)) and counterparts == (1, 2)


def test_under_declared_recorded_set_fails_closed():
    with pytest.raises(AuthorizationContractError) as excinfo:
        verify_recorded_set_agreement([[0, 1]], [1], FRESH, designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.RECORDED_SET_MISMATCH


def test_over_declared_recorded_set_fails_closed():
    # the over-declared list must itself be canonical and sorted, so that the SET comparison is
    # what fails (a malformed list is rejected earlier, by the canonical-form checks)
    with pytest.raises(AuthorizationContractError) as excinfo:
        verify_recorded_set_agreement(
            [[0, 1], [1, 2], [2, 3]], [1, 2, 3], FRESH, designated_face_index=0
        )
    assert excinfo.value.failure_code == AuthorizationFailureCode.RECORDED_SET_MISMATCH


def test_stale_finding_set_fails_closed():
    stale = [{"edge": [0, 1], "faces": [0, 1]}]  # one finding disappeared
    with pytest.raises(AuthorizationContractError) as excinfo:
        verify_recorded_set_agreement([[0, 1], [1, 2]], [1, 2], stale, designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.RECORDED_SET_MISMATCH


def test_empty_fresh_set_fails_closed():
    with pytest.raises(AuthorizationContractError) as excinfo:
        verify_recorded_set_agreement([[0, 1]], [1], [], designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.RECORDED_SET_MISMATCH


def test_designated_face_must_appear_in_the_fresh_pair():
    fresh = [{"edge": [0, 1], "faces": [1, 2]}]
    with pytest.raises(AuthorizationContractError) as excinfo:
        verify_recorded_set_agreement([[0, 1]], [1], fresh, designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.DESIGNATED_NOT_IN_FRESH_PAIR


def test_counterpart_must_appear_in_the_fresh_pair():
    fresh = [{"edge": [0, 1], "faces": [0, 3]}]
    with pytest.raises(AuthorizationContractError) as excinfo:
        verify_recorded_set_agreement([[0, 1]], [1], fresh, designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.COUNTERPART_NOT_IN_FRESH_PAIR


def test_counterpart_outside_the_fresh_pair_is_rejected():
    fresh = [{"edge": [0, 1], "faces": [0, 1]}]
    with pytest.raises(AuthorizationContractError) as excinfo:
        verify_recorded_set_agreement([[0, 1]], [2], fresh, designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.COUNTERPART_NOT_IN_FRESH_PAIR


def test_membership_checks_imply_the_pair_is_exactly_designated_and_counterpart():
    # ``_fresh_finding`` enforces a 2-element pair and ``validate_recorded_edges`` enforces
    # ``counterpart != designated``; together with the two membership checks that makes an
    # explicit "set(faces) == {designated, counterpart}" branch unreachable, so the implication
    # is pinned here instead: acceptance occurs only when the pair is exactly those two faces.
    fresh = [{"edge": [0, 1], "faces": [1, 0]}]      # canonicalized internally
    edges, counterparts = verify_recorded_set_agreement(
        [[0, 1]], [1], fresh, designated_face_index=0
    )
    assert edges == ((0, 1),) and counterparts == (1,)
    # any third face in the pair is impossible (2-element contract), so a wrong counterpart can
    # only ever be caught by the membership check above
    with pytest.raises(AuthorizationContractError) as excinfo:
        verify_recorded_set_agreement([[0, 1]], [0], fresh, designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.COUNTERPART_EQUALS_DESIGNATED_FACE


def test_malformed_fresh_finding_fails_closed():
    for bad in [None, {"edge": [0, 1]}, {"edge": [0], "faces": [0, 1]},
                {"edge": [0, 1], "faces": [0]}, {"edge": [0, 1], "faces": [0, True]}]:
        with pytest.raises(AuthorizationContractError) as excinfo:
            verify_recorded_set_agreement([[0, 1]], [1], [bad], designated_face_index=0)
        assert excinfo.value.failure_code == AuthorizationFailureCode.FRESH_FINDING_INVALID


def test_invalid_designated_face_argument_fails_closed():
    for bad in (True, -1, "0", None):
        with pytest.raises(AuthorizationContractError) as excinfo:
            verify_recorded_set_agreement([[0, 1]], [1], FRESH, designated_face_index=bad)
        assert excinfo.value.failure_code == AuthorizationFailureCode.DESIGNATED_FACE_INVALID


def test_p17_is_not_satisfiable_without_a_fresh_recomputation():
    # the recorded set is validated against the FRESH set, never trusted by itself
    with pytest.raises(AuthorizationContractError) as excinfo:
        verify_recorded_set_agreement([[0, 1]], [1], [], designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.RECORDED_SET_MISMATCH
    assert verify_recorded_set_agreement([[0, 1]], [1], [{"edge": [0, 1], "faces": [0, 1]}],
                                         designated_face_index=0)[0] == ((0, 1),)


# ---------------------------------------------------------------------------
# H. authority isolation / determinism
# ---------------------------------------------------------------------------


def test_module_has_no_bpy_or_execution_imports():
    source = inspect.getsource(
        __import__("planning.blender.correction_authorization", fromlist=["x"])
    )
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not ({"bpy", "bmesh", "subprocess", "os", "shutil", "random", "time", "socket"}
                & imported), imported


def test_module_exposes_no_mutation_or_persistence_surface():
    module = __import__("planning.blender.correction_authorization", fromlist=["x"])
    forbidden = ("execute", "mutator", "save", "persist", "rollback", "write", "apply",
                 "commit", "delete", "remove", "rename", "bpy")
    offenders = [name for name in dir(module)
                 if not name.startswith("__") and any(f in name.lower() for f in forbidden)]
    assert offenders == [], offenders


def test_no_authorization_expired_token_is_emitted():
    # design §1.5: defined but never emitted — the failure-code table must not carry it
    from planning.blender.correction_authorization import AuthorizationFailureCode as Codes
    assert not [n for n in dir(Codes) if "EXPIRED" in n.upper()]
    assert not hasattr(AuthorizationOutcome, "EXPIRED")


def test_parser_and_gate_are_deterministic_across_repeats():
    artifact = _parsed(expected_face_tuple=[2, 1, 0], scope_note="note")
    work = _work(execution_face_tuple=(2, 1, 0))
    digests = {artifact.digest() for _ in range(3)}
    verdicts = {verify_authorization(_parsed(expected_face_tuple=[2, 1, 0], scope_note="note"),
                                     work) for _ in range(3)}
    assert len(digests) == 1 and len(verdicts) == 1
    assert verdicts.pop().ok is True


def test_artifact_is_immutable():
    artifact = _parsed()
    with pytest.raises(Exception):
        artifact.decision = "REJECTED"
    with pytest.raises(Exception):
        artifact.designated_face_index = 5

# ---------------------------------------------------------------------------
# I. duplicate fresh-finding edges are rejected, never collapsed (M2 remediation)
# ---------------------------------------------------------------------------

UNIQUE_FRESH = [
    {"edge": [0, 1], "faces": [0, 1]},
    {"edge": [1, 2], "faces": [0, 2]},
]


def test_duplicate_fresh_finding_edge_is_rejected():
    dup = [{"edge": [0, 1], "faces": [0, 1]}, {"edge": [0, 1], "faces": [0, 1]}]
    with pytest.raises(AuthorizationContractError) as excinfo:
        verify_recorded_set_agreement([[0, 1]], [1], dup, designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.DUPLICATE_FRESH_EDGE


def test_duplicate_fresh_edge_cannot_be_hidden_by_ordering():
    # a contradictory duplicate: "last write wins" would ACCEPT the good-last ordering
    good_last = [{"edge": [0, 1], "faces": [0, 5]}, {"edge": [0, 1], "faces": [0, 1]}]
    good_first = [{"edge": [0, 1], "faces": [0, 1]}, {"edge": [0, 1], "faces": [0, 5]}]
    for ordering in (good_last, good_first):
        with pytest.raises(AuthorizationContractError) as excinfo:
            verify_recorded_set_agreement([[0, 1]], [1], ordering, designated_face_index=0)
        assert excinfo.value.failure_code == AuthorizationFailureCode.DUPLICATE_FRESH_EDGE


def test_duplicate_fresh_edge_is_rejected_anywhere_in_the_set():
    dup = list(UNIQUE_FRESH) + [{"edge": [1, 2], "faces": [0, 2]}]
    with pytest.raises(AuthorizationContractError) as excinfo:
        verify_recorded_set_agreement([[0, 1], [1, 2]], [1, 2], dup, designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.DUPLICATE_FRESH_EDGE


def test_duplicate_detection_precedes_the_set_comparison():
    # a malformed (duplicated) recomputation is reported as malformed, not as a set mismatch
    dup = [{"edge": [0, 1], "faces": [0, 1]}, {"edge": [0, 1], "faces": [0, 1]}]
    with pytest.raises(AuthorizationContractError) as excinfo:
        verify_recorded_set_agreement([[0, 1], [1, 2]], [1, 2], dup, designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.DUPLICATE_FRESH_EDGE


def test_valid_unique_fresh_finding_set_still_passes():
    edges, counterparts = verify_recorded_set_agreement(
        [[0, 1], [1, 2]], [1, 2], list(UNIQUE_FRESH), designated_face_index=0
    )
    assert edges == ((0, 1), (1, 2))
    assert counterparts == (1, 2)


def test_duplicate_rejection_leaves_under_and_over_declared_behaviour_unchanged():
    with pytest.raises(AuthorizationContractError) as under:
        verify_recorded_set_agreement([[0, 1]], [1], list(UNIQUE_FRESH), designated_face_index=0)
    assert under.value.failure_code == AuthorizationFailureCode.RECORDED_SET_MISMATCH
    with pytest.raises(AuthorizationContractError) as over:
        verify_recorded_set_agreement([[0, 1], [1, 2], [2, 3]], [1, 2, 3], list(UNIQUE_FRESH),
                                      designated_face_index=0)
    assert over.value.failure_code == AuthorizationFailureCode.RECORDED_SET_MISMATCH


# ---------------------------------------------------------------------------
# J. assertion discipline: the structured checks cannot be satisfied by text
# ---------------------------------------------------------------------------


def test_structured_code_assertion_cannot_be_satisfied_by_message_text():
    class Impostor(Exception):
        def __init__(self):
            super().__init__("RECORDED_SET_MISMATCH")  # identical TEXT, no structured code

    impostor = Impostor()
    assert "RECORDED_SET_MISMATCH" in str(impostor)      # a substring check would have passed
    assert not hasattr(impostor, "failure_code")         # the structured check cannot pass
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_recorded_edges([[1, 0]], [1], designated_face_index=0)
    assert excinfo.value.failure_code == AuthorizationFailureCode.RECORDED_EDGE_NOT_CANONICAL
    assert excinfo.value.failure_code != AuthorizationFailureCode.RECORDED_EDGES_NOT_SORTED


def test_every_declared_raise_carries_a_non_None_failure_code():
    probes = [
        lambda: parse_authorization({"unknown": 1}),
        lambda: parse_authorization(_artifact(decision="REJECTED")),
        lambda: parse_authorization(_artifact(authorization_policy_version="9")),
        lambda: validate_recorded_edges([], [1], designated_face_index=0),
        lambda: validate_recorded_edges([[0, 0]], [1], designated_face_index=0),
        lambda: validate_recorded_edges([[1, 0]], [1], designated_face_index=0),
        lambda: verify_recorded_set_agreement([[0, 1]], [0], UNIQUE_FRESH, designated_face_index=0),
        lambda: verify_recorded_set_agreement([[0, 1]], [1], [], designated_face_index=0),
        lambda: verify_recorded_set_agreement([[0, 1]], [1], [{"edge": [0], "faces": [0, 1]}],
                                              designated_face_index=0),
    ]
    for probe in probes:
        with pytest.raises(AuthorizationError) as excinfo:
            probe()
        assert excinfo.value.failure_code is not None
        assert type(excinfo.value.failure_code) is str
