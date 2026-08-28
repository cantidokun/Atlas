"""Validated persistence bundle for durable production sequence restart state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from planning.digital_twin_registry import DigitalTwinRegistry
from planning.durable_production_operation_sequence import DurableProductionSequenceCheckpoint


@dataclass(frozen=True)
class DurableProductionPersistenceBundle:
    """Canonical persisted registry/checkpoint pair used for restart."""

    registry_snapshot: dict[str, Any]
    checkpoint_snapshot: dict[str, Any]

    @classmethod
    def create(
        cls,
        registry: DigitalTwinRegistry,
        checkpoint: DurableProductionSequenceCheckpoint,
    ) -> "DurableProductionPersistenceBundle":
        if not isinstance(registry, DigitalTwinRegistry):
            raise TypeError("registry must be a DigitalTwinRegistry")
        if not isinstance(checkpoint, DurableProductionSequenceCheckpoint):
            raise TypeError("checkpoint must be a DurableProductionSequenceCheckpoint")
        return cls(registry.snapshot(), checkpoint.snapshot())

    def snapshot(self) -> dict[str, Any]:
        """Return the exact persisted pair after revalidating both components."""
        registry_snapshot = dict(self.registry_snapshot)
        checkpoint_snapshot = dict(self.checkpoint_snapshot)
        DigitalTwinRegistry.from_snapshot(registry_snapshot)
        DurableProductionSequenceCheckpoint.rehydrate(checkpoint_snapshot)
        return {
            "registry_snapshot": registry_snapshot,
            "checkpoint_snapshot": checkpoint_snapshot,
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any]) -> "DurableProductionPersistenceBundle":
        if not isinstance(snapshot, Mapping):
            raise TypeError("persistence bundle must be a mapping")
        required = {"registry_snapshot", "checkpoint_snapshot"}
        if set(snapshot) != required:
            raise ValueError("invalid durable production persistence bundle")
        registry_snapshot = snapshot["registry_snapshot"]
        checkpoint_snapshot = snapshot["checkpoint_snapshot"]
        if not isinstance(registry_snapshot, dict):
            raise TypeError("registry snapshot must be a mapping")
        if not isinstance(checkpoint_snapshot, dict):
            raise TypeError("checkpoint snapshot must be a mapping")
        try:
            DigitalTwinRegistry.from_snapshot(registry_snapshot)
        except ValueError as exc:
            if "digest" in str(exc):
                raise ValueError("persistence bundle registry snapshot digest validation failed") from exc
            raise
        DurableProductionSequenceCheckpoint.rehydrate(checkpoint_snapshot)
        return cls(dict(registry_snapshot), dict(checkpoint_snapshot))
