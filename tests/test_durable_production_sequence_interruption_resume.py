"""Prove durable multi-step production sequencing survives interruption."""

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_operation_sequence import DurableProductionOperationSequence
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.production_operation_lifecycle import ProductionOperationLifecycle, ProductionOperationState


def _task(task_id, evidence):
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
    task.resume = lambda max_steps=16: CorrectiveTaskResult((), evidence, True)
    return task


def _operation(task):
    return ProductionOperationLifecycle(task, lambda _: True)


def test_interrupted_sequence_rehydrates_and_runs_only_unfinished_steps():
    first = _operation(_task("task-1", {"step": 1}))
    second = _operation(_task("task-2", {"step": 2}))
    third = _operation(_task("task-3", {"step": 3}))
    persisted = {}

    def checkpoint_sink(checkpoint):
        persisted["checkpoint"] = checkpoint.snapshot()

    def interrupt_before_second(index, _operation):
        if index == 1:
            raise RuntimeError("simulated runtime interruption")

    sequence = DurableProductionOperationSequence((first, second, third))
    try:
        sequence.run(checkpoint_sink=checkpoint_sink, pre_operation_hook=interrupt_before_second)
    except RuntimeError as exc:
        assert str(exc) == "simulated runtime interruption"
    else:
        raise AssertionError("interruption hook did not interrupt the sequence")

    assert persisted["checkpoint"]["next_operation_index"] == 1
    assert first.state is ProductionOperationState.COMPLETED
    assert second.state is ProductionOperationState.RUNNING
    assert third.state is ProductionOperationState.RUNNING

    resumed_first = _operation(_task("task-1", {"step": 1}))
    resumed_second = _operation(_task("task-2", {"step": 2}))
    resumed_third = _operation(_task("task-3", {"step": 3}))
    resumed = DurableProductionOperationSequence(
        (resumed_first, resumed_second, resumed_third),
        checkpoint=sequence.checkpoint,
    ).run()

    assert resumed.state is ProductionOperationState.COMPLETED
    assert resumed.checkpoint.next_operation_index == 3
    assert len(resumed.results) == 2
    assert [result.task_result.final_evidence for result in resumed.results] == [
        {"step": 2},
        {"step": 3},
    ]
    assert resumed_first.state is ProductionOperationState.RUNNING
