import pytest

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.production_completion_receipt import ProductionCompletionReceipt
from planning.production_operation_lifecycle import (
    ProductionOperationLifecycle,
    ProductionOperationSequence,
    ProductionOperationState,
)
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.production_registry_resume_lifecycle import ProductionRegistryResumeLifecycle


def _task_result(converged=True, evidence=None):
    return CorrectiveTaskResult((), evidence or {"verified": True}, converged)


def _task(result, task_id="task-1"):
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


def _lifecycle(result, verified=True, task_id="task-1"):
    task = _task(result, task_id=task_id)
    return ProductionOperationLifecycle(task, lambda evidence: verified)


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


def test_operation_sequence_completes_only_when_every_operation_is_authoritatively_verified():
    first = _lifecycle(_task_result(True, {"verified": True}), task_id="task-1")
    second = _lifecycle(_task_result(True, {"verified": True}), task_id="task-2")

    result = ProductionOperationSequence((first, second)).run()

    assert result.state is ProductionOperationState.COMPLETED
    assert result.completed
    assert len(result.results) == 2
    assert len(result.receipts) == 2
    assert all(item.receipt is not None for item in result.results)


def test_operation_sequence_blocks_at_first_failed_operation_and_does_not_run_later_steps():
    first = _lifecycle(_task_result(True, {"verified": True}), task_id="task-1")
    second = _lifecycle(_task_result(True, {"verified": False}), verified=False, task_id="task-2")
    third = _lifecycle(_task_result(True, {"verified": True}), task_id="task-3")

    result = ProductionOperationSequence((first, second, third)).run()

    assert result.state is ProductionOperationState.BLOCKED
    assert not result.completed
    assert len(result.results) == 2
    assert result.results[0].completed
    assert result.results[1].state is ProductionOperationState.BLOCKED
    assert len(result.receipts) == 1
    assert third.state is ProductionOperationState.RUNNING


def test_operation_sequence_rejects_empty_or_invalid_operations():
    with pytest.raises(ValueError, match="at least one"):
        ProductionOperationSequence(())
    with pytest.raises(TypeError, match="ProductionOperationLifecycle"):
        ProductionOperationSequence((object(),))


def test_invalid_constructor_inputs_fail_closed():
    with pytest.raises(TypeError, match="DurableResumableCorrectiveTask"):
        ProductionOperationLifecycle(object(), lambda _: True)
    task = object.__new__(DurableResumableCorrectiveTask)
    with pytest.raises(TypeError, match="callable"):
        ProductionOperationLifecycle(task, None)


def _registry_and_revision():
    identity = DigitalTwinIdentity(
        twin_id="twin-1",
        entity_type="reconstruction",
        anchors=(IdentityAnchor("scene", "source", "scene-1"),),
    )
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = DigitalTwinRevision(
        twin_id="twin-1",
        revision_id="r1",
        sequence=1,
        kind=RevisionKind.RECONSTRUCTION,
        source_revision_id=None,
        source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(revision)
    return registry, revision


def _checkpoint_snapshot(revision):
    checkpoint = ProductionTaskCheckpoint.create(
        "task-1",
        revision,
        (),
        {"checkpoint": True},
        "authorization-1",
    )
    return checkpoint.snapshot()


def test_registry_snapshot_constructor_rehydrates_canonical_resume_boundary():
    registry, revision = _registry_and_revision()

    lifecycle = ProductionRegistryResumeLifecycle.from_registry_snapshot(
        registry.snapshot(),
        _checkpoint_snapshot(revision),
        revision,
        observe=lambda: {"fresh": True},
        plan=lambda _: (),
        verify_final=lambda _: True,
    )

    assert lifecycle.registry.canonical_revision("twin-1") == revision
    assert lifecycle.checkpoint.revision_id == "r1"
    assert lifecycle.checkpoint.task_id == "task-1"


def test_registry_snapshot_constructor_rejects_tampering_before_checkpoint_rehydration():
    registry, revision = _registry_and_revision()
    snapshot = registry.snapshot()
    snapshot["snapshot_digest"] = "tampered"

    with pytest.raises(ValueError, match="snapshot digest"):
        ProductionRegistryResumeLifecycle.from_registry_snapshot(
            snapshot,
            _checkpoint_snapshot(revision),
            revision,
            observe=lambda: {"fresh": True},
            plan=lambda _: (),
            verify_final=lambda _: True,
        )
