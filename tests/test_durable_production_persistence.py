from __future__ import annotations

import pytest

from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_operation_sequence import DurableProductionSequenceCheckpoint
from planning.durable_production_persistence import DurableProductionPersistenceBundle


def _state():
    identity = DigitalTwinIdentity(
        "persist-twin", "reconstruction", (IdentityAnchor("source", "capture", "persist"),)
    )
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = DigitalTwinRevision(
        identity.twin_id, "r1", 1, RevisionKind.RECONSTRUCTION,
        source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(revision)
    checkpoint = DurableProductionSequenceCheckpoint.create((), 0)
    return registry, checkpoint


def test_persistence_bundle_round_trips_valid_registry_and_checkpoint():
    registry, checkpoint = _state()
    bundle = DurableProductionPersistenceBundle.create(registry, checkpoint)
    restored = DurableProductionPersistenceBundle.from_snapshot(bundle.snapshot())
    assert restored.snapshot() == bundle.snapshot()


def test_persistence_bundle_rejects_tampered_registry_snapshot():
    registry, checkpoint = _state()
    snapshot = DurableProductionPersistenceBundle.create(registry, checkpoint).snapshot()
    snapshot["registry_snapshot"] = dict(snapshot["registry_snapshot"])
    snapshot["registry_snapshot"]["snapshot_digest"] = "tampered"
    with pytest.raises(ValueError, match="registry snapshot digest"):
        DurableProductionPersistenceBundle.from_snapshot(snapshot)


def test_persistence_bundle_rejects_tampered_checkpoint():
    registry, checkpoint = _state()
    snapshot = DurableProductionPersistenceBundle.create(registry, checkpoint).snapshot()
    snapshot["checkpoint_snapshot"] = dict(snapshot["checkpoint_snapshot"])
    snapshot["checkpoint_snapshot"]["sequence_digest"] = "tampered"
    with pytest.raises(ValueError, match="integrity failure"):
        DurableProductionPersistenceBundle.from_snapshot(snapshot)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.pop("registry_snapshot"),
        lambda value: value.__setitem__("extra", True),
    ],
)
def test_persistence_bundle_rejects_invalid_top_level_shape(mutation):
    registry, checkpoint = _state()
    snapshot = DurableProductionPersistenceBundle.create(registry, checkpoint).snapshot()
    mutation(snapshot)
    with pytest.raises(ValueError, match="invalid durable production persistence bundle"):
        DurableProductionPersistenceBundle.from_snapshot(snapshot)
