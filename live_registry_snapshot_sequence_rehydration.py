"""Live proof of durable production sequence rehydration from a registry snapshot."""
from __future__ import annotations

import json

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_operation_sequence import DurableProductionOperationSequence
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.production_operation_lifecycle import ProductionOperationLifecycle, ProductionOperationState
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.registry_bound_durable_production_operation_sequence import RegistryBoundDurableProductionOperationSequence


def _identity() -> DigitalTwinIdentity:
    return DigitalTwinIdentity(
        "live-snapshot-twin",
        "soccer-field",
        (IdentityAnchor("capture", "source", "live-snapshot"),),
    )


def _revision(identity: DigitalTwinIdentity, revision_id: str, sequence: int) -> DigitalTwinRevision:
    return DigitalTwinRevision(
        identity.twin_id,
        revision_id,
        sequence,
        RevisionKind.RECONSTRUCTION,
        None if sequence == 1 else f"r{sequence - 1}",
        identity.stable_fingerprint(),
    )


def _operation(task_id: str, revision: DigitalTwinRevision, writes: list[str], verified: bool = True):
    checkpoint = ProductionTaskCheckpoint.create(
        task_id, revision, (), {"task_id": task_id}, f"authorization-{task_id}"
    )
    task = object.__new__(DurableResumableCorrectiveTask)
    task.checkpoint = checkpoint
    task.revision = revision

    def resume(max_steps=16):
        writes.append(task_id)
        return CorrectiveTaskResult((), {"task_id": task_id}, True)

    task.resume = resume
    return ProductionOperationLifecycle(task, lambda _: verified)


def main() -> None:
    identity = _identity()
    registry = DigitalTwinRegistry()
    r1 = _revision(identity, "r1", 1)
    registry.register_identity(identity)
    registry.register_revision(r1)

    writes: list[str] = []
    first = _operation("sequence-1", r1, writes)
    second = _operation("sequence-2", r1, writes, verified=False)
    interrupted = RegistryBoundDurableProductionOperationSequence((first, second), registry).run()
    assert interrupted.state is ProductionOperationState.BLOCKED
    assert interrupted.checkpoint.next_operation_index == 1
    assert len(writes) == 2

    registry_snapshot = registry.snapshot()
    rehydrated_registry = DigitalTwinRegistry.from_snapshot(registry_snapshot)

    resumed_writes: list[str] = []
    resumed_first = _operation("sequence-1", r1, resumed_writes)
    resumed_second = _operation("sequence-2", r1, resumed_writes)
    resumed = RegistryBoundDurableProductionOperationSequence(
        (resumed_first, resumed_second), rehydrated_registry, checkpoint=interrupted.checkpoint
    ).run()

    assert resumed.state is ProductionOperationState.COMPLETED
    assert resumed.checkpoint.next_operation_index == 2
    assert resumed_writes == ["sequence-2"]

    tampered = dict(registry_snapshot)
    tampered["snapshot_digest"] = "tampered"
    try:
        DigitalTwinRegistry.from_snapshot(tampered)
    except ValueError as exc:
        tamper_rejection = str(exc)
    else:
        raise AssertionError("tampered registry snapshot must fail closed")

    print("ATLAS LIVE REGISTRY SNAPSHOT DURABLE SEQUENCE REHYDRATION")
    print(json.dumps({
        "interrupted_state": interrupted.state.value,
        "interrupted_next_operation_index": interrupted.checkpoint.next_operation_index,
        "resumed_state": resumed.state.value,
        "resumed_next_operation_index": resumed.checkpoint.next_operation_index,
        "resumed_writes": resumed_writes,
        "tamper_rejection": tamper_rejection,
    }, indent=2, sort_keys=True))
    print("ATLAS LIVE REGISTRY SNAPSHOT REHYDRATION GATE: PASS")
    print("ATLAS LIVE REGISTRY SNAPSHOT TAMPER FAIL-CLOSED GATE: PASS")


if __name__ == "__main__":
    main()
