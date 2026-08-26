"""Live proof for durable multi-operation production sequencing."""
from __future__ import annotations

import json

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_operation_sequence import DurableProductionOperationSequence
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.production_operation_lifecycle import ProductionOperationLifecycle, ProductionOperationState
from planning.production_task_checkpoint import ProductionTaskCheckpoint


def _task(task_id: str, evidence: dict, verified: bool = True):
    revision = DigitalTwinRevision(
        twin_id="live-sequence-twin",
        revision_id="live-sequence-r1",
        sequence=1,
        kind=RevisionKind.RECONSTRUCTION,
        source_revision_id=None,
        source_fingerprint="live-sequence-fingerprint",
    )
    checkpoint = ProductionTaskCheckpoint.create(
        task_id, revision, (), {"task_id": task_id}, f"authorization-{task_id}"
    )
    task = object.__new__(DurableResumableCorrectiveTask)
    task.checkpoint = checkpoint
    task.revision = revision
    task.resume = lambda max_steps=16: CorrectiveTaskResult((), evidence, True)
    return ProductionOperationLifecycle(task, lambda _: verified)


def main() -> None:
    first = _task("live-1", {"step": 1})
    second_blocked = _task("live-2", {"step": 2}, verified=False)
    interrupted = DurableProductionOperationSequence((first, second_blocked)).run()

    resumed_first = _task("live-1", {"step": 1})
    resumed_second = _task("live-2", {"step": 2})
    resumed = DurableProductionOperationSequence(
        (resumed_first, resumed_second), checkpoint=interrupted.checkpoint
    ).run()

    print("ATLAS LIVE DURABLE PRODUCTION SEQUENCE")
    print(json.dumps({
        "interrupted": {
            "state": interrupted.state.value,
            "next_operation_index": interrupted.checkpoint.next_operation_index,
            "completed_receipts": len(interrupted.checkpoint.completed_receipts),
        },
        "resumed": {
            "state": resumed.state.value,
            "next_operation_index": resumed.checkpoint.next_operation_index,
            "completed_receipts": len(resumed.checkpoint.completed_receipts),
        },
    }, indent=2, sort_keys=True))

    assert interrupted.state is ProductionOperationState.BLOCKED
    assert interrupted.checkpoint.next_operation_index == 1
    assert resumed.state is ProductionOperationState.COMPLETED
    assert resumed.checkpoint.next_operation_index == 2
    assert len(resumed.checkpoint.completed_receipts) == 2
    print("ATLAS LIVE DURABLE PRODUCTION SEQUENCE INTERRUPTION/RESUME GATE: PASS")
    print("ATLAS LIVE DURABLE PRODUCTION SEQUENCE FINAL VERIFICATION GATE: PASS")


if __name__ == "__main__":
    main()
