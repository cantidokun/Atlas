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
        persistence_store: Any = None,
    ) -> None:
        if not isinstance(registry, DigitalTwinRegistry):
            raise TypeError("registry must be a DigitalTwinRegistry")
        if not isinstance(bundle, DurableProductionPersistenceBundle):
            raise TypeError("bundle must be a DurableProductionPersistenceBundle")
        if persistence_store is not None and not callable(getattr(persistence_store, "save", None)):
            raise TypeError("persistence_store must provide save(bundle)")
        self.registry = registry
        self.bundle = DurableProductionPersistenceBundle.from_snapshot(bundle.snapshot())
        self.persistence_store = persistence_store
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
        persistence_store: Any = None,
    ) -> "ProductionPersistenceResumeLifecycle":
        return cls(registry, operations, bundle, persistence_store=persistence_store)

    @classmethod
    def from_persistence_store(
        cls,
        registry: DigitalTwinRegistry,
        operations: Iterable[Any],
        store: Any,
    ) -> "ProductionPersistenceResumeLifecycle":
        bundle = store.load()
        return cls(registry, operations, bundle, persistence_store=store)

    @property
    def checkpoint(self):
        return self.sequence.checkpoint

    @property
    def next_operation_index(self) -> int:
        return self.sequence.next_operation_index

    def _persist_checkpoint(self, checkpoint) -> None:
        if self.persistence_store is None:
            return
        bundle = DurableProductionPersistenceBundle.create(self.registry, checkpoint)
        self.persistence_store.save(bundle)
        self.bundle = bundle

    def run(self, max_steps: int = 16):
        return self.sequence.run(
            max_steps=max_steps,
            checkpoint_sink=self._persist_checkpoint if self.persistence_store is not None else None,
        )
