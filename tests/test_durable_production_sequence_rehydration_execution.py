from __future__ import annotations

import pytest

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_operation_sequence import DurableProductionSequenceCheckpoint
from planning.durable_production_sequence_rehydration import DurableProductionSequenceRehydrator
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.production_operation_lifecycle import ProductionOperationLifecycle, ProductionOperationState
from planning.production_task_checkpoint import ProductionTaskCheckpoint


def _registry():
    identity = DigitalTwinIdentity(
        "rehydration-execution-twin",
        "reconstruction",
        (IdentityAnchor("source", "capture", "rehydration-execution"),),
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
    return ProductionOperationLifecycle(task, lambda evidence: converged)


def test_rehydrated_sequence_executes_only_unfinished_operations():
    registry, revision = _registry()
    writes = []
    first = _operation("task-1", revision, writes)
    second = _operation("task-2", revision, writes, converged=False)

    interrupted = __import__("planning.durable_production_operation_sequence", fromlist=["DurableProductionOperationSequence"]).DurableProductionOperationSequence((first, second)).run()
    assert interrupted.state is ProductionOperationState.BLOCKED
    registry_snapshot = registry.snapshot()
    checkpoint_snapshot = interrupted.checkpoint.snapshot()

    resumed_writes = []
    resumed_first = _operation("task-1", revision, resumed_writes)
    resumed_second = _operation("task-2", revision, resumed_writes)
    restored = DurableProductionSequenceRehydrator(registry).rehydrate(
        (resumed_first, resumed_second), registry_snapshot, checkpoint_snapshot
    )
    result = restored.run()

    assert result.state is ProductionOperationState.COMPLETED
    assert resumed_writes == ["task-2"]
    assert result.checkpoint.next_operation_index == 2


def test_rehydrator_rejects_tampered_sequence_checkpoint():
    registry, revision = _registry()
    registry_snapshot = registry.snapshot()
    operation = _operation("task-1", revision, [])
    checkpoint = DurableProductionSequenceCheckpoint.create((), 0).snapshot()
    checkpoint["next_operation_index"] = 1
    with pytest.raises(ValueError, match="integrity"):
        DurableProductionSequenceRehydrator(registry).rehydrate(
            (operation,), registry_snapshot, checkpoint
        )
