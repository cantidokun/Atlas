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
        "autosave-twin", "reconstruction", (IdentityAnchor("source", "capture", "autosave"),)
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
    return ProductionOperationLifecycle(task, lambda evidence: evidence["task_id"] == task_id)


def test_store_backed_lifecycle_persists_checkpoint_after_each_completed_operation():
    registry, revision = _registry()
    store = InMemoryDurableProductionPersistenceStore()
    seed = DurableProductionOperationSequence(
        (_operation("task-1", revision, []), _operation("task-2", revision, [], converged=False))
    )
    store.save(DurableProductionPersistenceBundle.create(registry, seed.checkpoint))

    writes = []
    lifecycle = ProductionPersistenceResumeLifecycle.from_persistence_store(
        registry,
        (_operation("task-1", revision, writes), _operation("task-2", revision, writes, converged=False)),
        store,
    )

    result = lifecycle.run()

    assert result.state is ProductionOperationState.BLOCKED
    assert writes == ["task-1", "task-2"]
    persisted = store.load()
    assert persisted.checkpoint_snapshot["next_operation_index"] == 1
    assert len(persisted.checkpoint_snapshot["completed_receipts"]) == 1
    assert lifecycle.next_operation_index == 1


def test_store_backed_lifecycle_persists_blocked_checkpoint_without_promoting_operation():
    registry, revision = _registry()
    store = InMemoryDurableProductionPersistenceStore()
    seed = DurableProductionOperationSequence(
        (_operation("task-1", revision, [], converged=False),)
    )
    store.save(DurableProductionPersistenceBundle.create(registry, seed.checkpoint))

    writes = []
    lifecycle = ProductionPersistenceResumeLifecycle.from_persistence_store(
        registry,
        (_operation("task-1", revision, writes, converged=False),),
        store,
    )

    result = lifecycle.run()

    assert result.state is ProductionOperationState.BLOCKED
    assert writes == ["task-1"]
    persisted = store.load()
    assert persisted.checkpoint_snapshot["next_operation_index"] == 0
    assert persisted.checkpoint_snapshot["completed_receipts"] == ()
