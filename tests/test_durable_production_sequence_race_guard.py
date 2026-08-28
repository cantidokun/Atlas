from __future__ import annotations

import pytest

from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_sequence_rehydration import DurableProductionSequenceRehydrator
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.production_operation_lifecycle import ProductionOperationLifecycle
from planning.autonomous_corrective_task import CorrectiveTaskResult


def _registry():
    identity = DigitalTwinIdentity(
        "race-twin", "reconstruction", (IdentityAnchor("source", "capture", "race"),)
    )
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = DigitalTwinRevision(
        identity.twin_id, "r1", 1, RevisionKind.RECONSTRUCTION,
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


def test_rehydration_does_not_begin_writes_when_canonical_revision_drifts():
    registry, revision = _registry()
    persisted_registry = registry.snapshot()
    writes = []
    checkpoint = ProductionTaskCheckpoint.create(
        "task-1", revision, (), {"task_id": "task-1"}, "auth-task-1"
    )

    # Build a valid empty durable sequence checkpoint through the public rehydration
    # boundary; the registry drift must be rejected before any operation can run.
    from planning.durable_production_operation_sequence import DurableProductionOperationSequence

    task = object.__new__(DurableResumableCorrectiveTask)
    task.checkpoint = checkpoint
    task.revision = revision
    task.resume = lambda max_steps=16: CorrectiveTaskResult((), {"task_id": "task-1"}, True)
    operation = ProductionOperationLifecycle(task, lambda _evidence: True)
    persisted_checkpoint = DurableProductionOperationSequence((operation,)).checkpoint.snapshot()

    newer = DigitalTwinRevision(
        revision.twin_id, "r2", 2, RevisionKind.CLEANUP,
        source_revision_id=revision.revision_id,
        source_fingerprint=revision.source_fingerprint,
    )
    registry.register_revision(newer)

    with pytest.raises(ValueError, match="stale Digital Twin revision"):
        DurableProductionSequenceRehydrator(registry).rehydrate(
            (_operation("task-1", revision, writes),),
            persisted_registry,
            persisted_checkpoint,
        )
    assert writes == []
