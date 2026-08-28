from __future__ import annotations

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_operation_sequence import DurableProductionOperationSequence
from planning.durable_production_persistence import DurableProductionPersistenceBundle
from planning.durable_production_sequence_rehydration import DurableProductionSequenceRehydrator
from planning.in_memory_durable_production_persistence_store import (
    InMemoryDurableProductionPersistenceStore,
)
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.production_operation_lifecycle import ProductionOperationLifecycle, ProductionOperationState
from planning.production_task_checkpoint import ProductionTaskCheckpoint


def _registry():
    identity = DigitalTwinIdentity(
        "persist-restart-twin",
        "reconstruction",
        (IdentityAnchor("source", "capture", "persist-restart"),),
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


def _operation(task_id, revision, writes, converged):
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


def test_persisted_restart_resumes_only_unfinished_operation():
    registry, revision = _registry()
    writes = []
    first = _operation("task-1", revision, writes, True)
    second = _operation("task-2", revision, writes, False)

    interrupted = DurableProductionOperationSequence((first, second)).run()
    assert interrupted.state is ProductionOperationState.BLOCKED
    assert interrupted.checkpoint.next_operation_index == 1
    assert writes == ["task-1", "task-2"]

    store = InMemoryDurableProductionPersistenceStore()
    store.save(DurableProductionPersistenceBundle.create(registry, interrupted.checkpoint))

    # Simulate a process boundary: construct fresh operations and load only
    # the validated persisted bundle. The completed operation must not execute again.
    resumed_writes = []
    resumed_operations = (
        _operation("task-1", revision, resumed_writes, True),
        _operation("task-2", revision, resumed_writes, True),
    )
    persisted = store.load()
    restored = DurableProductionSequenceRehydrator(registry).rehydrate(
        resumed_operations, persisted
    )

    result = restored.run()

    assert result.state is ProductionOperationState.COMPLETED
    assert resumed_writes == ["task-2"]
    assert result.checkpoint.next_operation_index == 2
    assert [receipt["task_id"] for receipt in result.checkpoint.completed_receipts] == [
        "task-1",
        "task-2",
    ]
