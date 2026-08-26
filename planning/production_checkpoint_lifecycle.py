"""Production-facing durable checkpoint lifecycle.

A checkpoint is created only against the current canonical Digital Twin revision.
It is audit/progress state, never a reusable execution credential. Reloading a
checkpoint revalidates both its immutable digest and the registry's canonical
revision before the checkpoint can enter the durable resume boundary.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

from action_plan import ActionSpec
from planning.digital_twin_revision import DigitalTwinRevision
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.digital_twin_registry import DigitalTwinRegistry


class ProductionCheckpointLifecycle:
    def __init__(self, registry: DigitalTwinRegistry) -> None:
        if not isinstance(registry, DigitalTwinRegistry):
            raise TypeError("registry must be a DigitalTwinRegistry")
        self.registry = registry

    def validate_checkpoint(
        self,
        checkpoint: ProductionTaskCheckpoint,
        revision: DigitalTwinRevision,
    ) -> ProductionTaskCheckpoint:
        """Validate an in-memory checkpoint before it enters a resume boundary."""
        if not isinstance(checkpoint, ProductionTaskCheckpoint):
            raise TypeError("checkpoint must be a ProductionTaskCheckpoint")
        self.registry.require_canonical_revision(revision)
        if checkpoint.twin_id != revision.twin_id:
            raise ValueError("checkpoint belongs to a different Digital Twin")
        if checkpoint.revision_id != revision.revision_id:
            raise ValueError("checkpoint belongs to a different Digital Twin revision")
        restored = ProductionTaskCheckpoint.from_snapshot(checkpoint.snapshot(), revision)
        if restored.checkpoint_digest != checkpoint.checkpoint_digest:
            raise ValueError("checkpoint integrity does not match its contents")
        return restored

    def create_checkpoint(
        self,
        task_id: str,
        revision: DigitalTwinRevision,
        completed_actions: Tuple[ActionSpec, ...],
        evidence: Any,
        authorization_id: str,
        parent_checkpoint_digest: Optional[str] = None,
    ) -> ProductionTaskCheckpoint:
        self.registry.require_canonical_revision(revision)
        return ProductionTaskCheckpoint.create(
            task_id,
            revision,
            completed_actions,
            evidence,
            authorization_id,
            parent_checkpoint_digest=parent_checkpoint_digest,
        )

    def serialize_checkpoint(self, checkpoint: ProductionTaskCheckpoint) -> dict[str, Any]:
        canonical = self.registry.canonical_revision(checkpoint.twin_id)
        self.registry.require_canonical_revision(canonical)
        if checkpoint.revision_id != canonical.revision_id:
            raise ValueError("checkpoint revision is not the current canonical Digital Twin revision")
        return checkpoint.snapshot()

    def rehydrate_checkpoint(
        self,
        snapshot: Mapping[str, Any],
        revision: DigitalTwinRevision,
    ) -> ProductionTaskCheckpoint:
        self.registry.require_canonical_revision(revision)
        return ProductionTaskCheckpoint.from_snapshot(snapshot, revision)
