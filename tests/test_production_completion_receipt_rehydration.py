from __future__ import annotations

import hashlib
import json

import pytest

from planning.durable_production_operation_sequence import DurableProductionSequenceCheckpoint
from planning.production_completion_receipt import ProductionCompletionReceipt


def _digest(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _receipt_snapshot():
    return {
        "task_id": "task-1",
        "twin_id": "twin-1",
        "revision_id": "r1",
        "checkpoint_digest": "checkpoint-1",
        "evidence_digest": "evidence-1",
        "receipt_digest": _digest(
            {
                "task_id": "task-1",
                "twin_id": "twin-1",
                "revision_id": "r1",
                "checkpoint_digest": "checkpoint-1",
                "evidence_digest": "evidence-1",
            }
        ),
    }


def test_completion_receipt_snapshot_round_trip_is_stable():
    snapshot = _receipt_snapshot()
    receipt = ProductionCompletionReceipt.from_snapshot(snapshot)

    assert receipt.snapshot() == snapshot


def test_sequence_rehydration_rejects_receipt_tampering_even_with_recomputed_sequence_digest():
    receipt = _receipt_snapshot()
    receipt["evidence_digest"] = "tampered-evidence"
    checkpoint_payload = {
        "completed_receipts": [receipt],
        "next_operation_index": 1,
    }
    snapshot = {
        **checkpoint_payload,
        "sequence_digest": _digest(checkpoint_payload),
    }

    with pytest.raises(ValueError, match="receipt.*digest"):
        DurableProductionSequenceCheckpoint.rehydrate(snapshot)
