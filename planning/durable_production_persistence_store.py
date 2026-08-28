"""Process-boundary store for validated durable production restart state."""
from __future__ import annotations

from typing import Any, Mapping

from planning.durable_production_persistence import DurableProductionPersistenceBundle


class InMemoryDurableProductionPersistenceStore:
    """Small deterministic persistence seam used by production orchestration tests."""

    def __init__(self) -> None:
        self._snapshot: dict[str, Any] | None = None

    def save(self, bundle: DurableProductionPersistenceBundle) -> None:
        if not isinstance(bundle, DurableProductionPersistenceBundle):
            raise TypeError("bundle must be a DurableProductionPersistenceBundle")
        # Validate before replacement so a failed save cannot destroy the last
        # known-good restart point.
        snapshot = bundle.snapshot()
        self._snapshot = snapshot

    def load(self) -> DurableProductionPersistenceBundle:
        if self._snapshot is None:
            raise LookupError("no durable production persistence state is available")
        return DurableProductionPersistenceBundle.from_snapshot(self._snapshot)

    def snapshot(self) -> Mapping[str, Any] | None:
        if self._snapshot is None:
            return None
        snapshot = {
            "registry_snapshot": dict(self._snapshot["registry_snapshot"]),
            "checkpoint_snapshot": dict(self._snapshot["checkpoint_snapshot"]),
        }
        if "resume_identity" in self._snapshot:
            snapshot["resume_identity"] = dict(self._snapshot["resume_identity"])
            snapshot["resume_identity_digest"] = self._snapshot["resume_identity_digest"]
        return snapshot
