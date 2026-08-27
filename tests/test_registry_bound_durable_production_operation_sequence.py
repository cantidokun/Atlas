import pytest

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.digital_twin_identity import DigitalTwinIdentity
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.production_operation_lifecycle import ProductionOperationLifecycle
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.registry_bound_durable_production_operation_sequence import RegistryBoundDurableProductionOperationSequence


def _registry():
    identity = DigitalTwinIdentity(twin_id="twin-1", entity_type="soccer_field", anchors=())
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    first = DigitalTwinRevision(
        twin_id="twin-1", revision_id="r1", sequence=1,
        kind=RevisionKind.RECONSTRUCTION, source_revision_id=None,
        source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(first)
    return registry, identity, first


def _operation(task_id, revision, writes):
    checkpoint = ProductionTaskCheckpoint.create(
        task_id, revision, (), {"task": task_id}, "auth-1"
    )
    task = object.__new__(DurableResumableCorrectiveTask)
    task.checkpoint = checkpoint
    task.revision = revision
    def resume(max_steps=16):
        writes.append(task_id)
        return CorrectiveTaskResult((), {"ok": True}, True)
    task.resume = resume
    return ProductionOperationLifecycle(task, lambda _: True)


def test_sequence_accepts_current_canonical_revision_and_runs():
    registry, _, revision = _registry()
    writes = []
    result = RegistryBoundDurableProductionOperationSequence(
        (_operation("task-1", revision, writes),), registry
    ).run()
    assert result.completed
    assert writes == ["task-1"]


def test_sequence_rejects_stale_operation_before_any_write():
    registry, identity, revision = _registry()
    newer = DigitalTwinRevision(
        twin_id="twin-1", revision_id="r2", sequence=2,
        kind=RevisionKind.CLEANUP, source_revision_id="r1",
        source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(newer)
    writes = []
    with pytest.raises(ValueError, match="current canonical Digital Twin revision"):
        RegistryBoundDurableProductionOperationSequence(
            (_operation("task-1", revision, writes),), registry
        )
    assert writes == []


def test_sequence_rejects_registry_bound_completed_receipt_from_stale_revision():
    registry, identity, revision = _registry()
    writes = []
    operation = _operation("task-1", revision, writes)
    result = RegistryBoundDurableProductionOperationSequence((operation,), registry).run()
    newer = DigitalTwinRevision(
        twin_id="twin-1", revision_id="r2", sequence=2,
        kind=RevisionKind.CLEANUP, source_revision_id="r1",
        source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(newer)
    stale_writes = []
    with pytest.raises(ValueError, match="stale Digital Twin revision"):
        RegistryBoundDurableProductionOperationSequence(
            (_operation("task-1", revision, stale_writes),), registry, checkpoint=result.checkpoint
        )
    assert stale_writes == []


def test_sequence_rejects_stale_unfinished_operation_before_any_write():
    registry, identity, revision = _registry()
    writes = []
    first = _operation("task-1", revision, writes)
    result = RegistryBoundDurableProductionOperationSequence((first,), registry).run()
    newer = DigitalTwinRevision(
        twin_id="twin-1", revision_id="r2", sequence=2,
        kind=RevisionKind.CLEANUP, source_revision_id="r1",
        source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(newer)
    stale_writes = []
    second = _operation("task-2", revision, stale_writes)
    with pytest.raises(ValueError, match="stale Digital Twin revision|current canonical Digital Twin revision"):
        RegistryBoundDurableProductionOperationSequence(
            (first, second), registry, checkpoint=result.checkpoint
        )
    assert stale_writes == []
