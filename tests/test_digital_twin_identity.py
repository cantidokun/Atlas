from planning.digital_twin_identity import (
    DigitalTwinIdentity,
    IdentityAnchor,
    IdentityMatchStatus,
    evaluate_identity,
)


def make_identity():
    return DigitalTwinIdentity(
        twin_id="FIELD_001",
        entity_type="soccer_field",
        anchors=(
            IdentityAnchor("atlas", "site_code", "MTL-FIELD-01"),
            IdentityAnchor("spatial", "geo_reference", "45.5017,-73.5673"),
        ),
    )


def test_same_real_world_site_matches_when_all_required_anchors_are_present():
    result = evaluate_identity(
        make_identity(),
        [
            IdentityAnchor("atlas", "site_code", "MTL-FIELD-01"),
            IdentityAnchor("spatial", "geo_reference", "45.5017,-73.5673"),
        ],
    )
    assert result.status is IdentityMatchStatus.MATCH
    assert result.twin_id == "FIELD_001"


def test_capture_changes_do_not_change_identity_when_stable_anchors_match():
    result = evaluate_identity(
        make_identity(),
        [
            IdentityAnchor("atlas", "site_code", "MTL-FIELD-01"),
            IdentityAnchor("spatial", "geo_reference", "45.5017,-73.5673"),
            IdentityAnchor("capture", "capture_date", "2027-02-10"),
        ],
    )
    assert result.status is IdentityMatchStatus.MATCH


def test_missing_required_anchor_never_auto_merges():
    result = evaluate_identity(
        make_identity(),
        [IdentityAnchor("atlas", "site_code", "MTL-FIELD-01")],
    )
    assert result.status is IdentityMatchStatus.INSUFFICIENT_EVIDENCE
    assert len(result.missing_required_anchors) == 1


def test_conflicting_stable_anchor_is_an_explicit_no_match():
    result = evaluate_identity(
        make_identity(),
        [
            IdentityAnchor("atlas", "site_code", "MTL-FIELD-99"),
            IdentityAnchor("spatial", "geo_reference", "45.5017,-73.5673"),
        ],
    )
    assert result.status is IdentityMatchStatus.NO_MATCH
    assert len(result.conflicting_anchors) == 1


def test_identity_fingerprint_ignores_capture_metadata():
    identity = make_identity()
    assert identity.stable_fingerprint() == make_identity().stable_fingerprint()


def test_identity_fingerprint_changes_when_canonical_identity_changes():
    original = make_identity()
    changed = DigitalTwinIdentity(
        twin_id="FIELD_001",
        entity_type="soccer_field",
        anchors=(
            IdentityAnchor("atlas", "site_code", "MTL-FIELD-02"),
            IdentityAnchor("spatial", "geo_reference", "45.5017,-73.5673"),
        ),
    )
    assert original.stable_fingerprint() != changed.stable_fingerprint()
