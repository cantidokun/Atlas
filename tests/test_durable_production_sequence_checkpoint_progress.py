from planning.durable_production_operation_sequence import DurableProductionOperationSequence
from planning.production_operation_lifecycle import ProductionOperationState


def test_successful_operation_advances_checkpoint_exactly_one_receipt():
    # This regression belongs beside the durable sequence boundary: a successful
    # operation must persist exactly one receipt and advance exactly one index.
    first = _operation("task-1", converged=True)
    second = _operation("task-2", converged=False)

    sequence = DurableProductionOperationSequence((first, second))
    result = sequence.run()

    assert result.state is ProductionOperationState.BLOCKED
    assert sequence.checkpoint.next_operation_index == 1
    assert len(sequence.checkpoint.completed_receipts) == 1
    assert sequence.checkpoint.completed_receipts[0]["task_id"] == "task-1"


def test_blocked_first_operation_does_not_advance_checkpoint():
    operation = _operation("task-1", converged=False)
    sequence = DurableProductionOperationSequence((operation,))

    result = sequence.run()

    assert result.state is ProductionOperationState.BLOCKED
    assert sequence.checkpoint.next_operation_index == 0
    assert sequence.checkpoint.completed_receipts == ()


def _operation(task_id, *, converged):
    # Kept as a small adapter seam so this test exercises only checkpoint
    # progression rather than any concrete Blender executor.
    from tests.test_durable_production_sequence_restart import _operation as make_operation
    return make_operation(task_id, converged=converged)
