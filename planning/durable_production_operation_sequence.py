"""Durable multi-operation production composition."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Callable, Iterable, Tuple

from planning.production_completion_receipt import ProductionCompletionReceipt
from planning.production_operation_lifecycle import (
    ProductionOperationLifecycle,
    ProductionOperationResult,
    ProductionOperationState,
)


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DurableProductionSequenceCheckpoint:
    completed_receipts: Tuple[dict[str, str], ...]
    next_operation_index: int
    sequence_digest: str

    @classmethod
    def create(cls, receipts: Iterable[ProductionCompletionReceipt], next_operation_index: int):
        values = tuple(receipt.snapshot() for receipt in receipts)
        return cls._from_snapshots(values, next_operation_index)

    @classmethod
    def _from_snapshots(cls, values: Tuple[dict[str, str], ...], next_operation_index: int):
        if isinstance(next_operation_index, bool) or not isinstance(next_operation_index, int):
            raise TypeError("next operation index must be an integer")
        if next_operation_index != len(values):
            raise ValueError("next operation index must equal completed receipt count")
        if next_operation_index < 0:
            raise ValueError("next operation index cannot be negative")
        payload = {"completed_receipts": values, "next_operation_index": next_operation_index}
        return cls(values, next_operation_index, _digest(payload))

    def snapshot(self) -> dict[str, Any]:
        payload = {"completed_receipts": self.completed_receipts, "next_operation_index": self.next_operation_index}
        if _digest(payload) != self.sequence_digest:
            raise ValueError("durable production sequence checkpoint integrity failure")
        return {**payload, "sequence_digest": self.sequence_digest}

    @classmethod
    def rehydrate(cls, snapshot: dict[str, Any]):
        if not isinstance(snapshot, dict):
            raise TypeError("sequence snapshot must be a mapping")
        required = {"completed_receipts", "next_operation_index", "sequence_digest"}
        if set(snapshot) != required:
            raise ValueError("invalid durable production sequence checkpoint")
        if isinstance(snapshot["next_operation_index"], bool) or not isinstance(snapshot["next_operation_index"], int):
            raise TypeError("next operation index must be an integer")
        receipts = tuple(snapshot["completed_receipts"])
        if not all(isinstance(receipt, dict) for receipt in receipts):
            raise ValueError("invalid completed receipt snapshot")
        for receipt in receipts:
            ProductionCompletionReceipt.from_snapshot(receipt)
        payload = {"completed_receipts": receipts, "next_operation_index": snapshot["next_operation_index"]}
        if _digest(payload) != snapshot["sequence_digest"]:
            raise ValueError("durable production sequence checkpoint integrity failure")
        if snapshot["next_operation_index"] != len(receipts):
            raise ValueError("next operation index does not match completed receipts")
        return cls(receipts, snapshot["next_operation_index"], snapshot["sequence_digest"])


@dataclass(frozen=True)
class DurableProductionSequenceResult:
    state: ProductionOperationState
    results: Tuple[ProductionOperationResult, ...]
    checkpoint: DurableProductionSequenceCheckpoint
    reason: str

    @property
    def completed(self) -> bool:
        return self.state is ProductionOperationState.COMPLETED


class DurableProductionOperationSequence:
    """Compose production operations with durable interruption/resume state."""

    def __init__(self, operations: Iterable[ProductionOperationLifecycle], checkpoint=None) -> None:
        values = tuple(operations)
        if not values:
            raise ValueError("operations must contain at least one production operation")
        if any(not isinstance(operation, ProductionOperationLifecycle) for operation in values):
            raise TypeError("operations must contain ProductionOperationLifecycle values")
        if checkpoint is not None:
            checkpoint = DurableProductionSequenceCheckpoint.rehydrate(checkpoint.snapshot())
            if checkpoint.next_operation_index > len(values):
                raise ValueError("checkpoint contains more completed operations than sequence")
        self.operations = values
        self.checkpoint = checkpoint or DurableProductionSequenceCheckpoint.create((), 0)

    @property
    def next_operation_index(self) -> int:
        return self.checkpoint.next_operation_index

    def run(
        self,
        max_steps: int = 16,
        checkpoint_sink: Callable[[DurableProductionSequenceCheckpoint], None] | None = None,
    ) -> DurableProductionSequenceResult:
        if checkpoint_sink is not None and not callable(checkpoint_sink):
            raise TypeError("checkpoint_sink must be callable")
        results = []
        receipt_snapshots = self.checkpoint.completed_receipts
        for operation_index in range(self.next_operation_index, len(self.operations)):
            result = self.operations[operation_index].run(max_steps=max_steps)
            results.append(result)
            if result.state is ProductionOperationState.BLOCKED or result.receipt is None:
                self.checkpoint = DurableProductionSequenceCheckpoint._from_snapshots(receipt_snapshots, operation_index)
                if checkpoint_sink is not None:
                    checkpoint_sink(self.checkpoint)
                return DurableProductionSequenceResult(
                    ProductionOperationState.BLOCKED,
                    tuple(results),
                    self.checkpoint,
                    f"durable production sequence blocked at step {operation_index + 1}: {result.reason}",
                )
            receipt_snapshots = receipt_snapshots + (result.receipt.snapshot(),)
            self.checkpoint = DurableProductionSequenceCheckpoint._from_snapshots(receipt_snapshots, operation_index + 1)
            if checkpoint_sink is not None:
                checkpoint_sink(self.checkpoint)
        return DurableProductionSequenceResult(
            ProductionOperationState.COMPLETED,
            tuple(results),
            self.checkpoint,
            "all production operations completed with authoritative verification",
        )
