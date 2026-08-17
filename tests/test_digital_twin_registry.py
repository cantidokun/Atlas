import pytest

from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import RevisionKind, create_revision


def make_identity(twin_id="field-001"):
    return DigitalTwinIdentity(
        twin_id=twin_id,
        entity_type="soccer_field",
        anchors=(IdentityAnchor("site", "site_id", "stadium-a"),),
    )


def test_registry_requires_identity_before_revision():
    registry = DigitalTwinRegistry()
    revision = create_revision(make_identity(), "field-001-r1", 1, RevisionKind.RECONSTRUCTION)
    with pytest.raises(ValueError, match="registered first"):
        registry.register_revision(revision)


def test_registry_accepts_sequential_canonical_revisions():
    identity = make_identity()
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)

    first = create_revision(identity, "field-001-r1", 1, RevisionKind.RECONSTRUCTION)
    second = create_revision(identity, "field-001-r2", 2, RevisionKind.CLEANUP, first)
    registry.register_revision(first)
    registry.register_revision(second)

    assert [revision.revision_id for revision in registry.revisions("field-001")] == [
        "field-001-r1",
        "field-001-r2",
    ]


def test_registry_rejects_revision_sequence_gaps():
    identity = make_identity()
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = create_revision(identity, "field-001-r2", 2, RevisionKind.CLEANUP)
    with pytest.raises(ValueError, match="revision sequence must be 1"):
        registry.register_revision(revision)


def test_registry_refuses_identity_replacement():
    registry = DigitalTwinRegistry()
    registry.register_identity(make_identity())
    conflicting = DigitalTwinIdentity(
        twin_id="field-001",
        entity_type="soccer_field",
        anchors=(IdentityAnchor("site", "site_id", "stadium-b"),),
    )
    with pytest.raises(ValueError, match="cannot be silently replaced"):
        registry.register_identity(conflicting)
