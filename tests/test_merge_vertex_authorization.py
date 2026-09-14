"""Deterministic tests for the Wave-3 ``REPAIR_MERGE_VERTEX`` authorization/contract layer.

Covers ONLY the contract implemented in ``planning/blender/correction_authorization.py``
(Wave-3 design §2/§3/§4/§8/§10): the extended artifact (``expected_merge_mapping_digest`` +
field applicability), the exact ``target_object_mesh`` shape, the canonical duplicate-group /
survivor / index-mapping validators, the exact-bit vs sub-grid case rule and its refusal policy,
the canonical mapping digest, the merge binding gate, determinism, and authority isolation.

There is NO bpy, NO Blender, NO live run and NO mutation in this suite — no merge executor or
planner proposal exists yet, so nothing here can execute a merge.

Test discipline: artifacts are built from REAL, content-addressed bindings — the plan id and source
digest are taken from an actual ``CorrectionPlan``/``SceneReport`` produced by the project's own
planner and kernel, and the correction id is derived with the planner's own content-addressed id
function. Nothing fakes a plan id or bypasses artifact integrity.

Negative cases assert the STRUCTURED failure contract: every declared error carries its
``AuthorizationFailureCode`` as an attribute, so assertions compare values exactly — never error
text, and never a substring that an unrelated error could also satisfy.
"""
import ast
import hashlib
import json

import pytest

from planning.blender import correction_planner as planner_module
from planning.blender.correction_authorization import (
    ACCEPTED_AUTHORIZATION_POLICY_VERSIONS,
    AUTHORIZABLE_CORRECTION_TYPES,
    AUTHORIZATION_VERSION,
    MERGE_CASE_EXACT,
    MERGE_CASE_SUB_GRID,
    MERGE_CORRECTION_TYPE,
    WINDING_CORRECTION_TYPE,
    AuthorizationArtifact,
    AuthorizationContractError,
    AuthorizationError,
    AuthorizationFailureCode,
    AuthorizationInputError,
    AuthorizationOutcome,
    MergePresentedWork,
    canonical_coincidence_key,
    canonical_survivor_indices,
    classify_duplicate_group_case,
    make_index_mapping,
    mapping_digest,
    parse_authorization,
    require_supported_case,
    validate_duplicate_groups,
    validate_index_mapping,
    validate_survivor_indices,
    validate_target_object_mesh,
    verify_merge_authorization,
)
from planning.blender.finding_codes import FindingCode
from planning.blender.scene_report import REPORT_FORMAT_VERSION, Finding, build_report

MESH_ID = "pitch_mesh"
OBJECT_ID = "pitch"
_GROUP = ((0, 3),)
#: A vertex table whose exact-bit duplicate pair is (0, 3).
VERTICES = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 0.0))
_PROFILE = {
    "name": "soccer-field",
    "version": "1",
    "allowed_units": ["METERS", "meters", "m"],
    "name_pattern": r"^[a-z0-9][a-z0-9._-]*$",
}


def _real_bindings(mesh_id: str = MESH_ID):
    """Return (plan_id, source_report_digest, correction_id) from REAL planner/kernel output."""
    findings = [
        Finding(
            code=FindingCode.MESH_DUPLICATE_VERTEX,
            object_id=OBJECT_ID,
            mesh_id=mesh_id,
            measured={"vertex_a": 0, "vertex_b": 3, "coordinate": [0.0, 0.0, 0.0]},
        )
    ]
    report = build_report(
        scene_id="scene",
        validation_state="needs_review",
        findings=findings,
        scene_metrics={},
        profile_name="soccer-field",
    )
    payload = report.to_json_compatible()
    payload["digest"] = report.digest()
    payload["report_format_version"] = REPORT_FORMAT_VERSION
    plan = planner_module.plan_scene_report(payload, profile=_PROFILE)
    correction_id = planner_module._correction_id(
        FindingCode.MESH_DUPLICATE_VERTEX,
        OBJECT_ID,
        mesh_id,
        {"mesh_id": mesh_id},
    )
    return plan.plan_id, report.digest(), correction_id


BINDINGS = _real_bindings()


def _artifact(**overrides):
    """A valid merge authorization mapping (real bindings); ``overrides`` tweak fields."""
    payload = {
        "authorization_version": AUTHORIZATION_VERSION,
        "authorization_policy_version": "1",
        "decision": "APPROVED",
        "correction_type": MERGE_CORRECTION_TYPE,
        "correction_id": BINDINGS[2],
        "plan_id": BINDINGS[0],
        "source_report_digest": BINDINGS[1],
        "authorized_by": "operator@atlas",
        "authorized_at_utc": "2026-09-11T12:00:00Z",
    }
    payload.update(overrides)
    return payload


def _parsed(**overrides):
    return parse_authorization(_artifact(**overrides))


def _work(**overrides):
    payload = {
        "correction_type": MERGE_CORRECTION_TYPE,
        "correction_id": BINDINGS[2],
        "plan_id": BINDINGS[0],
        "source_report_digest": BINDINGS[1],
        "target_object_mesh": {"object_id": OBJECT_ID, "mesh_id": MESH_ID},
        "plan_target_object_mesh": {"object_id": OBJECT_ID, "mesh_id": MESH_ID},
        "duplicate_groups": _GROUP,
        "mapping_digest": mapping_digest(MESH_ID, len(VERTICES), make_index_mapping(len(VERTICES), _GROUP)),
    }
    payload.update(overrides)
    return MergePresentedWork(**payload)


# ===========================================================================
# A. AUTHORIZATION
# ===========================================================================


def test_valid_merge_artifact_verifies():
    verdict = verify_merge_authorization(_parsed(), _work())
    assert verdict.ok is True
    assert verdict.outcome == AuthorizationOutcome.VERIFIED
    assert verdict.failure_code is None


def test_merge_correction_type_is_authorizable_and_others_are_not():
    assert MERGE_CORRECTION_TYPE in AUTHORIZABLE_CORRECTION_TYPES
    assert WINDING_CORRECTION_TYPE in AUTHORIZABLE_CORRECTION_TYPES
    with pytest.raises(AuthorizationInputError) as excinfo:
        _parsed(correction_type="REPAIR_SOMETHING_ELSE")
    assert excinfo.value.failure_code == AuthorizationFailureCode.CORRECTION_TYPE_NOT_AUTHORIZABLE


def test_wrong_correction_id_fails_closed():
    verdict = verify_merge_authorization(_parsed(correction_id="MESH_DUPLICATE_VERTEX-x-00000000"), _work())
    assert verdict.ok is False
    assert verdict.outcome == AuthorizationOutcome.SCOPE_MISMATCH
    assert verdict.failure_code == AuthorizationFailureCode.CORRECTION_ID_MISMATCH


def test_wrong_plan_id_fails_closed():
    verdict = verify_merge_authorization(_parsed(plan_id="f" * 64), _work())
    assert verdict.failure_code == AuthorizationFailureCode.PLAN_ID_MISMATCH


def test_wrong_source_digest_fails_closed():
    verdict = verify_merge_authorization(_parsed(source_report_digest="e" * 64), _work())
    assert verdict.failure_code == AuthorizationFailureCode.SOURCE_DIGEST_MISMATCH


def test_wrong_policy_version_fails_closed_at_construction():
    with pytest.raises(AuthorizationInputError) as excinfo:
        _parsed(authorization_policy_version="2")
    assert excinfo.value.failure_code == AuthorizationFailureCode.UNSUPPORTED_POLICY_VERSION


@pytest.mark.parametrize("bad", [None, [], "not-a-mapping", 7, (("object_id", "a"),)])
def test_malformed_target_object_mesh_shape_is_refused(bad):
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_target_object_mesh(bad)
    assert excinfo.value.failure_code in {
        AuthorizationFailureCode.TARGET_SHAPE_INVALID,
        AuthorizationFailureCode.TARGET_MESH_UNRESOLVED,
    }


def test_target_object_mesh_extra_key_is_refused():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_target_object_mesh({"object_id": "a", "mesh_id": "m", "alias": "b"})
    assert excinfo.value.failure_code == AuthorizationFailureCode.TARGET_EXTRA_KEY


def test_target_object_mesh_missing_key_is_refused():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_target_object_mesh({"object_id": "a"})
    assert excinfo.value.failure_code == AuthorizationFailureCode.TARGET_MESH_UNRESOLVED


@pytest.mark.parametrize("bad", ["", "   "])
def test_target_object_mesh_empty_identifier_is_refused(bad):
    with pytest.raises(AuthorizationInputError) as excinfo:
        validate_target_object_mesh({"object_id": bad, "mesh_id": "m"})
    assert excinfo.value.failure_code == AuthorizationFailureCode.FIELD_EMPTY


def test_cross_object_or_cross_mesh_scope_is_not_expressible():
    """The target pair is exactly two identifiers; a second object/mesh has nowhere to live."""
    object_id, mesh_id = validate_target_object_mesh({"object_id": OBJECT_ID, "mesh_id": MESH_ID})
    assert (object_id, mesh_id) == (OBJECT_ID, MESH_ID)
    # A presented pair naming another mesh is refused against the plan-side target.
    verdict = verify_merge_authorization(
        _parsed(), _work(target_object_mesh={"object_id": OBJECT_ID, "mesh_id": "other_mesh"})
    )
    assert verdict.ok is False
    assert verdict.outcome == AuthorizationOutcome.SCOPE_MISMATCH
    assert verdict.failure_code == AuthorizationFailureCode.TARGET_CROSS_MESH


def test_cross_object_mismatch_is_refused():
    verdict = verify_merge_authorization(
        _parsed(), _work(target_object_mesh={"object_id": "goal_left", "mesh_id": MESH_ID})
    )
    assert verdict.ok is False
    assert verdict.failure_code == AuthorizationFailureCode.TARGET_CROSS_MESH


def test_matching_plan_side_target_verifies():
    verdict = verify_merge_authorization(
        _parsed(), _work(plan_target_object_mesh={"object_id": OBJECT_ID, "mesh_id": MESH_ID})
    )
    assert verdict.ok is True


def test_winding_fields_on_a_merge_artifact_are_refused():
    with pytest.raises(AuthorizationInputError) as excinfo:
        _parsed(designated_face_index=1)
    assert excinfo.value.failure_code == AuthorizationFailureCode.FIELD_NOT_APPLICABLE_TO_MERGE


def test_merge_field_on_a_winding_artifact_is_refused():
    with pytest.raises(AuthorizationInputError) as excinfo:
        _parsed(
            correction_type=WINDING_CORRECTION_TYPE,
            expected_merge_mapping_digest="a" * 64,
        )
    assert excinfo.value.failure_code == AuthorizationFailureCode.FIELD_NOT_APPLICABLE_TO_TYPE


def test_winding_artifact_json_is_unchanged_by_the_merge_field():
    """Backward compatibility: an artifact without the merge field serializes exactly as before."""
    artifact = _parsed()
    assert "expected_merge_mapping_digest" not in artifact.to_json_compatible()
    assert artifact.expected_merge_mapping_digest is None


def test_merge_artifact_serializes_the_assertion_when_present():
    digest = mapping_digest(MESH_ID, len(VERTICES), make_index_mapping(len(VERTICES), _GROUP))
    artifact = _parsed(expected_merge_mapping_digest=digest)
    assert artifact.to_json_compatible()["expected_merge_mapping_digest"] == digest
    assert json.loads(artifact.canonical_json())["expected_merge_mapping_digest"] == digest


def test_expected_mapping_digest_mismatch_fails_closed():
    verdict = verify_merge_authorization(_parsed(expected_merge_mapping_digest="c" * 64), _work())
    assert verdict.ok is False
    assert verdict.outcome == AuthorizationOutcome.SCOPE_MISMATCH
    assert verdict.failure_code == AuthorizationFailureCode.EXPECTED_MAPPING_DIGEST_MISMATCH


def test_expected_mapping_digest_without_a_recomputed_digest_fails_closed():
    verdict = verify_merge_authorization(
        _parsed(expected_merge_mapping_digest=BINDINGS[1]), _work(mapping_digest=None)
    )
    assert verdict.ok is False
    assert verdict.outcome == AuthorizationOutcome.INVALID
    assert verdict.failure_code == AuthorizationFailureCode.MAPPING_DIGEST_MISMATCH


def test_matching_expected_mapping_digest_verifies():
    digest = mapping_digest(MESH_ID, len(VERTICES), make_index_mapping(len(VERTICES), _GROUP))
    verdict = verify_merge_authorization(_parsed(expected_merge_mapping_digest=digest), _work())
    assert verdict.ok is True


def test_sub_grid_work_is_refused_before_authority_is_granted():
    verdict = verify_merge_authorization(_parsed(), _work(all_groups_exact=False))
    assert verdict.ok is False
    assert verdict.failure_code == AuthorizationFailureCode.SUB_GRID_COLLAPSE_UNSUPPORTED


def test_verify_merge_authorization_rejects_the_wrong_work_type():
    with pytest.raises(AuthorizationInputError) as excinfo:
        verify_merge_authorization(_parsed(), object())  # type: ignore[arg-type]
    assert excinfo.value.failure_code == AuthorizationFailureCode.FIELD_TYPE_INVALID


# ===========================================================================
# B. DUPLICATE GROUPS
# ===========================================================================


def test_valid_group_is_canonicalized():
    assert validate_duplicate_groups([[0, 3]]) == ((0, 3),)


def test_multiple_groups_must_be_ordered_by_survivor():
    assert validate_duplicate_groups([[0, 3], [1, 4]]) == ((0, 3), (1, 4))


def test_unordered_group_members_are_refused():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_duplicate_groups([[3, 0]])
    assert excinfo.value.failure_code == AuthorizationFailureCode.GROUP_MEMBERS_NOT_ASCENDING


def test_duplicate_member_is_refused():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_duplicate_groups([[0, 0, 3]])
    assert excinfo.value.failure_code == AuthorizationFailureCode.GROUP_MEMBERS_NOT_UNIQUE


def test_group_of_one_is_refused():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_duplicate_groups([[0]])
    assert excinfo.value.failure_code == AuthorizationFailureCode.GROUP_TOO_SMALL


def test_overlapping_groups_are_ambiguous_and_refused():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_duplicate_groups([[0, 3], [1, 3]])
    assert excinfo.value.failure_code == AuthorizationFailureCode.GROUP_MEMBERS_OVERLAP


def test_groups_not_ordered_by_survivor_are_refused():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_duplicate_groups([[1, 4], [0, 3]])
    assert excinfo.value.failure_code == AuthorizationFailureCode.GROUP_NOT_CANONICALLY_ORDERED


def test_non_integer_member_is_refused():
    with pytest.raises(AuthorizationInputError) as excinfo:
        validate_duplicate_groups([[0, 3.0]])
    assert excinfo.value.failure_code == AuthorizationFailureCode.FIELD_TYPE_INVALID


def test_mesh_id_of_the_wrong_type_is_refused():
    with pytest.raises(AuthorizationInputError) as excinfo:
        validate_duplicate_groups([[0, 3]], mesh_id=7)  # type: ignore[arg-type]
    assert excinfo.value.failure_code == AuthorizationFailureCode.FIELD_TYPE_INVALID


def test_transitive_group_representation_is_validated():
    groups = validate_duplicate_groups([[0, 3, 4]])
    assert groups == ((0, 3, 4),)
    assert canonical_survivor_indices(groups) == (0,)
    assert make_index_mapping(5, groups) == (0, 1, 2, 0, 0)


def test_non_coincident_declared_group_is_refused():
    table = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 0.5))
    with pytest.raises(AuthorizationContractError) as excinfo:
        require_supported_case(table, [[0, 2]])
    assert excinfo.value.failure_code == AuthorizationFailureCode.GROUP_MISMATCH


def test_group_member_outside_the_vertex_table_is_refused():
    with pytest.raises(AuthorizationContractError) as excinfo:
        make_index_mapping(3, [[0, 9]])
    assert excinfo.value.failure_code == AuthorizationFailureCode.MAPPING_TARGET_OUT_OF_RANGE


# ===========================================================================
# C. SURVIVOR CONTRACT
# ===========================================================================


def test_canonical_survivor_is_the_group_minimum():
    assert canonical_survivor_indices(((0, 3), (1, 4))) == (0, 1)
    assert validate_survivor_indices([0], ((0, 3),)) == (0,)


def test_survivor_not_in_its_group_is_refused():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_survivor_indices([7], ((0, 3),))
    assert excinfo.value.failure_code == AuthorizationFailureCode.SURVIVOR_NOT_IN_GROUP


def test_non_canonical_survivor_is_refused():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_survivor_indices([3], ((0, 3),))
    assert excinfo.value.failure_code == AuthorizationFailureCode.SURVIVOR_NOT_GROUP_MINIMUM


def test_survivor_count_mismatch_is_refused():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_survivor_indices([0, 1], ((0, 3),))
    assert excinfo.value.failure_code == AuthorizationFailureCode.SURVIVOR_COUNT_MISMATCH


def test_survivor_must_be_declared_never_inferred():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_survivor_indices(None, ((0, 3),))
    assert excinfo.value.failure_code == AuthorizationFailureCode.SURVIVOR_COUNT_MISMATCH


# ===========================================================================
# D. CASE CLASSIFICATION (EXACT vs SUB_GRID)
# ===========================================================================


def test_exact_bit_group_is_case_exact_and_accepted():
    assert classify_duplicate_group_case(VERTICES, (0, 3)) == MERGE_CASE_EXACT
    assert require_supported_case(VERTICES, _GROUP) == (MERGE_CASE_EXACT,)


def test_sub_grid_group_is_refused():
    near = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1e-7, 0.0, 0.0))
    assert classify_duplicate_group_case(near, (0, 3)) == MERGE_CASE_SUB_GRID
    with pytest.raises(AuthorizationContractError) as excinfo:
        require_supported_case(near, ((0, 3),))
    assert excinfo.value.failure_code == AuthorizationFailureCode.SUB_GRID_COLLAPSE_UNSUPPORTED


def test_case_decision_is_bitwise_not_key_based():
    """Two vertices can share the rounded key yet differ in the last bits → SUB_GRID."""
    a = (0.0, 0.0, 0.0)
    b = (1e-7, 0.0, 0.0)
    assert canonical_coincidence_key(a) == canonical_coincidence_key(b)
    assert classify_duplicate_group_case([a, b], (0, 1)) == MERGE_CASE_SUB_GRID


def test_boundary_at_the_kernel_rounding_semantics():
    """The key IS ``round(value, 6)`` — parity with mesh_health._rounded_vertex_key, including the
    half-to-even boundary and every adversarial value a C++ re-implementation must reproduce."""
    assert canonical_coincidence_key((0.0000005, 0.0, 0.0)) == (0.0, 0.0, 0.0)    # 0.5e-6 -> even
    assert canonical_coincidence_key((0.0000015, 0.0, 0.0)) == (2e-06, 0.0, 0.0)   # 1.5e-6 -> even
    for value in (0.0, 1e-7, 0.0000005, 0.0000015, 0.0000025, 0.1234565, -0.0000005, 1e-6, 12.3456789):
        assert canonical_coincidence_key((value, value, value)) == (
            round(value, 6), round(value, 6), round(value, 6)
        )


def test_one_micro_metre_apart_vertices_are_not_one_group():
    a = (0.0, 0.0, 0.0)
    b = (1e-6, 0.0, 0.0)
    assert canonical_coincidence_key(a) != canonical_coincidence_key(b)
    with pytest.raises(AuthorizationContractError) as excinfo:
        require_supported_case([a, b], [[0, 1]])
    assert excinfo.value.failure_code == AuthorizationFailureCode.GROUP_MISMATCH


# ===========================================================================
# E. INDEX MAPPING
# ===========================================================================


def test_make_index_mapping_is_the_design_mapping():
    assert make_index_mapping(4, ((0, 3),)) == (0, 1, 2, 0)
    assert make_index_mapping(5, ((0, 3, 4),)) == (0, 1, 2, 0, 0)
    assert make_index_mapping(4, ()) == (0, 1, 2, 3)


def test_valid_mapping_is_accepted():
    mapping = make_index_mapping(4, _GROUP)
    assert validate_index_mapping(mapping, mesh_id=MESH_ID, vertex_count=4, groups=_GROUP) == mapping


def test_mapping_length_mismatch_is_refused():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_index_mapping((0, 1, 2), mesh_id=MESH_ID, vertex_count=4, groups=_GROUP)
    assert excinfo.value.failure_code == AuthorizationFailureCode.MAPPING_LENGTH_MISMATCH


def test_mapping_target_out_of_range_is_refused():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_index_mapping((0, 1, 2, 9), mesh_id=MESH_ID, vertex_count=4, groups=_GROUP)
    assert excinfo.value.failure_code == AuthorizationFailureCode.MAPPING_TARGET_OUT_OF_RANGE


def test_negative_mapping_entry_is_refused():
    with pytest.raises(AuthorizationInputError) as excinfo:
        validate_index_mapping((0, 1, 2, -1), mesh_id=MESH_ID, vertex_count=4, groups=_GROUP)
    assert excinfo.value.failure_code == AuthorizationFailureCode.FIELD_TYPE_INVALID


def test_survivor_must_map_to_itself():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_index_mapping((1, 1, 2, 0), mesh_id=MESH_ID, vertex_count=4, groups=_GROUP)
    assert excinfo.value.failure_code == AuthorizationFailureCode.MAPPING_SURVIVOR_MISMATCH


def test_removed_duplicate_must_map_to_its_survivor():
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_index_mapping((0, 1, 2, 2), mesh_id=MESH_ID, vertex_count=4, groups=_GROUP)
    assert excinfo.value.failure_code == AuthorizationFailureCode.MAPPING_REMOVED_NOT_MAPPED


def test_stale_mapping_from_another_group_set_is_refused():
    stale = make_index_mapping(4, ((1, 3),))
    with pytest.raises(AuthorizationContractError) as excinfo:
        validate_index_mapping(stale, mesh_id=MESH_ID, vertex_count=4, groups=_GROUP)
    assert excinfo.value.failure_code in {
        AuthorizationFailureCode.MAPPING_SURVIVOR_MISMATCH,
        AuthorizationFailureCode.MAPPING_REMOVED_NOT_MAPPED,
        AuthorizationFailureCode.MAPPING_NONCANONICAL,
    }


def test_mapping_digest_is_content_addressed_and_stable():
    mapping = make_index_mapping(4, _GROUP)
    first = mapping_digest(MESH_ID, 4, mapping)
    second = mapping_digest(MESH_ID, 4, tuple(mapping))
    assert first == second
    assert len(first) == 64 and all(ch in "0123456789abcdef" for ch in first)


def test_mapping_digest_changes_with_mesh_id():
    mapping = make_index_mapping(4, _GROUP)
    assert mapping_digest(MESH_ID, 4, mapping) != mapping_digest("other_mesh", 4, mapping)


def test_mapping_digest_is_sha256_over_canonical_json():
    mapping = make_index_mapping(4, _GROUP)
    expected_body = {
        "mesh_id": MESH_ID,
        "n": 4,
        "m": 3,
        "kept": [0, 1, 2],
        "sigma": list(mapping),
    }
    expected = hashlib.sha256(
        json.dumps(expected_body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    assert mapping_digest(MESH_ID, 4, mapping) == expected


# ===========================================================================
# F. DETERMINISM
# ===========================================================================


def test_dictionary_insertion_order_does_not_change_the_digest():
    payload = _artifact()
    forward = parse_authorization(json.dumps(payload, sort_keys=True))
    reversed_payload = {k: payload[k] for k in reversed(list(payload))}
    backward = parse_authorization(json.dumps(reversed_payload, sort_keys=True))
    assert forward.digest() == backward.digest()
    assert forward.canonical_json() == backward.canonical_json()


def test_canonical_json_is_byte_identical_across_constructions():
    assert _parsed().canonical_json() == _parsed().canonical_json()
    assert _parsed().digest() == _parsed().digest()


def test_repeated_construction_is_identical():
    artifacts = [_parsed() for _ in range(5)]
    assert len({a.digest() for a in artifacts}) == 1
    assert len({a.canonical_json() for a in artifacts}) == 1


def test_mapping_and_groups_are_order_independent():
    mapping = make_index_mapping(4, _GROUP)
    assert mapping_digest(MESH_ID, 4, mapping) == mapping_digest(MESH_ID, 4, tuple(list(mapping)))


def test_verdict_is_deterministic():
    verdicts = {verify_merge_authorization(_parsed(), _work()).outcome for _ in range(5)}
    assert verdicts == {AuthorizationOutcome.VERIFIED}


def test_verdict_serialization_shape():
    verdict = verify_merge_authorization(_parsed(), _work())
    assert verdict.to_json_compatible() == {
        "authorization_verified": True,
        "outcome": AuthorizationOutcome.VERIFIED,
        "failure_code": None,
    }


# ===========================================================================
# H. ERROR BOUNDARY — every public Slice-1 validator must fail through the
#    declared AuthorizationInputError / AuthorizationContractError boundary
# ===========================================================================
#
# Regression guard for the defect proven by the hostile-input sweep: public validators that iterate,
# index or ``len()`` a caller container BEFORE validating it used to leak a raw ``TypeError`` (and, for
# float coercion, a ``ValueError``) instead of a declared contract error. The reported instances were
# ``require_supported_case`` and ``make_index_mapping``; the sweep above found the same class in eight
# more argument positions, so the fix routes every caller container through ONE declared normalization
# path and this section pins the whole boundary, not just the two named functions.
#
# Deliberately excluded from the battery: an astronomically large int driven through a COUNT position
# (``make_index_mapping(<huge>, ...)`` / ``validate_index_mapping(vertex_count=<huge>, ...)``) makes the
# canonical mapping's ``range(vertex_count)`` non-terminating. That is a documented unbounded-input
# path, not a declared malformed-input case, and it is NOT given an invented policy limit here.
HOSTILE_VALUES = (
    None, 0, 1, -1, True, False, 1.5, float("nan"), float("inf"), 10**400,
    "", "   ", "x", [], {}, (), set(), frozenset(), [{}], [[0, 3]], ((0, 3),), {"0": 3},
    b"bytes", bytearray(b"b"), memoryview(b"m"), object(),
    [None], [0, 3], (0,), ((0,),), [[0, 3]], {"object_id": "a"},
    [(0, 0)], [(0, 0, 0)], [(0, 0, 0, 0)], "a" * 64, (0, 3), [0.0, 0.0, 0.0], [["a", 0, 0]],
)


#: The huge int is never driven through a COUNT position (see the note above): doing so would iterate
#: ``range(vertex_count)`` and the battery would not terminate. Every other position keeps it.
COUNT_SAFE_VALUES = tuple(v for v in HOSTILE_VALUES if v != 10**400)


def _boundary_calls():
    """(label, callable) pairs: every public Slice-1 validator driven with every hostile value."""
    calls = []
    for tag, value in enumerate(COUNT_SAFE_VALUES):
        calls.append((f"validate_target_object_mesh[{tag}]", lambda v=value: validate_target_object_mesh(v)))
        calls.append((f"validate_duplicate_groups[{tag}]", lambda v=value: validate_duplicate_groups(v)))
        calls.append((f"canonical_survivor_indices[{tag}]", lambda v=value: canonical_survivor_indices(v)))
        calls.append((f"validate_survivor_indices[{tag}]", lambda v=value: validate_survivor_indices(v, _GROUP)))
        calls.append((f"validate_survivor_indices.groups[{tag}]", lambda v=value: validate_survivor_indices((0,), v)))
        calls.append((f"classify_case[table:{tag}]", lambda v=value: classify_duplicate_group_case(v, (0, 3))))
        calls.append((f"classify_case[group:{tag}]", lambda v=value: classify_duplicate_group_case(VERTICES, v)))
        calls.append((f"require_supported_case[table:{tag}]", lambda v=value: require_supported_case(v, _GROUP)))
        calls.append((f"require_supported_case[groups:{tag}]", lambda v=value: require_supported_case(VERTICES, v)))
        calls.append((f"make_index_mapping[count:{tag}]", lambda v=value: make_index_mapping(v, _GROUP)))
        calls.append((f"make_index_mapping[groups:{tag}]", lambda v=value: make_index_mapping(4, v)))
        calls.append((f"mapping_digest[mesh:{tag}]", lambda v=value: mapping_digest(v, 4, (0, 1, 2, 0))))
        calls.append((f"mapping_digest[count:{tag}]", lambda v=value: mapping_digest(MESH_ID, v, (0, 1, 2, 0))))
        calls.append((f"mapping_digest[mapping:{tag}]", lambda v=value: mapping_digest(MESH_ID, 4, v)))
        calls.append((f"validate_index_mapping[mapping:{tag}]",
                      lambda v=value: validate_index_mapping(v, mesh_id=MESH_ID, vertex_count=4, groups=_GROUP)))
        calls.append((f"validate_index_mapping[groups:{tag}]",
                      lambda v=value: validate_index_mapping((0, 1, 2, 0), mesh_id=MESH_ID, vertex_count=4, groups=v)))
        calls.append((f"validate_index_mapping[mesh:{tag}]",
                      lambda v=value: validate_index_mapping((0, 1, 2, 0), mesh_id=v, vertex_count=4, groups=_GROUP)))
        calls.append((f"validate_index_mapping[count:{tag}]",
                      lambda v=value: validate_index_mapping((0, 1, 2, 0), mesh_id=MESH_ID, vertex_count=v, groups=_GROUP)))
        calls.append((f"canonical_coincidence_key[{tag}]", lambda v=value: canonical_coincidence_key(v)))
    for tag, value in enumerate(HOSTILE_VALUES):
        # type-guarded positions: these can never reach an iteration, so the huge int is included
        calls.append((f"validate_target_object_mesh[huge:{tag}]", lambda v=value: validate_target_object_mesh(v)))
        calls.append((f"group_container[huge:{tag}]", lambda v=value: validate_duplicate_groups(v)))
        calls.append((f"require_supported_case.groups[huge:{tag}]", lambda v=value: require_supported_case(VERTICES, v)))
    return calls


#: The module declares its codes as class constants (not an Enum), so the closed set of legal codes is
#: derived from the class itself — an assertion against a hand-written list could drift from the module.
DECLARED_FAILURE_CODES = frozenset(
    value for name, value in vars(AuthorizationFailureCode).items()
    if name.isupper() and isinstance(value, str)
)

_BOUNDARY_CALLS = _boundary_calls()


@pytest.mark.parametrize("label,call", _BOUNDARY_CALLS, ids=[c[0] for c in _BOUNDARY_CALLS])
def test_no_undeclared_exception_escapes_any_public_validator(label, call):
    """A hostile value must produce a declared contract error — never a raw TypeError/ValueError."""
    try:
        call()
    except (AuthorizationInputError, AuthorizationContractError) as exc:
        assert exc.failure_code in DECLARED_FAILURE_CODES, (label, exc.failure_code)
    except Exception as exc:  # noqa: BLE001 - an undeclared exception IS the failure
        pytest.fail("%s leaked %s: %s" % (label, type(exc).__name__, exc))


@pytest.mark.parametrize(
    "bad,expected",
    [
        (None, AuthorizationFailureCode.GROUP_MISMATCH),
        (0, AuthorizationFailureCode.GROUP_MISMATCH),
        (True, AuthorizationFailureCode.GROUP_MISMATCH),
        (1.5, AuthorizationFailureCode.GROUP_MISMATCH),
        (b"g", AuthorizationFailureCode.GROUP_MISMATCH),
        ("g", AuthorizationFailureCode.GROUP_MISMATCH),
        ({"0": 3}, AuthorizationFailureCode.GROUP_MISMATCH),
        (object(), AuthorizationFailureCode.GROUP_MISMATCH),
    ],
)
def test_malformed_group_container_fails_closed_with_a_declared_code(bad, expected):
    """The reported defect: a non-iterable / wrong-typed group container leaked a raw TypeError."""
    with pytest.raises(AuthorizationContractError) as excinfo:
        require_supported_case(VERTICES, bad)
    assert excinfo.value.failure_code == expected
    with pytest.raises(AuthorizationContractError) as excinfo2:
        make_index_mapping(4, bad)
    assert excinfo2.value.failure_code == expected


@pytest.mark.parametrize("bad", [None, 0, True, 1.5, b"g", "g", {"0": 3}, object()])
def test_malformed_group_container_is_refused_by_every_group_consumer(bad):
    for call in (
        lambda: canonical_survivor_indices(bad),
        lambda: validate_survivor_indices((0,), bad),
        lambda: validate_index_mapping((0, 1, 2, 0), mesh_id=MESH_ID, vertex_count=4, groups=bad),
    ):
        with pytest.raises((AuthorizationInputError, AuthorizationContractError)):
            call()


@pytest.mark.parametrize("bad", [None, 0, True, 1.5, b"v", "v", (0.0, 0.0), (0.0, 0.0, 0.0, 0.0),
                                 ["a", "b", "c"], [None, None, None], object()])
def test_malformed_vertex_table_fails_closed(bad):
    with pytest.raises((AuthorizationInputError, AuthorizationContractError)):
        require_supported_case(bad, _GROUP)
    with pytest.raises((AuthorizationInputError, AuthorizationContractError)):
        classify_duplicate_group_case(bad, (0, 3))


@pytest.mark.parametrize("bad", [None, 0, True, b"c", "c", (0.0, 0.0), (0.0, 0.0, 0.0, 0.0),
                                 ["a", "b", "c"], [None, None, None], object()])
def test_malformed_coordinate_fails_closed(bad):
    with pytest.raises((AuthorizationInputError, AuthorizationContractError)):
        canonical_coincidence_key(bad)


@pytest.mark.parametrize("bad", [None, 0, True, b"m", "m", {"0": 1}, set(), object()])
def test_malformed_mapping_fails_closed(bad):
    with pytest.raises((AuthorizationInputError, AuthorizationContractError)):
        mapping_digest(MESH_ID, 4, bad)


def test_group_member_beyond_the_vertex_table_is_declared_not_index_error():
    """Index-out-of-range used to be a raw IndexError inside the case decision."""
    with pytest.raises(AuthorizationContractError) as excinfo:
        require_supported_case(VERTICES, [[0, 99]])
    assert excinfo.value.failure_code == AuthorizationFailureCode.MAPPING_TARGET_OUT_OF_RANGE
    with pytest.raises(AuthorizationContractError) as excinfo2:
        classify_duplicate_group_case(VERTICES, (0, 99))
    assert excinfo2.value.failure_code == AuthorizationFailureCode.MAPPING_TARGET_OUT_OF_RANGE


def test_valid_input_behaviour_is_unchanged_by_the_boundary_fix():
    """Positive controls: the fix validates containers only — it must not alter any accepted case."""
    assert validate_duplicate_groups([[0, 3]]) == ((0, 3),)
    assert canonical_survivor_indices(((0, 3), (1, 4))) == (0, 1)
    assert validate_survivor_indices([0, 1], ((0, 3), (1, 4))) == (0, 1)
    assert classify_duplicate_group_case(VERTICES, (0, 3)) == MERGE_CASE_EXACT
    assert require_supported_case(VERTICES, _GROUP) == (MERGE_CASE_EXACT,)
    assert make_index_mapping(4, _GROUP) == (0, 1, 2, 0)
    assert make_index_mapping(4, ()) == (0, 1, 2, 3)
    assert canonical_coincidence_key((0.0, 0.0, 0.0)) == (0.0, 0.0, 0.0)
    assert canonical_coincidence_key((0, 0, 0)) == (0, 0, 0)
    mapping = make_index_mapping(4, _GROUP)
    assert validate_index_mapping(mapping, mesh_id=MESH_ID, vertex_count=4, groups=_GROUP) == mapping
    assert mapping_digest(MESH_ID, 4, mapping) == mapping_digest(MESH_ID, 4, list(mapping))


def test_sub_grid_still_refused_after_the_boundary_fix():
    near = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1e-7, 0.0, 0.0))
    assert classify_duplicate_group_case(near, (0, 3)) == MERGE_CASE_SUB_GRID
    with pytest.raises(AuthorizationContractError) as excinfo:
        require_supported_case(near, ((0, 3),))
    assert excinfo.value.failure_code == AuthorizationFailureCode.SUB_GRID_COLLAPSE_UNSUPPORTED


def test_mapping_digest_value_is_unchanged_by_the_boundary_fix():
    """The digest is content-addressed: the known SHA-256 for the canonical mapping must not move."""
    mapping = make_index_mapping(4, _GROUP)
    assert mapping == (0, 1, 2, 0)
    assert mapping_digest(MESH_ID, 4, mapping) == hashlib.sha256(
        json.dumps(
            {"mesh_id": MESH_ID, "n": 4, "m": 3, "kept": [0, 1, 2], "sigma": [0, 1, 2, 0]},
            sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


# ===========================================================================
# G. AUTHORITY ISOLATION (AST scan, Wave-2 slice-1 pattern)
# ===========================================================================

_MODULE_PATH = "planning/blender/correction_authorization.py"
_FORBIDDEN_IMPORTS = {
    "bpy", "bpy_extras", "os", "subprocess", "shutil", "socket", "time", "random", "uuid",
    "secrets", "threading", "multiprocessing", "tempfile", "pathlib", "sys",
}
_FORBIDDEN_NAMES = {
    "save_as_mainfile", "save_mainfile", "wm", "rollback", "recover", "persist", "sqlite3",
    "subprocess", "Popen", "system", "execv", "spawn",
}


def _module_source():
    import planning.blender.correction_authorization as module

    with open(module.__file__, encoding="utf-8") as handle:
        return handle.read()


def test_module_imports_no_forbidden_modules():
    tree = ast.parse(_module_source())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
    assert not (imported & _FORBIDDEN_IMPORTS), sorted(imported & _FORBIDDEN_IMPORTS)


def test_module_contains_no_forbidden_authority_names():
    tree = ast.parse(_module_source())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
    assert not (found & _FORBIDDEN_NAMES), sorted(found & _FORBIDDEN_NAMES)


def test_no_bpy_token_outside_docstrings():
    source = _module_source()
    tree = ast.parse(source)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                docstrings.add(doc)
    stripped = source
    for doc in docstrings:
        stripped = stripped.replace(doc, "")
    assert "bpy" not in stripped


def test_contract_layer_has_no_top_level_execution():
    """Importing the module must not perform I/O, mutation or environment reads."""
    tree = ast.parse(_module_source())
    for node in tree.body:
        assert not isinstance(node, ast.Expr) or not isinstance(
            node.value, ast.Call
        ), "unexpected top-level call in the contract layer"
