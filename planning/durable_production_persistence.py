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
    resume_identity: dict[str, str] | None = None

    @classmethod
    def create(
        cls,
        registry: DigitalTwinRegistry,
        checkpoint: DurableProductionSequenceCheckpoint,
        resume_identity: Mapping[str, str] | None = None,
    ) -> "DurableProductionPersistenceBundle":
        if not isinstance(registry, DigitalTwinRegistry):
            raise TypeError("registry must be a DigitalTwinRegistry")
        if not isinstance(checkpoint, DurableProductionSequenceCheckpoint):
            raise TypeError("checkpoint must be a DurableProductionSequenceCheckpoint")
        normalized_identity = None
        if resume_identity is not None:
            if not isinstance(resume_identity, Mapping):
                raise TypeError("resume_identity must be a mapping")
            required = {"sequence_id", "plan_id", "digital_twin_revision"}
            if set(resume_identity) != required or not all(
                isinstance(value, str) and value.strip() for value in resume_identity.values()
            ):
                raise ValueError("resume_identity must contain non-empty sequence_id, plan_id, and digital_twin_revision")
            normalized_identity = {key: str(resume_identity[key]) for key in sorted(required)}
        return cls(registry.snapshot(), checkpoint.snapshot(), normalized_identity)

    def snapshot(self) -> dict[str, Any]:
        """Return the exact persisted state after revalidating every component."""
        registry_snapshot = dict(self.registry_snapshot)
        checkpoint_snapshot = dict(self.checkpoint_snapshot)
        DigitalTwinRegistry.from_snapshot(registry_snapshot)
        DurableProductionSequenceCheckpoint.rehydrate(checkpoint_snapshot)
        result = {
            "registry_snapshot": registry_snapshot,
            "checkpoint_snapshot": checkpoint_snapshot,
        }
        if self.resume_identity is not None:
            result["resume_identity"] = dict(self.resume_identity)
        return result

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any]) -> "DurableProductionPersistenceBundle":
        if not isinstance(snapshot, Mapping):
            raise TypeError("persistence bundle must be a mapping")
        required = {"registry_snapshot", "checkpoint_snapshot"}
        if not required.issubset(snapshot) or set(snapshot) - required - {"resume_identity"}:
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

        resume_identity = snapshot.get("resume_identity")
        normalized_identity = None
        if resume_identity is not None:
            if not isinstance(resume_identity, Mapping):
                raise TypeError("resume_identity must be a mapping")
            required_identity = {"sequence_id", "plan_id", "digital_twin_revision"}
            if set(resume_identity) != required_identity or not all(
                isinstance(value, str) and value.strip() for value in resume_identity.values()
            ):
                raise ValueError("invalid persisted resume identity")
            normalized_identity = {key: str(resume_identity[key]) for key in sorted(required_identity)}
        return cls(dict(registry_snapshot), dict(checkpoint_snapshot), normalized_identity)
