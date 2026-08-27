from __future__ import annotations

import pytest

from planning.durable_production_operation_sequence import DurableProductionSequenceCheckpoint
from planning.production_completion_receipt import ProductionCompletionReceipt


def test_rehydrated_checkpoint_rejects_receipt_order_tampering():
    receipt = ProductionCompletionReceipt(
        operation_id="op-1",
        task_id="task-1",
        twin_id="twin-1",
        revision_id="r1",
        result_digest="digest-1",
    )
    checkpoint = DurableProductionSequenceCheckpoint.create((receipt,), 1)
    snapshot = checkpoint.snapshot()
    snapshot["completed_receipts"] = ({**snapshot["completed_receipts"][0], "task_id": "tampered"},)
    with pytest.raises(ValueError, match="integrity failure"):
        DurableProductionSequenceCheckpoint.rehydrate(snapshot)


def test_checkpoint_rejects_negative_next_operation_index():
    with pytest.raises(ValueError, match="cannot be negative"):
        DurableProductionSequenceCheckpoint._from_snapshots((), -1)


def test_checkpoint_snapshot_preserves_completed_receipt_count():
    receipt = ProductionCompletionReceipt(
        operation_id="op-1",
        task_id="task-1",
        twin_id="twin-1",
        revision_id="r1",
        result_digest="digest-1",
    )
    checkpoint = DurableProductionSequenceCheckpoint.create((receipt,), 1)
    restored = DurableProductionSequenceCheckpoint.rehydrate(checkpoint.snapshot())
    assert restored.next_operation_index == 1
    assert len(restored.completed_receipts) == 1
