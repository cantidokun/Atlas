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
from planning.production_persistence_resume_lifecycle import ProductionPersistenceResumeLifecycle
from planning.production_task_checkpoint import ProductionTaskCheckpoint


def _registry():
    identity = DigitalTwinIdentity(
        "persistence-integrity-twin",
        "reconstruction",
        (IdentityAnchor("source", "capture", "integrity"),),
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


def _interrupted_bundle(registry, revision):
    writes = []
    result = DurableProductionOperationSequence(
        (
            _operation("task-1", revision, writes, converged=True),
            _operation("task-2", revision, writes, converged=False),
        )
    ).run()
    return DurableProductionPersistenceBundle.create(registry, result.checkpoint)


def test_persistence_resume_lifecycle_rejects_tampered_bundle_before_any_resume_write():
    registry, revision = _registry()
    bundle = _interrupted_bundle(registry, revision)
    bundle.registry_snapshot["snapshot_digest"] = "tampered"
    writes = []

    with pytest.raises(ValueError, match="registry snapshot digest"):
        ProductionPersistenceResumeLifecycle.from_bundle(
            registry,
            (_operation("task-1", revision, writes), _operation("task-2", revision, writes)),
            bundle,
        )

    assert writes == []


def test_persistence_resume_lifecycle_rejects_stale_registry_before_any_resume_write():
    registry, revision = _registry()
    store = InMemoryDurableProductionPersistenceStore()
    store.save(_interrupted_bundle(registry, revision))

    registry.register_revision(
        DigitalTwinRevision(
            revision.twin_id,
            "r2",
            2,
            RevisionKind.CLEANUP,
            source_revision_id=revision.revision_id,
            source_fingerprint=revision.source_fingerprint,
        )
    )

    writes = []
    with pytest.raises(ValueError, match="stale Digital Twin revision"):
        ProductionPersistenceResumeLifecycle.from_persistence_store(
            registry,
            (_operation("task-1", revision, writes), _operation("task-2", revision, writes)),
            store,
        )

    assert writes == []


def test_completed_persistence_resume_is_idempotent_and_does_not_write():
    registry, revision = _registry()
    writes = []
    completed = DurableProductionOperationSequence(
        (
            _operation("task-1", revision, writes),
            _operation("task-2", revision, writes),
        )
    ).run()
    bundle = DurableProductionPersistenceBundle.create(registry, completed.checkpoint)
    resumed_writes = []

    lifecycle = ProductionPersistenceResumeLifecycle.from_bundle(
        registry,
        (
            _operation("task-1", revision, resumed_writes),
            _operation("task-2", revision, resumed_writes),
        ),
        bundle,
    )
    result = lifecycle.run()

    assert result.state is ProductionOperationState.COMPLETED
    assert result.results == ()
    assert lifecycle.next_operation_index == 2
    assert resumed_writes == []
