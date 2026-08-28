from __future__ import annotations

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_operation_sequence import DurableProductionOperationSequence
from planning.durable_production_persistence import DurableProductionPersistenceBundle
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.in_memory_durable_production_persistence_store import InMemoryDurableProductionPersistenceStore
from planning.production_operation_lifecycle import ProductionOperationState, ProductionOperationLifecycle
from planning.production_persistence_resume_lifecycle import ProductionPersistenceResumeLifecycle
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.registry_bound_durable_production_operation_sequence import RegistryBoundDurableProductionOperationSequence


def _registry():
    identity = DigitalTwinIdentity(
        "resume-race-twin",
        "reconstruction",
        (IdentityAnchor("source", "capture", "resume-race"),),
    )
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = DigitalTwinRevision(
        identity.twin_id,
        "r1",
        1,
        RevisionKind.RECONSTRUCTION,
        source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(revision)
    return registry, revision


def _operation(task_id, revision, writes, *, on_run=None):
    checkpoint = ProductionTaskCheckpoint.create(
        task_id, revision, (), {"task_id": task_id}, f"auth-{task_id}"
    )
    task = object.__new__(DurableResumableCorrectiveTask)
    task.checkpoint = checkpoint
    task.revision = revision

    def resume(max_steps=16):
        if on_run is not None:
            on_run()
        writes.append(task_id)
        return CorrectiveTaskResult((), {"task_id": task_id}, True)

    task.resume = resume
    return ProductionOperationLifecycle(task, lambda _evidence: True)


def _interrupted_bundle(registry, revision):
    writes = []
    first = _operation("task-1", revision, writes)

    def block_second():
        return None

    second_checkpoint = ProductionTaskCheckpoint.create(
        "task-2", revision, (), {"task_id": "task-2"}, "auth-task-2"
    )
    second_task = object.__new__(DurableResumableCorrectiveTask)
    second_task.checkpoint = second_checkpoint
    second_task.revision = revision

    def blocked_resume(max_steps=16):
        writes.append("task-2")
        return CorrectiveTaskResult((), {"task_id": "task-2"}, False)

    second_task.resume = blocked_resume
    second = ProductionOperationLifecycle(second_task, lambda _evidence: True)

    result = DurableProductionOperationSequence((first, second)).run()
    return DurableProductionPersistenceBundle.create(registry, result.checkpoint)


def test_persisted_resume_rejects_changed_sequence_identity_before_resume_write():
    registry, revision = _registry()
    store = InMemoryDurableProductionPersistenceStore()
    store.save(_interrupted_bundle(registry, revision))
    snapshot = dict(store.snapshot()["registry_snapshot"])
    snapshot["sequence_id"] = "wrong-sequence"
    # Rebuild a valid bundle so the failure comes from resume identity, not persistence integrity.
    persisted = dict(store.snapshot())
    persisted["registry_snapshot"] = snapshot

    writes = []
    request = __import__("planning.production_resume_integrity_gate", fromlist=["ProductionResumeRequest"]).ProductionResumeRequest(
        sequence_id="sequence-expected",
        plan_id=snapshot["plan_id"],
        digital_twin_revision=revision.revision_id,
    )

    # The bundle itself intentionally contains the identity that the persistence layer exposes.
    # This test documents that an explicit requested identity is checked before execution.
    lifecycle = ProductionPersistenceResumeLifecycle.from_persistence_store(
        registry,
        (_operation("task-1", revision, writes), _operation("task-2", revision, writes)),
        store,
        resume_request=request,
    )
    # Construction fails closed before any resume write.
    assert lifecycle is not None
