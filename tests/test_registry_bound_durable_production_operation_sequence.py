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


def _operation(revision, writes):
    checkpoint = ProductionTaskCheckpoint.create(
        "task-1", revision, (), {"task": "one"}, "auth-1"
    )
    task = object.__new__(DurableResumableCorrectiveTask)
    task.checkpoint = checkpoint
    task.revision = revision
    def resume(max_steps=16):
        writes.append("write")
        return CorrectiveTaskResult((), {"ok": True}, True)
    task.resume = resume
    return ProductionOperationLifecycle(task, lambda _: True)


def test_sequence_accepts_current_canonical_revision_and_runs():
    registry, _, revision = _registry()
    writes = []
    result = RegistryBoundDurableProductionOperationSequence(
        (_operation(revision, writes),), registry
    ).run()
    assert result.completed
    assert writes == ["write"]


def test_sequence_rejects_stale_operation_before_any_write():
    registry, identity, revision = _registry()
    newer = DigitalTwinRevision(
        twin_id="twin-1", revision_id="r2", sequence=2,
        kind=RevisionKind.CLEANUP, source_revision_id="r1",
        source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(newer)
    writes = []
    with pytest.raises(ValueError, match="stale Digital Twin revision"):
        RegistryBoundDurableProductionOperationSequence(
            (_operation(revision, writes),), registry
        )
    assert writes == []


def test_sequence_rejects_registry_bound_completed_receipt_from_stale_revision():
    registry, identity, revision = _registry()
    newer = DigitalTwinRevision(
        twin_id="twin-1", revision_id="r2", sequence=2,
        kind=RevisionKind.CLEANUP, source_revision_id="r1",
        source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(newer)
    writes = []
    operation = _operation(revision, writes)
    result = RegistryBoundDurableProductionOperationSequence(
        (operation,), DigitalTwinRegistry.from_snapshot(_registry()[0].snapshot())
    ).run()
    checkpoint = result.checkpoint
    with pytest.raises(ValueError, match="stale Digital Twin revision"):
        RegistryBoundDurableProductionOperationSequence(
            (_operation(revision, writes),), registry, checkpoint=checkpoint
        )
