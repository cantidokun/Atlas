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
        parent_checkpoint: Optional[ProductionTaskCheckpoint] = None,
    ) -> ProductionTaskCheckpoint:
        """Create a checkpoint with optional validated parent lineage."""
        self.registry.require_canonical_revision(revision)
        if parent_checkpoint is not None:
            validated_parent = self.validate_checkpoint(parent_checkpoint, revision)
            parent_checkpoint_digest = validated_parent.checkpoint_digest
        elif parent_checkpoint_digest is not None:
            if not isinstance(parent_checkpoint_digest, str) or not parent_checkpoint_digest.strip():
                raise ValueError("parent_checkpoint_digest must be a non-empty string when supplied")
        return ProductionTaskCheckpoint.create(
            task_id,
            revision,
            completed_actions,
            evidence,
            authorization_id,
            parent_checkpoint_digest=parent_checkpoint_digest,
        )

    def serialize_checkpoint(self, checkpoint: ProductionTaskCheckpoint) -> dict[str, Any]:
        """Serialize only a current, internally consistent checkpoint."""
        if not isinstance(checkpoint, ProductionTaskCheckpoint):
            raise TypeError("checkpoint must be a ProductionTaskCheckpoint")
        canonical = self.registry.canonical_revision(checkpoint.twin_id)
        self.registry.require_canonical_revision(canonical)
        if checkpoint.revision_id != canonical.revision_id:
            raise ValueError("checkpoint revision is not the current canonical Digital Twin revision")
        validated = self.validate_checkpoint(checkpoint, canonical)
        return validated.snapshot()

    def rehydrate_checkpoint(
        self,
        snapshot: Mapping[str, Any],
        revision: DigitalTwinRevision,
    ) -> ProductionTaskCheckpoint:
        self.registry.require_canonical_revision(revision)
        return ProductionTaskCheckpoint.from_snapshot(snapshot, revision)

    def validate_parent_lineage(
        self,
        checkpoint: ProductionTaskCheckpoint,
        parent_checkpoint: ProductionTaskCheckpoint,
    ) -> ProductionTaskCheckpoint:
        """Require a checkpoint's declared parent to be the exact prior checkpoint."""
        if not isinstance(checkpoint, ProductionTaskCheckpoint):
            raise TypeError("checkpoint must be a ProductionTaskCheckpoint")
        parent = self.validate_checkpoint(parent_checkpoint, self.registry.canonical_revision(parent_checkpoint.twin_id))
        if checkpoint.parent_checkpoint_digest != parent.checkpoint_digest:
            raise ValueError("checkpoint parent lineage does not match the referenced parent checkpoint")
        if checkpoint.twin_id != parent.twin_id:
            raise ValueError("checkpoint parent belongs to a different Digital Twin")
        if checkpoint.revision_id != parent.revision_id:
            raise ValueError("checkpoint parent belongs to a different Digital Twin revision")
        return parent
