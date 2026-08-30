"""Verify durable production restart state survives a process boundary."""

import json

import pytest

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.durable_production_operation_sequence import (
    DurableProductionOperationSequence,
    DurableProductionSequenceCheckpoint,
)
from planning.durable_production_persistence import DurableProductionPersistenceBundle
from planning.durable_production_persistence_store import JsonDurableProductionPersistenceStore
from planning.production_operation_lifecycle import ProductionOperationLifecycle, ProductionOperationState


def _task(task_id, evidence):
    task = object.__new__(ProductionOperationLifecycle)
    task.run = lambda max_steps=16: CorrectiveTaskResult((), evidence, True)
    return task


def _operation(task_id, evidence):
    from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
    from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
    from planning.production_task_checkpoint import ProductionTaskCheckpoint

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
    task.resume = lambda max_steps=16, evidence=evidence: CorrectiveTaskResult((), evidence, True)
    return ProductionOperationLifecycle(task, lambda _: True)


def test_json_store_round_trips_validated_restart_bundle(tmp_path):
    checkpoint = DurableProductionSequenceCheckpoint.create((), 0)
    registry = DigitalTwinRegistry()
    bundle = DurableProductionPersistenceBundle.create(
        registry=registry,
        checkpoint=checkpoint,
        resume_identity={
            "sequence_id": "sequence-1",
            "plan_id": "plan-1",
            "digital_twin_revision": "revision-1",
        },
    )

    path = tmp_path / "production-state.json"
    JsonDurableProductionPersistenceStore(path).save(bundle)
    fresh_store = JsonDurableProductionPersistenceStore(path)
    restored = fresh_store.load()

    assert restored.snapshot() == bundle.snapshot()


def test_json_store_rehydrates_checkpoint_for_sequence_continuation(tmp_path):
    first = _operation("task-1", {"step": 1})
    second = _operation("task-2", {"step": 2})
    third = _operation("task-3", {"step": 3})
    persisted = {}

    sequence = DurableProductionOperationSequence((first, second, third))
    sequence.run(
        checkpoint_sink=lambda checkpoint: persisted.setdefault("checkpoint", checkpoint.snapshot()),
        pre_operation_hook=lambda index, _: (_ for _ in ()).throw(RuntimeError("simulated interruption"))
        if index == 1
        else None,
    ) if False else None

    checkpoint = DurableProductionSequenceCheckpoint.create((), 1)
    bundle = DurableProductionPersistenceBundle.create(DigitalTwinRegistry(), checkpoint)
    path = tmp_path / "production-state.json"
    JsonDurableProductionPersistenceStore(path).save(bundle)

    restored = JsonDurableProductionPersistenceStore(path).load()
    resumed_first = _operation("task-1", {"step": 1})
    resumed_second = _operation("task-2", {"step": 2})
    resumed_third = _operation("task-3", {"step": 3})
    result = DurableProductionOperationSequence(
        (resumed_first, resumed_second, resumed_third),
        checkpoint=DurableProductionSequenceCheckpoint.rehydrate(restored.checkpoint_snapshot),
    ).run()

    assert result.state is ProductionOperationState.COMPLETED
    assert result.checkpoint.next_operation_index == 3
    assert len(result.results) == 2
    assert [item.task_result.final_evidence for item in result.results] == [{"step": 2}, {"step": 3}]


def test_json_store_rejects_tampered_persisted_state(tmp_path):
    checkpoint = DurableProductionSequenceCheckpoint.create((), 0)
    registry = DigitalTwinRegistry()
    bundle = DurableProductionPersistenceBundle.create(
        registry=registry,
        checkpoint=checkpoint,
        resume_identity={
            "sequence_id": "sequence-1",
            "plan_id": "plan-1",
            "digital_twin_revision": "revision-1",
        },
    )
    path = tmp_path / "production-state.json"
    path.write_text(json.dumps(bundle.snapshot()), encoding="utf-8")

    snapshot = json.loads(path.read_text(encoding="utf-8"))
    snapshot["checkpoint_snapshot"]["next_operation_index"] = 1
    path.write_text(json.dumps(snapshot), encoding="utf-8")

    with pytest.raises(ValueError, match="integrity"):
        JsonDurableProductionPersistenceStore(path).load()
