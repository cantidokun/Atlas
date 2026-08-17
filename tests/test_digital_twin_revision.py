import pytest

from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_revision import (
    DigitalTwinRevision,
    RepresentationKind,
    RevisionKind,
    create_representation,
    create_revision,
    next_revision_sequence,
)


def identity():
    return DigitalTwinIdentity(
        twin_id="field-001",
        entity_type="soccer_field",
        anchors=(
            IdentityAnchor("site", "site_id", "stadium-a"),
            IdentityAnchor("survey", "coordinate_frame", "local-v1"),
        ),
    )


def test_first_revision_is_canonical_sequence_one():
    revision = create_revision(identity(), "field-001-r1", 1, RevisionKind.RECONSTRUCTION)
    assert revision.twin_id == "field-001"
    assert revision.sequence == 1
    assert revision.source_revision_id is None
    assert revision.source_fingerprint == identity().stable_fingerprint()


def test_revision_preserves_twin_ownership():
    first = create_revision(identity(), "field-001-r1", 1, RevisionKind.RECONSTRUCTION)
    second = create_revision(identity(), "field-001-r2", 2, RevisionKind.CLEANUP, first)
    assert second.twin_id == first.twin_id
    assert second.source_revision_id == first.revision_id


def test_cross_twin_revision_source_is_rejected():
    first = create_revision(identity(), "field-001-r1", 1, RevisionKind.RECONSTRUCTION)
    other = DigitalTwinIdentity("field-002", "soccer_field", identity().anchors)
    with pytest.raises(ValueError, match="different Digital Twin"):
        create_revision(other, "field-002-r2", 2, RevisionKind.CLEANUP, first)


def test_representation_is_derived_from_revision_and_not_canonical():
    revision = create_revision(identity(), "field-001-r1", 1, RevisionKind.OPTIMIZATION)
    representation = create_representation(
        identity(),
        "field-001-blender-r1",
        RepresentationKind.BLENDER,
        revision,
        "Blender 4.4",
    )
    assert representation.twin_id == "field-001"
    assert representation.source_revision_id == revision.revision_id
    assert representation.canonical is False


def test_representation_cannot_cross_twin_boundaries():
    revision = create_revision(identity(), "field-001-r1", 1, RevisionKind.RECONSTRUCTION)
    other = DigitalTwinIdentity("field-002", "soccer_field", identity().anchors)
    with pytest.raises(ValueError, match="different Digital Twin"):
        create_representation(
            other,
            "field-002-blender-r1",
            RepresentationKind.BLENDER,
            revision,
            "Blender 4.4",
        )


def test_next_revision_sequence_is_monotonic():
    revisions = (
        create_revision(identity(), "field-001-r1", 1, RevisionKind.RECONSTRUCTION),
        create_revision(identity(), "field-001-r2", 2, RevisionKind.CLEANUP),
    )
    assert next_revision_sequence(revisions) == 3
    assert next_revision_sequence(()) == 1


def test_empty_production_tool_is_rejected():
    revision = create_revision(identity(), "field-001-r1", 1, RevisionKind.RECONSTRUCTION)
    with pytest.raises(ValueError, match="production_tool"):
        create_representation(
            identity(),
            "field-001-empty-tool",
            RepresentationKind.OTHER,
            revision,
            "   ",
        )
