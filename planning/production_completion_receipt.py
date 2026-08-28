"""Immutable receipt binding production completion to authoritative evidence."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from planning.digital_twin_revision import DigitalTwinRevision
from planning.production_task_checkpoint import ProductionTaskCheckpoint


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProductionCompletionReceipt:
    task_id: str
    twin_id: str
    revision_id: str
    checkpoint_digest: str
    evidence_digest: str

    @classmethod
    def create(
        cls,
        checkpoint: ProductionTaskCheckpoint,
        revision: DigitalTwinRevision,
        final_evidence: Any,
    ) -> "ProductionCompletionReceipt":
        if not isinstance(checkpoint, ProductionTaskCheckpoint):
            raise TypeError("checkpoint must be a ProductionTaskCheckpoint")
        if not isinstance(revision, DigitalTwinRevision):
            raise TypeError("revision must be a DigitalTwinRevision")
        if checkpoint.twin_id != revision.twin_id or checkpoint.revision_id != revision.revision_id:
            raise ValueError("completion receipt revision does not match checkpoint")
        return cls(
            task_id=checkpoint.task_id,
            twin_id=revision.twin_id,
            revision_id=revision.revision_id,
            checkpoint_digest=checkpoint.checkpoint_digest,
            evidence_digest=_digest(final_evidence),
        )

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, str]) -> "ProductionCompletionReceipt":
        """Rehydrate only an intact, structurally valid completion receipt."""
        if not isinstance(snapshot, Mapping):
            raise TypeError("completion receipt snapshot must be a mapping")
        required = {
            "task_id",
            "twin_id",
            "revision_id",
            "checkpoint_digest",
            "evidence_digest",
            "receipt_digest",
        }
        if set(snapshot) != required:
            raise ValueError("invalid completion receipt snapshot")
        payload = {key: snapshot[key] for key in required if key != "receipt_digest"}
        if not all(isinstance(value, str) for value in payload.values()):
            raise ValueError("completion receipt fields must be strings")
        if _digest(payload) != snapshot["receipt_digest"]:
            raise ValueError("completion receipt snapshot digest validation failed")
        return cls(
            task_id=snapshot["task_id"],
            twin_id=snapshot["twin_id"],
            revision_id=snapshot["revision_id"],
            checkpoint_digest=snapshot["checkpoint_digest"],
            evidence_digest=snapshot["evidence_digest"],
        )

    def matches(self, checkpoint: ProductionTaskCheckpoint, revision: DigitalTwinRevision, final_evidence: Any) -> bool:
        return (
            checkpoint.task_id == self.task_id
            and checkpoint.twin_id == self.twin_id
            and checkpoint.revision_id == self.revision_id
            and checkpoint.checkpoint_digest == self.checkpoint_digest
            and revision.twin_id == self.twin_id
            and revision.revision_id == self.revision_id
            and _digest(final_evidence) == self.evidence_digest
        )

    def snapshot(self) -> dict[str, str]:
        payload = {
            "task_id": self.task_id,
            "twin_id": self.twin_id,
            "revision_id": self.revision_id,
            "checkpoint_digest": self.checkpoint_digest,
            "evidence_digest": self.evidence_digest,
        }
        return {**payload, "receipt_digest": _digest(payload)}
