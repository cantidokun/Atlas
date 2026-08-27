"""Live proof that a rehydrated durable sequence fails closed after registry advancement."""
from __future__ import annotations

import json

from planning.digital_twin_identity import DigitalTwinIdentity
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.production_completion_receipt import ProductionCompletionReceipt
from planning.production_operation_lifecycle import ProductionOperationLifecycle
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.registry_bound_durable_production_operation_sequence import RegistryBoundDurableProductionOperationSequence


def _revision(revision_id: str, sequence: int, identity: DigitalTwinIdentity) -> DigitalTwinRevision:
    return DigitalTwinRevision(identity.twin_id, revision_id, sequence, RevisionKind.RECONSTRUCTION, source_fingerprint=identity.stable_fingerprint())


def _operation(task_id, revision, writes):
    checkpoint = ProductionTaskCheckpoint.create(task_id, revision, (), {"task_id": task_id}, "auth")
    task = object.__new__(DurableResumableCorrectiveTask)
    task.checkpoint = checkpoint
    task.revision = revision
    task.resume = lambda max_steps=16: writes.append(task_id)
    return ProductionOperationLifecycle(task, lambda _: True)


def main():
    identity = DigitalTwinIdentity("rehydrated-stale-twin", "reconstruction")
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    r1 = _revision("r1", 1, identity)
    registry.register_revision(r1)
    registry.promote_revision(r1)

    writes = []
    op1 = _operation("op-1", r1, writes)
    op2 = _operation("op-2", r1, writes)
    completed = RegistryBoundDurableProductionOperationSequence((op1, op2), registry).run()
    assert completed.state.value == "completed"
    snapshot = registry.snapshot()

    r2 = _revision("r2", 2, identity)
    registry.register_revision(r2)
    registry.promote_revision(r2)

    stale_writes = []
    stale_op1 = _operation("op-1", r1, stale_writes)
    stale_op2 = _operation("op-2", r1, stale_writes)
    try:
        RegistryBoundDurableProductionOperationSequence((stale_op1, stale_op2), registry, checkpoint=completed.checkpoint)
    except ValueError as exc:
        rejection = str(exc)
    else:
        raise AssertionError("rehydrated stale sequence must fail closed")

    assert "stale Digital Twin revision" in rejection
    assert stale_writes == []

    print("ATLAS LIVE REHYDRATED REGISTRY STALE-REVISION SEQUENCE")
    print(json.dumps({
        "registry_snapshot_digest": snapshot["snapshot_digest"],
        "rejection": rejection,
        "continuation_writes": stale_writes,
    }, indent=2, sort_keys=True))
    print("ATLAS LIVE REHYDRATED REGISTRY STALE-REVISION ZERO-WRITE GATE: PASS")


if __name__ == "__main__":
    main()
