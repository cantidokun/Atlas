import copy

import pytest

from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import RevisionKind, create_revision


def _identity(twin_id="twin-1"):
    return DigitalTwinIdentity(
        twin_id=twin_id,
        entity_type="soccer_field",
        anchors=(
            IdentityAnchor("venue", "name", "Field A"),
            IdentityAnchor("venue", "city", "Montreal"),
        ),
    )


def _registry():
    registry = DigitalTwinRegistry()
    identity = _identity()
    registry.register_identity(identity)
    revision = create_revision(identity, "r1", 1, RevisionKind.RECONSTRUCTION)
    registry.register_revision(revision)
    return registry


def test_registry_snapshot_round_trips_canonical_identity_and_revisions():
    original = _registry()
    restored = DigitalTwinRegistry.from_snapshot(original.snapshot())

    assert restored._identities["twin-1"].stable_fingerprint() == original._identities["twin-1"].stable_fingerprint()
    assert restored.revisions("twin-1") == original.revisions("twin-1")
    assert restored.snapshot() == original.snapshot()


def test_registry_rejects_tampered_snapshot_before_rehydration():
    snapshot = _registry().snapshot()
    tampered = copy.deepcopy(snapshot)
    tampered["revisions"]["twin-1"][0]["revision_id"] = "r-tampered"

    with pytest.raises(ValueError, match="digest"):
        DigitalTwinRegistry.from_snapshot(tampered)


def test_registry_rejects_revision_for_unknown_twin_even_with_valid_snapshot_digest():
    snapshot = _registry().snapshot()
    snapshot["revisions"]["unknown"] = []
    from planning.digital_twin_registry import _digest
    snapshot["snapshot_digest"] = _digest({"identities": snapshot["identities"], "revisions": snapshot["revisions"]})

    with pytest.raises(ValueError, match="unregistered Digital Twin"):
        DigitalTwinRegistry.from_snapshot(snapshot)
