from __future__ import annotations

import pytest

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_operation_sequence import DurableProductionSequenceCheckpoint
from planning.durable_production_persistence import DurableProductionPersistenceBundle
from planning.durable_production_sequence_rehydration import DurableProductionSequenceRehydrator
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.in_memory_durable_production_persistence_store import (
    InMemoryDurableProductionPersistenceStore,
)
from planning.production_operation_lifecycle import ProductionOperationLifecycle
from planning.production_task_checkpoint import ProductionTaskCheckpoint


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
    return registry, revision, DurableProductionSequenceCheckpoint.create((), 0)


def _operation(task_id, revision):
    checkpoint = ProductionTaskCheckpoint.create(
        task_id, revision, (), {"task_id": task_id}, f"auth-{task_id}"
    )
    task = object.__new__(DurableResumableCorrectiveTask)
    task.checkpoint = checkpoint
    task.revision = revision

    def resume(max_steps=16):
        return CorrectiveTaskResult((), {"task_id": task_id}, True)

    task.resume = resume
    return ProductionOperationLifecycle(task, lambda _evidence: True)


def test_rehydrator_accepts_valid_persistence_bundle():
    registry, revision, checkpoint = _registry_and_checkpoint()
    bundle = DurableProductionPersistenceBundle.create(registry, checkpoint)
    result = DurableProductionSequenceRehydrator(registry).rehydrate(
        (_operation("task-1", revision),), bundle
    )
    assert result.checkpoint.snapshot() == checkpoint.snapshot()


def test_rehydrator_accepts_bundle_loaded_from_persistence_store():
    registry, revision, checkpoint = _registry_and_checkpoint()
    store = InMemoryDurableProductionPersistenceStore()
    store.save(DurableProductionPersistenceBundle.create(registry, checkpoint))
    result = DurableProductionSequenceRehydrator(registry).rehydrate(
        (_operation("task-1", revision),), store.load()
    )
    assert result.checkpoint.snapshot() == checkpoint.snapshot()


def test_rehydrator_revalidates_mutated_bundle_snapshots():
    registry, _, checkpoint = _registry_and_checkpoint()
    bundle = DurableProductionPersistenceBundle.create(registry, checkpoint)
    bundle.registry_snapshot["snapshot_digest"] = "tampered"

    with pytest.raises(ValueError, match="registry snapshot digest"):
        DurableProductionSequenceRehydrator(registry).rehydrate(
            (), bundle
        )


def test_rehydrator_rejects_checkpoint_argument_with_bundle():
    registry, _, checkpoint = _registry_and_checkpoint()
    bundle = DurableProductionPersistenceBundle.create(registry, checkpoint)
    with pytest.raises(TypeError, match="checkpoint snapshot must be omitted"):
        DurableProductionSequenceRehydrator(registry).rehydrate((), bundle, {})
