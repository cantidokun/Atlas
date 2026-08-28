"""Production-facing restart boundary for persisted durable operation sequences."""
from __future__ import annotations

from typing import Any, Iterable

from planning.digital_twin_registry import DigitalTwinRegistry
from planning.durable_production_persistence import DurableProductionPersistenceBundle
from planning.durable_production_sequence_rehydration import DurableProductionSequenceRehydrator
from planning.registry_bound_durable_production_operation_sequence import (
    RegistryBoundDurableProductionOperationSequence,
)


class ProductionPersistenceResumeLifecycle:
    """Load and resume a persisted production sequence against canonical registry state."""

    def __init__(
        self,
        registry: DigitalTwinRegistry,
        operations: Iterable[Any],
        bundle: DurableProductionPersistenceBundle,
    ) -> None:
        if not isinstance(registry, DigitalTwinRegistry):
            raise TypeError("registry must be a DigitalTwinRegistry")
        if not isinstance(bundle, DurableProductionPersistenceBundle):
            raise TypeError("bundle must be a DurableProductionPersistenceBundle")
        self.registry = registry
        self.bundle = DurableProductionPersistenceBundle.from_snapshot(bundle.snapshot())
        self.sequence: RegistryBoundDurableProductionOperationSequence = (
            DurableProductionSequenceRehydrator(registry).rehydrate(
                tuple(operations), self.bundle
            )
        )

    @classmethod
    def from_bundle(
        cls,
        registry: DigitalTwinRegistry,
        operations: Iterable[Any],
        bundle: DurableProductionPersistenceBundle,
    ) -> "ProductionPersistenceResumeLifecycle":
        return cls(registry, operations, bundle)

    @classmethod
    def from_persistence_store(
        cls,
        registry: DigitalTwinRegistry,
        operations: Iterable[Any],
        store: Any,
    ) -> "ProductionPersistenceResumeLifecycle":
        bundle = store.load()
        return cls(registry, operations, bundle)

    @property
    def checkpoint(self):
        return self.sequence.checkpoint

    @property
    def next_operation_index(self) -> int:
        return self.sequence.next_operation_index

    def run(self, max_steps: int = 16):
        return self.sequence.run(max_steps=max_steps)
