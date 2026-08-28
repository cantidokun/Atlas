"""Process-boundary persistence store for validated durable production state."""
from __future__ import annotations

from typing import Any, Mapping

from planning.durable_production_persistence import DurableProductionPersistenceBundle


class InMemoryDurableProductionPersistenceStore:
    """Small deterministic persistence seam used by production orchestration tests.

    A save validates the complete bundle before replacing the last known-good state.
    The store never exposes its internal mutable copy directly.
    """

    def __init__(self) -> None:
        self._snapshot: dict[str, Any] | None = None

    def save(self, bundle: DurableProductionPersistenceBundle) -> None:
        if not isinstance(bundle, DurableProductionPersistenceBundle):
            raise TypeError("persistence bundle must be a DurableProductionPersistenceBundle")
        snapshot = bundle.snapshot()
        self._snapshot = {
            "registry_snapshot": dict(snapshot["registry_snapshot"]),
            "checkpoint_snapshot": dict(snapshot["checkpoint_snapshot"]),
        }
        if "resume_identity" in snapshot:
            self._snapshot["resume_identity"] = dict(snapshot["resume_identity"])

    def load(self) -> DurableProductionPersistenceBundle:
        if self._snapshot is None:
            raise ValueError("no durable production persistence state")
        return DurableProductionPersistenceBundle.from_snapshot(self.snapshot())

    def snapshot(self) -> Mapping[str, Any]:
        if self._snapshot is None:
            raise ValueError("no durable production persistence state")
        result = {
            "registry_snapshot": dict(self._snapshot["registry_snapshot"]),
            "checkpoint_snapshot": dict(self._snapshot["checkpoint_snapshot"]),
        }
        if "resume_identity" in self._snapshot:
            result["resume_identity"] = dict(self._snapshot["resume_identity"])
        return result
