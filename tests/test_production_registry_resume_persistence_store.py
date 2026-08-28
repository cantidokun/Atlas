from __future__ import annotations

import pytest

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_operation_sequence import DurableProductionOperationSequence
from planning.durable_production_persistence import DurableProductionPersistenceBundle
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.in_memory_durable_production_persistence_store import InMemoryDurableProductionPersistenceStore
from planning.production_operation_lifecycle import ProductionOperationLifecycle, ProductionOperationState
from planning.production_registry_resume_lifecycle import ProductionRegistryResumeLifecycle
from planning.production_task_checkpoint import ProductionTaskCheckpoint


def _registry():
    identity = DigitalTwinIdentity(
        "resume-store-twin", "reconstruction", (IdentityAnchor("source", "capture", "store"),)
    )
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = DigitalTwinRevision(
        identity.twin_id, "r1", 1, RevisionKind.RECONSTRUCTION,
        source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(revision)
    return registry, revision


def _operation(task_id, revision, writes, converged=True):
    checkpoint = ProductionTaskCheckpoint.create(
        task_id, revision, (), {"task_id": task_id}, f"auth-{task_id}"
    )
    task = object.__new__(DurableResumableCorrectiveTask)
    task.checkpoint = checkpoint
    task.revision = revision

    def resume(max_steps=16):
        writes.append(task_id)
        return CorrectiveTaskResult((), {"task_id": task_id}, converged)

    task.resume = resume
    return ProductionOperationLifecycle(task, lambda _evidence: True)


def test_store_backed_resume_lifecycle_round_trips_persisted_checkpoint():
    registry, revision = _registry()
    writes = []
    interrupted = DurableProductionOperationSequence(
        (_operation("task-1", revision, writes), _operation("task-2", revision, writes, converged=False))
    ).run()

    store = InMemoryDurableProductionPersistenceStore()
    store.save(DurableProductionPersistenceBundle.create(registry, interrupted.checkpoint))
    bundle = store.load()

    resumed_writes = []
    lifecycle = ProductionRegistryResumeLifecycle.from_registry_snapshot(
        bundle.registry_snapshot,
        bundle.checkpoint_snapshot,
        revision,
        observe=lambda: {"task": "task-2"},
        plan=lambda _evidence: (),
        verify_final=lambda _evidence: True,
        executor=None,
    )
    lifecycle.task.resume = lambda max_steps=16: CorrectiveTaskResult(
        (), {"task": "task-2"}, True
    )

    result = lifecycle.run()

    assert result.state is ProductionOperationState.COMPLETED
    assert result.receipt is not None
    assert lifecycle.checkpoint.revision_id == revision.revision_id


def test_store_backed_resume_rejects_tampered_checkpoint_before_execution():
    registry, revision = _registry()
    checkpoint = DurableProductionSequenceOperationSequence((
        _operation("task-1", revision, []),
    )).checkpoint if False else DurableProductionOperationSequence((_operation("task-1", revision, []) ,)).checkpoint
    bundle = DurableProductionPersistenceBundle.create(registry, checkpoint)
    store = InMemoryDurableProductionPersistenceStore()
    store.save(bundle)
    persisted = dict(store.snapshot())
    persisted["checkpoint_snapshot"] = dict(persisted["checkpoint_snapshot"])
    persisted["checkpoint_snapshot"]["sequence_digest"] = "tampered"
    store._snapshot = persisted

    with pytest.raises(ValueError, match="integrity failure"):
        bundle = store.load()
