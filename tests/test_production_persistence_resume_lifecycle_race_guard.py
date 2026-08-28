from __future__ import annotations

import pytest

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_operation_sequence import DurableProductionOperationSequence
from planning.durable_production_persistence import DurableProductionPersistenceBundle
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.in_memory_durable_production_persistence_store import InMemoryDurableProductionPersistenceStore
from planning.production_operation_lifecycle import ProductionOperationLifecycle
from planning.production_persistence_resume_lifecycle import ProductionPersistenceResumeLifecycle
from planning.production_resume_integrity_gate import ProductionResumeRequest
from planning.production_task_checkpoint import ProductionTaskCheckpoint


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


def _operation(task_id, revision, writes, converged=True):
    checkpoint = ProductionTaskCheckpoint.create(
        task_id, revision, (), {"task_id": task_id}, f"auth-{task_id}"
    )
    task = object.__new__(DurableResumableCorrectiveTask)
    task.checkpoint = checkpoint
    task.revision = revision

    def resume(max_steps=16):
        writes.append(task_id)
        return CorrectiveTaskResult((), {"task_id": task_id}, converged)

    task.resume = resume
    return ProductionOperationLifecycle(task, lambda _evidence: True)


def _interrupted_bundle(registry, revision):
    writes = []
    result = DurableProductionOperationSequence(
        (_operation("task-1", revision, writes), _operation("task-2", revision, writes, converged=False))
    ).run()
    return DurableProductionPersistenceBundle.create(
        registry,
        result.checkpoint,
        resume_identity={
            "sequence_id": "sequence-1",
            "plan_id": "plan-1",
            "digital_twin_revision": revision.revision_id,
        },
    )


def test_requested_resume_identity_is_checked_before_first_resume_write():
    registry, revision = _registry()
    store = InMemoryDurableProductionPersistenceStore()
    store.save(_interrupted_bundle(registry, revision))
    writes = []
    request = ProductionResumeRequest(
        sequence_id="wrong-sequence",
        plan_id="plan-1",
        digital_twin_revision=revision.revision_id,
    )

    with pytest.raises(ValueError, match="sequence_id"):
        ProductionPersistenceResumeLifecycle.from_persistence_store(
            registry,
            (_operation("task-1", revision, writes), _operation("task-2", revision, writes)),
            store,
            resume_request=request,
        )

    assert writes == []


def test_resume_identity_is_rechecked_when_run_begins():
    registry, revision = _registry()
    store = InMemoryDurableProductionPersistenceStore()
    bundle = _interrupted_bundle(registry, revision)
    store.save(bundle)
    writes = []
    request = ProductionResumeRequest(
        sequence_id=bundle.resume_identity["sequence_id"],
        plan_id=bundle.resume_identity["plan_id"],
        digital_twin_revision=revision.revision_id,
    )
    lifecycle = ProductionPersistenceResumeLifecycle.from_persistence_store(
        registry,
        (_operation("task-1", revision, writes), _operation("task-2", revision, writes)),
        store,
        resume_request=request,
    )
    lifecycle.resume_request = ProductionResumeRequest(
        sequence_id="changed-sequence",
        plan_id=request.plan_id,
        digital_twin_revision=request.digital_twin_revision,
    )

    with pytest.raises(ValueError, match="sequence_id"):
        lifecycle.run()

    assert writes == []


def test_resume_revision_must_be_current_canonical_revision():
    registry, revision = _registry()
    newer = DigitalTwinRevision(
        revision.twin_id,
        "r2",
        2,
        RevisionKind.CLEANUP,
        source_revision_id=revision.revision_id,
        source_fingerprint=revision.source_fingerprint,
    )
    registry.register_revision(newer)
    store = InMemoryDurableProductionPersistenceStore()
    bundle = _interrupted_bundle(registry, revision)
    store.save(bundle)
    writes = []
    request = ProductionResumeRequest(
        sequence_id="sequence-1",
        plan_id="plan-1",
        digital_twin_revision=revision.revision_id,
    )

    with pytest.raises(ValueError, match="canonical"):
        ProductionPersistenceResumeLifecycle.from_persistence_store(
            registry,
            (_operation("task-1", revision, writes),),
            store,
            resume_request=request,
        )

    assert writes == []


def test_resume_revision_must_exist_in_canonical_registry():
    registry, revision = _registry()
    store = InMemoryDurableProductionPersistenceStore()
    bundle = _interrupted_bundle(registry, revision)
    store.save(bundle)
    registry_without_revision = DigitalTwinRegistry()
    identity = next(iter(registry._identities.values()))
    registry_without_revision.register_identity(identity)
    writes = []
    request = ProductionResumeRequest(
        sequence_id="sequence-1",
        plan_id="plan-1",
        digital_twin_revision=revision.revision_id,
    )

    with pytest.raises(ValueError, match="not canonical"):
        ProductionPersistenceResumeLifecycle.from_persistence_store(
            registry_without_revision,
            (_operation("task-1", revision, writes),),
            store,
            resume_request=request,
        )

    assert writes == []


def test_store_snapshot_preserves_resume_identity_and_integrity_digest():
    registry, revision = _registry()
    store = InMemoryDurableProductionPersistenceStore()
    bundle = _interrupted_bundle(registry, revision)
    store.save(bundle)

    snapshot = store.snapshot()

    assert snapshot is not None
    assert snapshot["resume_identity"] == bundle.resume_identity
    assert snapshot["resume_identity_digest"] == bundle.resume_identity_digest
    restored = DurableProductionPersistenceBundle.from_snapshot(snapshot)
    assert restored.resume_identity == bundle.resume_identity
    assert restored.resume_identity_digest == bundle.resume_identity_digest
