from __future__ import annotations

import pytest

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.production_completion_receipt import ProductionCompletionReceipt
from planning.production_operation_lifecycle import ProductionOperationLifecycle
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.registry_bound_durable_production_operation_sequence import RegistryBoundDurableProductionOperationSequence


def _registry():
    identity = DigitalTwinIdentity(
        "twin-1", "soccer-field",
        (IdentityAnchor("capture", "source", "soccer-field"),),
    )
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = DigitalTwinRevision(
        "twin-1", "r1", 1, RevisionKind.RECONSTRUCTION,
        None, identity.stable_fingerprint()
    )
    registry.register_revision(revision)
    return registry, identity, revision


def _operation(task_id, revision, writes):
    checkpoint = ProductionTaskCheckpoint.create(
        task_id, revision, (), {"task": task_id}, f"auth-{task_id}"
    )
    task = object.__new__(DurableResumableCorrectiveTask)
    task.checkpoint = checkpoint
    task.revision = revision

    def resume(max_steps=16):
        writes.append(task_id)
        return CorrectiveTaskResult((), {"task": task_id}, True)

    task.resume = resume
    return ProductionOperationLifecycle(task, lambda _: True)


def _completed_checkpoint(revision):
    checkpoint = ProductionTaskCheckpoint.create(
        "task-1", revision, (), {"done": True}, "auth-1"
    )
    receipt = ProductionCompletionReceipt.create(checkpoint, revision, {"done": True})
    from planning.durable_production_operation_sequence import DurableProductionSequenceCheckpoint
    return DurableProductionSequenceCheckpoint.create((receipt,), 1)


def test_tampered_completed_receipt_binding_is_rejected():
    _, _, revision = _registry()
    checkpoint = _completed_checkpoint(revision)
    snapshot = checkpoint.snapshot()
    receipt = dict(snapshot["completed_receipts"][0])
    receipt["revision_id"] = "r2"
    snapshot["completed_receipts"] = (receipt,)
    with pytest.raises(ValueError, match="integrity"):
        from planning.durable_production_operation_sequence import DurableProductionSequenceCheckpoint
        DurableProductionSequenceCheckpoint.rehydrate(snapshot)


def test_registry_revision_change_blocks_resume_before_any_write():
    registry, identity, revision = _registry()
    writes = []
    result = RegistryBoundDurableProductionOperationSequence(
        (_operation("task-1", revision, writes),), registry
    ).run()
    newer = DigitalTwinRevision(
        "twin-1", "r2", 2, RevisionKind.CLEANUP,
        "r1", identity.stable_fingerprint()
    )
    registry.register_revision(newer)
    stale_writes = []
    with pytest.raises(ValueError, match="stale Digital Twin revision"):
        RegistryBoundDurableProductionOperationSequence(
            (_operation("task-2", revision, stale_writes),), registry,
            checkpoint=result.checkpoint,
        )
    assert stale_writes == []


def test_completed_receipt_must_bind_to_corresponding_operation():
    registry, _, revision = _registry()
    checkpoint = _completed_checkpoint(revision)
    writes = []
    with pytest.raises(ValueError, match="corresponding production operation"):
        RegistryBoundDurableProductionOperationSequence(
            (_operation("task-2", revision, writes),), registry, checkpoint=checkpoint
        )
    assert writes == []


def test_current_revision_sequence_runs_and_keeps_canonical_binding():
    registry, _, revision = _registry()
    writes = []
    result = RegistryBoundDurableProductionOperationSequence(
        (_operation("task-1", revision, writes),), registry
    ).run()
    assert result.completed
    assert result.checkpoint.completed_receipts[0]["revision_id"] == revision.revision_id
    assert writes == ["task-1"]
