"""Immutable receipt binding production completion to authoritative evidence."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

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
