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
        "completion-receipt-restart-twin",
        "reconstruction",
        (IdentityAnchor("source", "capture", "completion-receipt-restart"),),
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


def test_restart_after_completed_operation_does_not_reexecute_receipted_operation():
    registry, revision = _registry()
    writes = []
    interrupted = DurableProductionOperationSequence(
        (
            _operation("task-1", revision, writes, converged=True),
            _operation("task-2", revision, writes, converged=False),
        )
    ).run()

    store = InMemoryDurableProductionPersistenceStore()
    store.save(DurableProductionPersistenceBundle.create(registry, interrupted.checkpoint))

    resumed_writes = []
    lifecycle = ProductionPersistenceResumeLifecycle.from_persistence_store(
        registry,
        (
            _operation("task-1", revision, resumed_writes, converged=True),
            _operation("task-2", revision, resumed_writes, converged=True),
        ),
        store,
    )

    result = lifecycle.run()

    assert result.state is ProductionOperationState.COMPLETED
    assert resumed_writes == ["task-2"]
    assert len(result.checkpoint.completed_receipts) == 2


def test_completed_sequence_restart_is_terminal_and_performs_no_writes():
    registry, revision = _registry()
    writes = []
    completed = DurableProductionOperationSequence(
        (_operation("task-1", revision, writes, converged=True),)
    ).run()
    assert completed.state is ProductionOperationState.COMPLETED

    store = InMemoryDurableProductionPersistenceStore()
    store.save(DurableProductionPersistenceBundle.create(registry, completed.checkpoint))

    resumed_writes = []
    lifecycle = ProductionPersistenceResumeLifecycle.from_persistence_store(
        registry,
        (_operation("task-1", revision, resumed_writes, converged=True),),
        store,
    )
    result = lifecycle.run()

    assert result.state is ProductionOperationState.COMPLETED
    assert lifecycle.next_operation_index == 1
    assert resumed_writes == []
    assert result.results == ()
