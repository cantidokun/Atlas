import pytest

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.production_completion_receipt import ProductionCompletionReceipt
from planning.production_operation_lifecycle import (
    ProductionOperationLifecycle,
    ProductionOperationState,
)
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind


def _task_result(converged=True, evidence=None):
    return CorrectiveTaskResult((), evidence or {"verified": True}, converged)


def _task(result):
    revision = DigitalTwinRevision(
        twin_id="twin-1",
        revision_id="r1",
        sequence=1,
        kind=RevisionKind.RECONSTRUCTION,
        source_revision_id=None,
        source_fingerprint="fingerprint",
    )
    checkpoint = ProductionTaskCheckpoint.create(
        "task-1",
        revision,
        (),
        {"checkpoint": True},
        "authorization-1",
    )
    task = object.__new__(DurableResumableCorrectiveTask)
    task.checkpoint = checkpoint
    task.revision = revision
    task.resume = lambda max_steps=16: result
    return task


def test_production_operation_does_not_complete_from_executor_convergence_alone():
    task = _task(_task_result(True, {"verified": False}))
    result = ProductionOperationLifecycle(task, lambda evidence: evidence["verified"]).run()
    assert result.state is ProductionOperationState.BLOCKED
    assert not result.completed
    assert result.receipt is None


def test_authoritative_verification_promotes_converged_result_to_completed():
    evidence = {"verified": True, "location": [2, 0, 0]}
    task = _task(_task_result(True, evidence))
    result = ProductionOperationLifecycle(task, lambda value: value["verified"]).run()
    assert result.state is ProductionOperationState.COMPLETED
    assert result.completed
    assert isinstance(result.receipt, ProductionCompletionReceipt)
    assert result.receipt.matches(task.checkpoint, task.revision, evidence)


def test_non_converged_result_is_blocked_without_authoritative_completion():
    task = _task(_task_result(False, {"verified": True}))
    result = ProductionOperationLifecycle(task, lambda evidence: True).run()
    assert result.state is ProductionOperationState.BLOCKED
    assert "did not converge" in result.reason
    assert result.receipt is None


def test_verifier_exception_blocks_operation():
    task = _task(_task_result(True))

    def verify(_evidence):
        raise RuntimeError("authoritative state unavailable")

    result = ProductionOperationLifecycle(task, verify).run()
    assert result.state is ProductionOperationState.BLOCKED
    assert "authoritative verification failed" in result.reason
    assert result.receipt is None


def test_rejected_authoritative_state_cannot_create_receipt():
    evidence = {"verified": False}
    task = _task(_task_result(True, evidence))
    result = ProductionOperationLifecycle(task, lambda _: False).run()
    assert result.state is ProductionOperationState.BLOCKED
    assert result.receipt is None


def test_invalid_constructor_inputs_fail_closed():
    with pytest.raises(TypeError, match="DurableResumableCorrectiveTask"):
        ProductionOperationLifecycle(object(), lambda _: True)
    task = object.__new__(DurableResumableCorrectiveTask)
    with pytest.raises(TypeError, match="callable"):
        ProductionOperationLifecycle(task, None)
