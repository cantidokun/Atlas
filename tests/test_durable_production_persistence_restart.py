from __future__ import annotations

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_operation_sequence import DurableProductionOperationSequence
from planning.durable_production_persistence import DurableProductionPersistenceBundle
from planning.durable_production_sequence_rehydration import DurableProductionSequenceRehydrator
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.in_memory_durable_production_persistence_store import InMemoryDurableProductionPersistenceStore
from planning.production_operation_lifecycle import ProductionOperationLifecycle, ProductionOperationState
from planning.production_task_checkpoint import ProductionTaskCheckpoint


def _registry():
    identity = DigitalTwinIdentity(
        "persistence-restart-twin",
        "reconstruction",
        (IdentityAnchor("source", "capture", "persistence-restart"),),
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


def test_store_bundle_restart_resumes_only_unfinished_operation():
    registry, revision = _registry()
    first_writes = []
    interrupted = DurableProductionOperationSequence(
        (
            _operation("task-1", revision, first_writes, converged=True),
            _operation("task-2", revision, first_writes, converged=False),
        )
    ).run()

    assert interrupted.state is ProductionOperationState.BLOCKED
    store = InMemoryDurableProductionPersistenceStore()
    store.save(DurableProductionPersistenceBundle.create(registry, interrupted.checkpoint))

    resumed_writes = []
    restored = DurableProductionSequenceRehydrator(registry).rehydrate(
        (
            _operation("task-1", revision, resumed_writes),
            _operation("task-2", revision, resumed_writes, converged=True),
        ),
        store.load(),
    )

    result = restored.run()

    assert result.state is ProductionOperationState.COMPLETED
    assert resumed_writes == ["task-2"]
    assert result.checkpoint.next_operation_index == 2


def test_store_bundle_restart_refuses_newer_canonical_revision_before_write():
    registry, revision = _registry()
    writes = []
    interrupted = DurableProductionOperationSequence(
        (
            _operation("task-1", revision, writes),
            _operation("task-2", revision, writes, converged=False),
        )
    ).run()
    store = InMemoryDurableProductionPersistenceStore()
    store.save(DurableProductionPersistenceBundle.create(registry, interrupted.checkpoint))

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

    resumed_writes = []
    with __import__("pytest").raises(ValueError, match="stale Digital Twin revision"):
        DurableProductionSequenceRehydrator(registry).rehydrate(
            (
                _operation("task-1", revision, resumed_writes),
                _operation("task-2", revision, resumed_writes),
            ),
            store.load(),
        )

    assert resumed_writes == []
