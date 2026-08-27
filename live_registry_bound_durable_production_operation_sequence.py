"""Live stale-revision zero-write proof for registry-bound durable sequencing."""
from __future__ import annotations

import json

from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.production_operation_lifecycle import ProductionOperationLifecycle, ProductionOperationState
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.registry_bound_durable_production_operation_sequence import RegistryBoundDurableProductionOperationSequence
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.autonomous_corrective_task import CorrectiveTaskResult


def _revision(revision_id: str) -> DigitalTwinRevision:
    return DigitalTwinRevision(
        twin_id="live-registry-sequence-twin",
        revision_id=revision_id,
        sequence=1,
        kind=RevisionKind.RECONSTRUCTION,
        source_revision_id=None,
        source_fingerprint="live-registry-sequence-fingerprint",
    )


def _operation(task_id: str, revision: DigitalTwinRevision, writes: list[str]):
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
    return ProductionOperationLifecycle(task, lambda _: True)


def main() -> None:
    registry = DigitalTwinRegistry()
    canonical = _revision("live-r1")
    advanced = _revision("live-r2")
    registry.register_revision(canonical)
    registry.promote_revision(canonical)

    writes: list[str] = []
    first = _operation("live-registry-1", canonical, writes)
    second = _operation("live-registry-2", canonical, writes)
    sequence = RegistryBoundDurableProductionOperationSequence((first, second), registry)
    result = sequence.run()
    assert result.state is ProductionOperationState.COMPLETED
    assert writes == ["live-registry-1", "live-registry-2"]

    registry.register_revision(advanced)
    registry.promote_revision(advanced)

    stale_writes: list[str] = []
    stale_first = _operation("stale-1", canonical, stale_writes)
    stale_second = _operation("stale-2", canonical, stale_writes)
    try:
        RegistryBoundDurableProductionOperationSequence(
            (stale_first, stale_second), registry, checkpoint=result.checkpoint
        )
    except ValueError as exc:
        rejection = str(exc)
    else:
        raise AssertionError("stale registry revision must fail closed")

    assert "stale Digital Twin revision" in rejection
    assert stale_writes == []

    print("ATLAS LIVE REGISTRY-BOUND DURABLE PRODUCTION SEQUENCE")
    print(json.dumps({
        "canonical_completion": result.state.value,
        "canonical_writes": writes,
        "stale_revision_rejection": rejection,
        "stale_revision_writes": stale_writes,
    }, indent=2, sort_keys=True))
    print("ATLAS LIVE REGISTRY-BOUND STALE-REVISION ZERO-WRITE GATE: PASS")


if __name__ == "__main__":
    main()
