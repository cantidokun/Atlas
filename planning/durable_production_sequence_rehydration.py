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
        canonical_registry = DigitalTwinRegistry.from_snapshot(registry_snapshot)
        if canonical_registry.snapshot() != self.registry.snapshot():
            raise ValueError("registry snapshot does not match current canonical registry")
        checkpoint = DurableProductionSequenceCheckpoint.rehydrate(checkpoint_snapshot)
        bound = RegistryBoundDurableProductionOperationSequence(
            operations, self.registry, checkpoint=checkpoint
        )
        return bound
