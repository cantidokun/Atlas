from __future__ import annotations

import pytest

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_operation_sequence import DurableProductionOperationSequence, DurableProductionSequenceCheckpoint
from planning.durable_production_sequence_rehydration import DurableProductionSequenceRehydrator
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.production_completion_receipt import ProductionCompletionReceipt
from planning.production_operation_lifecycle import ProductionOperationLifecycle, ProductionOperationState
from planning.production_task_checkpoint import ProductionTaskCheckpoint


def _registry():
    identity = DigitalTwinIdentity(
        "twin-1", "soccer-field", (IdentityAnchor("capture", "source", "twin-1"),)
    )
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = DigitalTwinRevision(
        "twin-1", "r1", 1, RevisionKind.RECONSTRUCTION, None,
        identity.stable_fingerprint(),
    )
    registry.register_revision(revision)
    return registry, identity, revision


def _operation(task_id, revision, writes, converged=True):
    checkpoint = ProductionTaskCheckpoint.create(task_id, revision, (), {"task_id": task_id}, f"auth-{task_id}")
    task = object.__new__(DurableResumableCorrectiveTask)
    task.checkpoint = checkpoint
    task.revision = revision
    def resume(max_steps=16):
        writes.append(task_id)
        return CorrectiveTaskResult((), {"task_id": task_id}, converged)
    task.resume = resume
    return ProductionOperationLifecycle(task, lambda _: True)


def test_rehydrator_loads_registry_and_sequence_checkpoint():
    registry, _, revision = _registry()
    writes = []
    operation = _operation("task-1", revision, writes)
    completed = DurableProductionOperationSequence((operation,),).run()
    restored = DurableProductionSequenceRehydrator(registry).rehydrate(
        (operation,), registry.snapshot(), completed.checkpoint.snapshot()
    )
    assert restored.next_operation_index == 1


def test_rehydrator_rejects_tampered_registry_snapshot():
    registry, _, revision = _registry()
    writes = []
    operation = _operation("task-1", revision, writes)
    completed = DurableProductionOperationSequence((operation,),).run()
    snapshot = registry.snapshot()
    snapshot["identities"]["twin-1"]["entity_type"] = "tampered"
    with pytest.raises(ValueError, match="digest"):
        DurableProductionSequenceRehydrator(registry).rehydrate(
            (operation,), snapshot, completed.checkpoint.snapshot()
        )


def test_rehydrator_rejects_tampered_sequence_checkpoint():
    registry, _, revision = _registry()
    task = _operation("task-1", revision, [])
    receipt = ProductionCompletionReceipt.create(task.task.checkpoint, revision, {"task_id": "task-1"})
    checkpoint = DurableProductionSequenceCheckpoint.create((receipt,), 1)
    snapshot = checkpoint.snapshot()
    snapshot["next_operation_index"] = 0
    with pytest.raises(ValueError, match="integrity"):
        DurableProductionSequenceRehydrator(registry).rehydrate(
            (task,), registry.snapshot(), snapshot
        )


def test_rehydrated_sequence_resumes_from_checkpoint_position():
    registry, _, revision = _registry()
    initial_writes = []
    first = _operation("task-1", revision, initial_writes)
    second = _operation("task-2", revision, initial_writes, converged=False)
    interrupted = DurableProductionOperationSequence((first, second)).run()
    assert interrupted.state is ProductionOperationState.BLOCKED

    resumed_writes = []
    resumed_first = _operation("task-1", revision, resumed_writes)
    resumed_second = _operation("task-2", revision, resumed_writes)
    rehydrated = DurableProductionSequenceRehydrator(registry).rehydrate(
        (resumed_first, resumed_second), registry.snapshot(), interrupted.checkpoint.snapshot()
    )
    result = rehydrated.run()
    assert result.state is ProductionOperationState.COMPLETED
    assert resumed_writes == ["task-2"]
