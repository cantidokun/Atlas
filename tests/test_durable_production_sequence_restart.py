from __future__ import annotations

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_operation_sequence import DurableProductionOperationSequence
from planning.durable_production_sequence_rehydration import DurableProductionSequenceRehydrator
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.production_operation_lifecycle import ProductionOperationLifecycle, ProductionOperationState
from planning.production_task_checkpoint import ProductionTaskCheckpoint


def _registry():
    identity = DigitalTwinIdentity(
        "restart-twin",
        "reconstruction",
        (IdentityAnchor("source", "capture", "restart-boundary"),),
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


def _operation(task_id, revision, writes, converged=True, authoritative=True):
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
    return ProductionOperationLifecycle(task, lambda evidence: authoritative)


def test_restart_boundary_persists_first_completion_and_resumes_only_second_operation():
    registry, revision = _registry()
    writes = []
    first = _operation("task-1", revision, writes, converged=True)
    second = _operation("task-2", revision, writes, converged=False)

    interrupted = DurableProductionOperationSequence((first, second)).run()
    assert interrupted.state is ProductionOperationState.BLOCKED
    assert interrupted.checkpoint.next_operation_index == 1
    assert writes == ["task-1", "task-2"]

    registry_snapshot = registry.snapshot()
    checkpoint_snapshot = interrupted.checkpoint.snapshot()

    resumed_writes = []
    resumed_first = _operation("task-1", revision, resumed_writes, converged=True)
    resumed_second = _operation("task-2", revision, resumed_writes, converged=True)
    restored = DurableProductionSequenceRehydrator(registry).rehydrate(
        (resumed_first, resumed_second), registry_snapshot, checkpoint_snapshot
    )

    result = restored.run()

    assert result.state is ProductionOperationState.COMPLETED
    assert resumed_writes == ["task-2"]
    assert result.checkpoint.next_operation_index == 2


def test_authoritative_rejection_does_not_advance_durable_checkpoint():
    registry, revision = _registry()
    writes = []
    operation = _operation(
        "task-1", revision, writes, converged=True, authoritative=False
    )

    result = DurableProductionOperationSequence((operation,)).run()

    assert result.state is ProductionOperationState.BLOCKED
    assert result.results[0].receipt is None
    assert result.checkpoint.next_operation_index == 0
    assert result.checkpoint.completed_receipts == ()
    assert writes == ["task-1"]


def test_multi_operation_block_preserves_prior_receipts_and_resumes_only_blocked_operation():
    registry, revision = _registry()
    writes = []
    first = _operation("task-1", revision, writes, converged=True)
    second = _operation("task-2", revision, writes, converged=True)
    third = _operation("task-3", revision, writes, converged=False)

    interrupted = DurableProductionOperationSequence((first, second, third)).run()

    assert interrupted.state is ProductionOperationState.BLOCKED
    assert interrupted.checkpoint.next_operation_index == 2
    assert [receipt["task_id"] for receipt in interrupted.checkpoint.completed_receipts] == [
        "task-1",
        "task-2",
    ]
    assert writes == ["task-1", "task-2", "task-3"]

    resumed_writes = []
    restored = DurableProductionSequenceRehydrator(registry).rehydrate(
        (
            _operation("task-1", revision, [], converged=True),
            _operation("task-2", revision, [], converged=True),
            _operation("task-3", revision, resumed_writes, converged=True),
        ),
        registry.snapshot(),
        interrupted.checkpoint.snapshot(),
    )

    result = restored.run()

    assert result.state is ProductionOperationState.COMPLETED
    assert resumed_writes == ["task-3"]
    assert result.checkpoint.next_operation_index == 3
    assert [receipt["task_id"] for receipt in result.checkpoint.completed_receipts] == [
        "task-1",
        "task-2",
        "task-3",
    ]
