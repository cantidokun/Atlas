from __future__ import annotations

import pytest

from planning.durable_production_operation_sequence import DurableProductionSequenceCheckpoint
from planning.production_completion_receipt import ProductionCompletionReceipt
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind


def _revision() -> DigitalTwinRevision:
    return DigitalTwinRevision(
        "twin-1", "r1", 1, RevisionKind.RECONSTRUCTION, None, "fingerprint"
    )


def _receipt() -> ProductionCompletionReceipt:
    revision = _revision()
    checkpoint = ProductionTaskCheckpoint.create(
        "task-1", revision, (), {"done": True}, "auth-1"
    )
    return ProductionCompletionReceipt.create(checkpoint, revision, {"done": True})


def test_rehydrated_checkpoint_rejects_receipt_order_tampering():
    receipt = _receipt()
    checkpoint = DurableProductionSequenceCheckpoint.create((receipt,), 1)
    snapshot = checkpoint.snapshot()
    receipt_snapshot = dict(snapshot["completed_receipts"][0])
    receipt_snapshot["task_id"] = "tampered"
    snapshot["completed_receipts"] = (receipt_snapshot,)
    with pytest.raises(ValueError, match="integrity failure"):
        DurableProductionSequenceCheckpoint.rehydrate(snapshot)


def test_checkpoint_rejects_negative_next_operation_index():
    with pytest.raises(ValueError, match="must equal completed receipt count"):
        DurableProductionSequenceCheckpoint._from_snapshots((), -1)


def test_checkpoint_snapshot_preserves_completed_receipt_count():
    checkpoint = DurableProductionSequenceCheckpoint.create((_receipt(),), 1)
    restored = DurableProductionSequenceCheckpoint.rehydrate(checkpoint.snapshot())
    assert restored.next_operation_index == 1
    assert len(restored.completed_receipts) == 1


def test_rehydrated_checkpoint_rejects_boolean_next_operation_index():
    receipt = _receipt()
    checkpoint = DurableProductionSequenceCheckpoint.create((receipt,), 1)
    snapshot = checkpoint.snapshot()
    snapshot["next_operation_index"] = True
    with pytest.raises(TypeError, match="next operation index must be an integer"):
        DurableProductionSequenceCheckpoint.rehydrate(snapshot)


def test_checkpoint_creation_rejects_boolean_next_operation_index():
    with pytest.raises(TypeError, match="next operation index must be an integer"):
        DurableProductionSequenceCheckpoint.create((), False)
