from __future__ import annotations

import pytest

from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_operation_sequence import DurableProductionSequenceCheckpoint
from planning.durable_production_persistence import DurableProductionPersistenceBundle
from planning.durable_production_sequence_rehydration import DurableProductionSequenceRehydrator
from planning.in_memory_durable_production_persistence_store import (
    InMemoryDurableProductionPersistenceStore,
)


def _registry_and_checkpoint():
    identity = DigitalTwinIdentity(
        "rehydrate-persist-twin",
        "reconstruction",
        (IdentityAnchor("source", "capture", "persist"),),
    )
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = DigitalTwinRevision(
        identity.twin_id,
        "r1",
        1,
        RevisionKind.RECONSTRUCTION,
        source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(revision)
    return registry, DurableProductionSequenceCheckpoint.create((), 0)


def test_rehydrator_accepts_valid_persistence_bundle():
    registry, checkpoint = _registry_and_checkpoint()
    bundle = DurableProductionPersistenceBundle.create(registry, checkpoint)
    result = DurableProductionSequenceRehydrator(registry).rehydrate((), bundle)
    assert result.checkpoint.snapshot() == checkpoint.snapshot()


def test_rehydrator_accepts_bundle_loaded_from_persistence_store():
    registry, checkpoint = _registry_and_checkpoint()
    store = InMemoryDurableProductionPersistenceStore()
    store.save(DurableProductionPersistenceBundle.create(registry, checkpoint))
    result = DurableProductionSequenceRehydrator(registry).rehydrate((), store.load())
    assert result.checkpoint.snapshot() == checkpoint.snapshot()


def test_rehydrator_revalidates_mutated_bundle_snapshots():
    registry, checkpoint = _registry_and_checkpoint()
    bundle = DurableProductionPersistenceBundle.create(registry, checkpoint)
    bundle.registry_snapshot["snapshot_digest"] = "tampered"

    with pytest.raises(ValueError, match="registry snapshot digest"):
        DurableProductionSequenceRehydrator(registry).rehydrate((), bundle)


def test_rehydrator_rejects_checkpoint_argument_with_bundle():
    registry, checkpoint = _registry_and_checkpoint()
    bundle = DurableProductionPersistenceBundle.create(registry, checkpoint)
    with pytest.raises(TypeError, match="checkpoint snapshot must be omitted"):
        DurableProductionSequenceRehydrator(registry).rehydrate((), bundle, {})
