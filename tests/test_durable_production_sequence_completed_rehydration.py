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
        "completed-rehydration-twin",
        "reconstruction",
        (IdentityAnchor("source", "capture", "completed-rehydration"),),
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


def _operation(task_id, revision, writes):
    checkpoint = ProductionTaskCheckpoint.create(
        task_id, revision, (), {"task_id": task_id}, f"auth-{task_id}"
    )
    task = object.__new__(DurableResumableCorrectiveTask)
    task.checkpoint = checkpoint
    task.revision = revision

    def resume(max_steps=16):
        writes.append(task_id)
        return CorrectiveTaskResult((), {"task_id": task_id}, True)

    task.resume = resume
    return ProductionOperationLifecycle(task, lambda _evidence: True)


def test_rehydrated_completed_sequence_does_not_replay_completed_operations():
    registry, revision = _registry()
    writes = []
    sequence = DurableProductionOperationSequence(
        (_operation("task-1", revision, writes), _operation("task-2", revision, writes))
    )
    completed = sequence.run()

    assert completed.state is ProductionOperationState.COMPLETED
    assert writes == ["task-1", "task-2"]

    restored_writes = []
    restored = DurableProductionSequenceRehydrator(registry).rehydrate(
        (_operation("task-1", revision, restored_writes), _operation("task-2", revision, restored_writes)),
        registry.snapshot(),
        completed.checkpoint.snapshot(),
    )
    result = restored.run()

    assert result.state is ProductionOperationState.COMPLETED
    assert result.results == ()
    assert restored_writes == []
    assert result.checkpoint.next_operation_index == 2
