import pytest

from action_plan import ActionSpec
from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.production_operation_lifecycle import (
    ProductionOperationLifecycle,
    ProductionOperationState,
)
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind


class FakeTask:
    def __init__(self, result):
        self.result = result

    def resume(self, max_steps=16):
        return self.result


def _task_result(converged=True, evidence=None):
    return CorrectiveTaskResult((), evidence or {"verified": True}, converged)


def test_production_operation_does_not_complete_from_executor_convergence_alone():
    task = object.__new__(DurableResumableCorrectiveTask)
    task.resume = lambda max_steps=16: _task_result(True, {"verified": False})
    lifecycle = ProductionOperationLifecycle(task, lambda evidence: evidence["verified"])
    result = lifecycle.run()
    assert result.state is ProductionOperationState.BLOCKED
    assert not result.completed


def test_authoritative_verification_promotes_converged_result_to_completed():
    task = object.__new__(DurableResumableCorrectiveTask)
    task.resume = lambda max_steps=16: _task_result(True, {"verified": True})
    lifecycle = ProductionOperationLifecycle(task, lambda evidence: evidence["verified"])
    result = lifecycle.run()
    assert result.state is ProductionOperationState.COMPLETED
    assert result.completed


def test_non_converged_result_is_blocked_without_authoritative_completion():
    task = object.__new__(DurableResumableCorrectiveTask)
    task.resume = lambda max_steps=16: _task_result(False, {"verified": True})
    lifecycle = ProductionOperationLifecycle(task, lambda evidence: True)
    result = lifecycle.run()
    assert result.state is ProductionOperationState.BLOCKED
    assert "did not converge" in result.reason


def test_verifier_exception_blocks_operation():
    task = object.__new__(DurableResumableCorrectiveTask)
    task.resume = lambda max_steps=16: _task_result(True)

    def verify(_evidence):
        raise RuntimeError("authoritative state unavailable")

    result = ProductionOperationLifecycle(task, verify).run()
    assert result.state is ProductionOperationState.BLOCKED
    assert "authoritative verification failed" in result.reason


def test_invalid_constructor_inputs_fail_closed():
    with pytest.raises(TypeError, match="DurableResumableCorrectiveTask"):
        ProductionOperationLifecycle(object(), lambda _: True)
    task = object.__new__(DurableResumableCorrectiveTask)
    with pytest.raises(TypeError, match="callable"):
        ProductionOperationLifecycle(task, None)
