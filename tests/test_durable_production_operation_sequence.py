import pytest

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_operation_sequence import (
    DurableProductionOperationSequence,
    DurableProductionSequenceCheckpoint,
)
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.production_completion_receipt import ProductionCompletionReceipt
from planning.production_operation_lifecycle import ProductionOperationLifecycle, ProductionOperationState
from planning.production_task_checkpoint import ProductionTaskCheckpoint


def _task(result, task_id):
    revision = DigitalTwinRevision(
        twin_id="twin-1",
        revision_id="r1",
        sequence=1,
        kind=RevisionKind.RECONSTRUCTION,
        source_revision_id=None,
        source_fingerprint="fingerprint",
    )
    checkpoint = ProductionTaskCheckpoint.create(
        task_id,
        revision,
        (),
        {"checkpoint": True, "task_id": task_id},
        f"authorization-{task_id}",
    )
    task = object.__new__(DurableResumableCorrectiveTask)
    task.checkpoint = checkpoint
    task.revision = revision
    task.resume = lambda max_steps=16: result
    return task


def _operation(task, verified=True):
    return ProductionOperationLifecycle(task, lambda _: verified)


def test_sequence_persists_completed_receipt_before_next_operation():
    first = _operation(_task(CorrectiveTaskResult((), {"step": 1}, True), "task-1"))
    second = _operation(_task(CorrectiveTaskResult((), {"step": 2}, False), "task-2"))

    result = DurableProductionOperationSequence((first, second)).run()

    assert result.state is ProductionOperationState.BLOCKED
    assert result.checkpoint.next_operation_index == 1
    assert len(result.checkpoint.completed_receipts) == 1
    assert result.results[0].completed


def test_rehydrated_sequence_resumes_at_first_unfinished_operation():
    first = _operation(_task(CorrectiveTaskResult((), {"step": 1}, True), "task-1"))
    second = _operation(_task(CorrectiveTaskResult((), {"step": 2}, False), "task-2"))
    interrupted = DurableProductionOperationSequence((first, second)).run()

    resumed_first = _operation(_task(CorrectiveTaskResult((), {"step": 1}, True), "task-1"))
    resumed_second = _operation(_task(CorrectiveTaskResult((), {"step": 2}, True), "task-2"))
    resumed = DurableProductionOperationSequence(
        (resumed_first, resumed_second),
        checkpoint=interrupted.checkpoint,
    ).run()

    assert resumed.state is ProductionOperationState.COMPLETED
    assert resumed.checkpoint.next_operation_index == 2
    assert len(resumed.results) == 1
    assert resumed.results[0].task_result.final_evidence == {"step": 2}
    assert resumed_first.state is ProductionOperationState.RUNNING


def test_rehydrated_sequence_rejects_changed_operation_identity():
    first = _operation(_task(CorrectiveTaskResult((), {"step": 1}, True), "task-1"))
    second = _operation(_task(CorrectiveTaskResult((), {"step": 2}, False), "task-2"))
    interrupted = DurableProductionOperationSequence((first, second)).run()

    changed_first = _operation(_task(CorrectiveTaskResult((), {"step": 1}, True), "task-1"))
    changed_second = _operation(_task(CorrectiveTaskResult((), {"step": 2}, True), "task-replaced"))

    with pytest.raises(ValueError, match="operation identity mismatch"):
        DurableProductionOperationSequence(
            (changed_first, changed_second),
            checkpoint=interrupted.checkpoint,
        )


def test_sequence_never_runs_later_operations_after_a_block():
    first = _operation(_task(CorrectiveTaskResult((), {"step": 1}, True), "task-1"))
    second = _operation(_task(CorrectiveTaskResult((), {"step": 2}, True), "task-2"), verified=False)
    third = _operation(_task(CorrectiveTaskResult((), {"step": 3}, True), "task-3"))

    result = DurableProductionOperationSequence((first, second, third)).run()

    assert result.state is ProductionOperationState.BLOCKED
    assert len(result.results) == 2
    assert third.state is ProductionOperationState.RUNNING
    assert result.checkpoint.next_operation_index == 1


def test_checkpoint_rejects_tampering():
    checkpoint = DurableProductionSequenceCheckpoint.create((), 0)
    snapshot = checkpoint.snapshot()
    snapshot["next_operation_index"] = 1

    with pytest.raises(ValueError, match="integrity"):
        DurableProductionSequenceCheckpoint.rehydrate(snapshot)


def test_checkpoint_rejects_inconsistent_operation_index():
    checkpoint = DurableProductionSequenceCheckpoint.create((), 0)
    snapshot = checkpoint.snapshot()
    snapshot["sequence_digest"] = checkpoint.sequence_digest
    snapshot["next_operation_index"] = 1

    with pytest.raises(ValueError, match="integrity"):
        DurableProductionSequenceCheckpoint.rehydrate(snapshot)


def test_sequence_rejects_checkpoint_beyond_operation_count():
    first_task = _task(CorrectiveTaskResult((), {"step": 1}, True), "task-1")
    second_task = _task(CorrectiveTaskResult((), {"step": 2}, True), "task-2")
    first_receipt = ProductionCompletionReceipt.create(
        first_task.checkpoint,
        first_task.revision,
        {"step": 1},
    )
    second_receipt = ProductionCompletionReceipt.create(
        second_task.checkpoint,
        second_task.revision,
        {"step": 2},
    )
    checkpoint = DurableProductionSequenceCheckpoint.create(
        (first_receipt, second_receipt),
        2,
    )
    operation = _operation(first_task)

    with pytest.raises(ValueError, match="more completed operations"):
        DurableProductionOperationSequence((operation,), checkpoint=checkpoint)


def test_empty_sequence_is_rejected():
    with pytest.raises(ValueError, match="at least one"):
        DurableProductionOperationSequence(())
