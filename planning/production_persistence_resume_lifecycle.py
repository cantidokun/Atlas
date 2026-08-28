"""Production-facing restart boundary for persisted durable operation sequences."""
from __future__ import annotations

from typing import Any, Iterable

from planning.digital_twin_registry import DigitalTwinRegistry
from planning.durable_production_persistence import DurableProductionPersistenceBundle
from planning.durable_production_sequence_rehydration import DurableProductionSequenceRehydrator
from planning.production_resume_integrity_gate import (
    ProductionResumeCheckpoint,
    ProductionResumeRequest,
    validate_production_resume,
)
from planning.registry_bound_durable_production_operation_sequence import (
    RegistryBoundDurableProductionOperationSequence,
)


class ProductionPersistenceResumeLifecycle:
    """Load and resume a persisted production sequence against canonical registry state."""

    def __init__(self, registry: DigitalTwinRegistry, operations: Iterable[Any], bundle: DurableProductionPersistenceBundle, persistence_store: Any = None, resume_request: ProductionResumeRequest | None = None) -> None:
        if not isinstance(registry, DigitalTwinRegistry):
            raise TypeError("registry must be a DigitalTwinRegistry")
        if not isinstance(bundle, DurableProductionPersistenceBundle):
            raise TypeError("bundle must be a DurableProductionPersistenceBundle")
        if persistence_store is not None and not callable(getattr(persistence_store, "save", None)):
            raise TypeError("persistence_store must provide save(bundle)")
        if resume_request is not None and not isinstance(resume_request, ProductionResumeRequest):
            raise TypeError("resume_request must be a ProductionResumeRequest")
        self.registry = registry
        self.bundle = DurableProductionPersistenceBundle.from_snapshot(bundle.snapshot())
        self.persistence_store = persistence_store
        self.resume_request = resume_request
        # Resume identity and canonical revision are validated before rehydration.
        # This ensures a resume request fails at the production restart boundary,
        # rather than being obscured by the lower-level registry snapshot guard.
        if self.resume_request is not None:
            self._validate_resume_request(self.resume_request)
        self.sequence: RegistryBoundDurableProductionOperationSequence = DurableProductionSequenceRehydrator(registry).rehydrate(tuple(operations), self.bundle)

    @classmethod
    def from_bundle(cls, registry: DigitalTwinRegistry, operations: Iterable[Any], bundle: DurableProductionPersistenceBundle, persistence_store: Any = None, resume_request: ProductionResumeRequest | None = None) -> "ProductionPersistenceResumeLifecycle":
        return cls(registry, operations, bundle, persistence_store=persistence_store, resume_request=resume_request)

    @classmethod
    def from_persistence_store(cls, registry: DigitalTwinRegistry, operations: Iterable[Any], store: Any, resume_request: ProductionResumeRequest | None = None) -> "ProductionPersistenceResumeLifecycle":
        bundle = store.load()
        return cls(registry, operations, bundle, persistence_store=store, resume_request=resume_request)

    @property
    def checkpoint(self):
        return self.sequence.checkpoint

    @property
    def next_operation_index(self) -> int:
        return self.sequence.next_operation_index

    def _resume_checkpoint(self) -> ProductionResumeCheckpoint:
        identity = self.bundle.resume_identity
        if not isinstance(identity, dict):
            raise ValueError("persisted resume identity is incomplete")
        return ProductionResumeCheckpoint(
            sequence_id=identity["sequence_id"],
            plan_id=identity["plan_id"],
            digital_twin_revision=identity["digital_twin_revision"],
            completed_operation_index=self.next_operation_index - 1 if hasattr(self, "sequence") else -1,
        )

    def _validate_canonical_resume_revision(self) -> None:
        identity = self.bundle.resume_identity
        if not isinstance(identity, dict):
            raise ValueError("persisted resume identity is incomplete")
        target_revision_id = identity["digital_twin_revision"]
        matches = [
            revision
            for twin_id in self.registry._revisions
            for revision in self.registry.revisions(twin_id)
            if revision.revision_id == target_revision_id
        ]
        if not matches:
            raise ValueError("persisted resume Digital Twin revision is not canonical")
        if len(matches) != 1:
            raise ValueError("persisted resume Digital Twin revision is ambiguous")
        try:
            self.registry.require_canonical_revision(matches[0])
        except ValueError as exc:
            raise ValueError("persisted resume Digital Twin revision is not the current canonical revision") from exc

    def _validate_resume_request(self, request: ProductionResumeRequest) -> None:
        validate_production_resume(self._resume_checkpoint(), request)
        self._validate_canonical_resume_revision()

    def validate_resume(self, request: ProductionResumeRequest) -> None:
        """Validate a requested restart without executing production work."""
        if not isinstance(request, ProductionResumeRequest):
            raise TypeError("request must be a ProductionResumeRequest")
        self._validate_resume_request(request)

    def _persist_checkpoint(self, checkpoint) -> None:
        if self.persistence_store is None:
            return
        bundle = DurableProductionPersistenceBundle.create(
            self.registry,
            checkpoint,
            resume_identity=self.bundle.resume_identity,
        )
        self.persistence_store.save(bundle)
        self.bundle = bundle

    def run(self, max_steps: int = 16):
        if self.resume_request is not None:
            self._validate_resume_request(self.resume_request)
        return self.sequence.run(max_steps=max_steps, checkpoint_sink=self._persist_checkpoint if self.persistence_store is not None else None)
