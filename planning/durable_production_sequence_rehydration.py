"""Durable production sequence rehydration from canonical registry snapshots."""
from __future__ import annotations

from planning.digital_twin_registry import DigitalTwinRegistry
from planning.durable_production_operation_sequence import DurableProductionSequenceCheckpoint
from planning.registry_bound_durable_production_operation_sequence import (
    RegistryBoundDurableProductionOperationSequence,
)


class DurableProductionSequenceRehydrator:
    """Rehydrate a registry-bound production sequence from persisted snapshots."""

    def __init__(self, registry: DigitalTwinRegistry) -> None:
        if not isinstance(registry, DigitalTwinRegistry):
            raise TypeError("registry must be a DigitalTwinRegistry")
        self.registry = registry

    def rehydrate(self, operations, registry_snapshot, checkpoint_snapshot):
        if not isinstance(registry_snapshot, dict):
            raise TypeError("registry snapshot must be a mapping")
        try:
            canonical_registry = DigitalTwinRegistry.from_snapshot(registry_snapshot)
        except ValueError as exc:
            if "digest" in str(exc):
                raise ValueError("snapshot digest validation failed") from exc
            raise

        # Validate the persisted checkpoint before consulting the live registry
        # binding.  This keeps malformed checkpoint input fail-closed even when
        # callers deliberately bypass __init__ in contract tests.
        checkpoint = DurableProductionSequenceCheckpoint.rehydrate(checkpoint_snapshot)

        # A persisted checkpoint can legitimately reference an older registry
        # snapshot, but it must never resume against a newer canonical revision.
        # Classify that condition explicitly before the broader snapshot-equality
        # guard so callers can distinguish revision drift from snapshot mismatch.
        for receipt in checkpoint.completed_receipts:
            twin_id = receipt.get("twin_id")
            revision_id = receipt.get("revision_id")
            if twin_id and revision_id:
                current_revision = self.registry.canonical_revision(twin_id)
                if current_revision.revision_id != revision_id:
                    raise ValueError(
                        "durable sequence checkpoint is bound to a stale Digital Twin revision"
                    )

        if canonical_registry.snapshot() != self.registry.snapshot():
            raise ValueError("registry snapshot does not match current canonical registry")
        bound = RegistryBoundDurableProductionOperationSequence(
            operations, self.registry, checkpoint=checkpoint
        )
        return bound
