from __future__ import annotations

import pytest

from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_operation_sequence import DurableProductionSequenceCheckpoint
from planning.durable_production_persistence import DurableProductionPersistenceBundle
from planning.in_memory_durable_production_persistence_store import (
    InMemoryDurableProductionPersistenceStore,
)


def _bundle():
    identity = DigitalTwinIdentity(
        "store-twin", "reconstruction", (IdentityAnchor("source", "capture", "store"),)
    )
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = DigitalTwinRevision(
        identity.twin_id, "r1", 1, RevisionKind.RECONSTRUCTION,
        source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(revision)
    checkpoint = DurableProductionSequenceCheckpoint.create((), 0)
    return DurableProductionPersistenceBundle.create(registry, checkpoint)


def test_load_rejects_when_store_has_no_state():
    with pytest.raises(ValueError, match="no durable production persistence state"):
        InMemoryDurableProductionPersistenceStore().load()


def test_valid_save_load_round_trips():
    store = InMemoryDurableProductionPersistenceStore()
    bundle = _bundle()
    store.save(bundle)
    assert store.load().snapshot() == bundle.snapshot()


def test_invalid_save_does_not_replace_last_known_good_state():
    store = InMemoryDurableProductionPersistenceStore()
    good = _bundle()
    store.save(good)

    tampered = good.snapshot()
    tampered["checkpoint_snapshot"] = dict(tampered["checkpoint_snapshot"])
    tampered["checkpoint_snapshot"]["sequence_digest"] = "tampered"
    invalid = DurableProductionPersistenceBundle(
        tampered["registry_snapshot"], tampered["checkpoint_snapshot"]
    )
    with pytest.raises(ValueError, match="integrity failure"):
        store.save(invalid)
    assert store.load().snapshot() == good.snapshot()


def test_tampered_persisted_state_is_rejected_on_load():
    store = InMemoryDurableProductionPersistenceStore()
    store.save(_bundle())
    persisted = dict(store.snapshot())
    persisted["registry_snapshot"] = dict(persisted["registry_snapshot"])
    persisted["registry_snapshot"]["snapshot_digest"] = "tampered"

    # Simulate storage corruption without going through save(), which validates input.
    store._snapshot = persisted
    with pytest.raises(ValueError, match="registry snapshot digest"):
        store.load()


def test_tampered_persisted_state_is_rejected_at_snapshot_boundary():
    store = InMemoryDurableProductionPersistenceStore()
    store.save(_bundle())
    persisted = dict(store.snapshot())
    persisted["checkpoint_snapshot"] = dict(persisted["checkpoint_snapshot"])
    persisted["checkpoint_snapshot"]["sequence_digest"] = "tampered"

    # Simulate storage corruption without going through save(), which validates input.
    store._snapshot = persisted
    with pytest.raises(ValueError, match="sequence checkpoint digest"):
        store.snapshot()
