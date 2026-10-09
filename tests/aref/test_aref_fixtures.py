"""A-REF fixture-validator tests (R4F sections 8.2, 25; criteria G41/G48/G53)."""

import copy

import pytest

from tests.aref.aref_fixture import FixtureError, validate_authorization_fixture, validate_fixture
from tests.aref.fixtures import SPECS, load_case

GOOD_AUTH = {
    "authorization_version": "1",
    "authorization_policy_version": "1",
    "decision": "APPROVED",
    "correction_type": "REPAIR_FACE_WINDING",
    "correction_id": "mesh.duplicate_face-atlas-target-01234567",
    "plan_id": "a" * 64,
    "source_report_digest": "b" * 64,
    "authorized_by": "AREF-TEST-fixture",
    "authorized_at_utc": "2026-10-08T00:00:00Z",
}


def test_all_catalog_cases_validate():
    for fixture_id in SPECS:
        spec = load_case(fixture_id)
        assert spec.fixture_id == fixture_id
        assert spec.expected["oc_class"].startswith("OC")
        assert spec.expected["disposition"] in (
            "POSITIVELY_DEMONSTRATED", "NOT_APPLICABLE")


def test_fixture_id_marker_required():
    spec = copy.deepcopy(SPECS["AREF-TEST-FX-C1-PAIR"])
    spec["fixture_id"] = "FX-C1-PAIR"  # no harness marker
    spec["expected"] = load_case("AREF-TEST-FX-C1-PAIR").expected
    with pytest.raises(FixtureError, match="marker"):
        validate_fixture(spec)


def test_plan_id_marker_forbidden_and_hex_required():
    with pytest.raises(FixtureError, match="must not be prefixed"):
        validate_authorization_fixture({**GOOD_AUTH, "plan_id": "AREF-TEST-plan"}, case_requires_auth=True)
    with pytest.raises(FixtureError, match="64 lowercase hex"):
        validate_authorization_fixture({**GOOD_AUTH, "plan_id": "XYZ"}, case_requires_auth=True)


def test_correction_id_marker_forbidden_and_format_required():
    with pytest.raises(FixtureError, match="must not be prefixed"):
        validate_authorization_fixture(
            {**GOOD_AUTH, "correction_id": "AREF-TEST-correct"}, case_requires_auth=True)
    with pytest.raises(FixtureError, match="planner-derived"):
        validate_authorization_fixture({**GOOD_AUTH, "correction_id": "not-a-planner-id"}, case_requires_auth=True)


def test_authorized_by_marker_required_when_auth_declared():
    with pytest.raises(FixtureError, match="must carry the AREF-TEST- marker"):
        validate_authorization_fixture({**GOOD_AUTH, "authorized_by": "operator"}, case_requires_auth=True)


def test_null_authorization_is_permitted():
    assert validate_authorization_fixture(None, case_requires_auth=True) is None


def test_unknown_authorization_field_rejected():
    with pytest.raises(FixtureError, match="unknown field"):
        validate_authorization_fixture({**GOOD_AUTH, "signed": True}, case_requires_auth=True)


def test_scope_note_may_carry_marker_and_stays_free_text():
    auth = validate_authorization_fixture({**GOOD_AUTH, "scope_note": "AREF-TEST-note"}, case_requires_auth=True)
    assert auth["scope_note"] == "AREF-TEST-note"


def test_object_name_rules():
    spec = copy.deepcopy(SPECS["AREF-TEST-FX-C1-PAIR"])
    spec["objects"][0]["object_id"] = "AtlasTarget"  # uppercase violates the profile pattern
    spec["expected"] = load_case("AREF-TEST-FX-C1-PAIR").expected
    with pytest.raises(FixtureError, match="name pattern"):
        validate_fixture(spec)


def test_duplicate_object_names_rejected():
    spec = copy.deepcopy(SPECS["AREF-TEST-FX-AL-C1"])
    spec["objects"][1]["object_id"] = "atlas-target"  # duplicate name is an invalid fixture
    spec["expected"] = load_case("AREF-TEST-FX-AL-C1").expected
    spec["sharing"] = {"DB1": ["atlas-target", "atlas-target"]}
    with pytest.raises(FixtureError):
        validate_fixture(spec)


def test_numeric_rules_negative_zero_and_nonfinite():
    spec = copy.deepcopy(SPECS["AREF-TEST-FX-C1-PAIR"])
    spec["expected"] = load_case("AREF-TEST-FX-C1-PAIR").expected
    bad = copy.deepcopy(spec)
    bad["datablocks"][0]["vertices"] = [list(v) for v in spec["datablocks"][0]["vertices"]]
    bad["datablocks"][0]["vertices"][0] = [-0.0, 0.0, 0.0]
    with pytest.raises(FixtureError, match="negative zero"):
        validate_fixture(bad)
    bad2 = copy.deepcopy(spec)
    bad2["datablocks"][0]["vertices"] = [list(v) for v in spec["datablocks"][0]["vertices"]]
    bad2["datablocks"][0]["vertices"][0] = [float("nan"), 0.0, 0.0]
    with pytest.raises(FixtureError, match="non-finite"):
        validate_fixture(bad2)


def test_numeric_rules_float32_and_six_decimals():
    spec = copy.deepcopy(SPECS["AREF-TEST-FX-C1-PAIR"])
    spec["expected"] = load_case("AREF-TEST-FX-C1-PAIR").expected
    bad = copy.deepcopy(spec)
    bad["datablocks"][0]["vertices"] = [list(v) for v in spec["datablocks"][0]["vertices"]]
    bad["datablocks"][0]["vertices"][0] = [0.1234567, 0.0, 0.0]  # not 6-decimal idempotent
    with pytest.raises(FixtureError, match="six-decimal"):
        validate_fixture(bad)
    bad2 = copy.deepcopy(spec)
    bad2["datablocks"][0]["vertices"] = [list(v) for v in spec["datablocks"][0]["vertices"]]
    bad2["datablocks"][0]["vertices"][0] = [16777217.0, 0.0, 0.0]  # 2^24+1: passes six-decimal, lossy in float32
    with pytest.raises(FixtureError, match="float32"):
        validate_fixture(bad2)


def test_face_index_bool_rejected():
    spec = copy.deepcopy(SPECS["AREF-TEST-FX-C1-PAIR"])
    spec["expected"] = load_case("AREF-TEST-FX-C1-PAIR").expected
    spec["datablocks"][0]["faces"] = [list(f) for f in spec["datablocks"][0]["faces"]]
    spec["datablocks"][0]["faces"][0][0] = True
    with pytest.raises(FixtureError, match="exact ints"):
        validate_fixture(spec)


def test_repoint_requires_p1_and_pair_shape():
    spec = copy.deepcopy(SPECS["AREF-TEST-FX-C1-REVERSED"])
    spec["expected"] = load_case("AREF-TEST-FX-C1-REVERSED").expected
    spec["plan_construction"] = {"rule": "P2", "selected_pair": [0, 2], "repoint": {"face_ids": [2, 0]}}
    with pytest.raises(FixtureError, match="repoint"):
        validate_fixture(spec)


def test_sharing_must_match_references():
    spec = copy.deepcopy(SPECS["AREF-TEST-FX-AL-C1"])
    spec["expected"] = load_case("AREF-TEST-FX-AL-C1").expected
    spec["sharing"] = {"DB1": ["atlas-target"]}  # missing atlas-unrelated
    with pytest.raises(FixtureError, match="sharing"):
        validate_fixture(spec)


def test_witness_order_must_be_name_sorted():
    spec = copy.deepcopy(SPECS["AREF-TEST-FX-AL-C1"])
    spec["expected"] = copy.deepcopy(load_case("AREF-TEST-FX-AL-C1").expected)
    spec["expected"]["graph_witness"]["order"] = ["atlas-unrelated", "atlas-target"]
    with pytest.raises(FixtureError, match="order"):
        validate_fixture(spec)


def test_field_binding_map_is_closed_and_complete():
    from tests.aref.aref_fixture import (BINDING_CLASSES, FIELD_BINDING_CLASSES,
                                         digest_bound_fields, validate_binding_map)

    m = validate_binding_map()
    assert m == FIELD_BINDING_CLASSES and len(m) >= 36
    assert set(m.values()) <= BINDING_CLASSES
    # the digest actually binds the fields the map calls digest-bound (spot inventory: identity,
    # coordinates, tables, mesh_id)
    for f in ("object_id", "name", "location", "rotation", "scale", "visible", "vertices",
              "faces", "mesh_id", "scene_id", "unit_system"):
        assert f in digest_bound_fields(), f
    with pytest.raises(FixtureError):
        validate_binding_map({"faces": "BIND-BY-VIBES"})
    assert {"world_bounds", "normals", "uvs", "local_frame_id"} <= set(m)  # DECLARED-ABSENT set


def _merged_raw(fixture_id):
    from tests.aref.aref_harness import load_expected

    raw = copy.deepcopy(SPECS[fixture_id])
    raw["expected"] = load_expected(fixture_id)["expected"]  # same merge load_case applies
    return raw


def test_material_slots_validation():
    good = _merged_raw("AREF-TEST-FX-C1-PAIR")
    good["objects"][0]["material_slots"] = [["DATA", "bayside"]]
    validate_fixture(good)  # accepted: link + pattern-valid name
    bad = _merged_raw("AREF-TEST-FX-C1-PAIR")
    bad["objects"][0]["material_slots"] = [["SIDEWAYS", None]]
    with pytest.raises(FixtureError, match="link"):
        validate_fixture(bad)
    bad2 = _merged_raw("AREF-TEST-FX-C1-PAIR")
    bad2["objects"][0]["material_slots"] = [["OBJECT", "Bad Name"]]
    with pytest.raises(FixtureError, match="pattern-valid"):
        validate_fixture(bad2)
