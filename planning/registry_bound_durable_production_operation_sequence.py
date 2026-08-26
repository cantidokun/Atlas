"""Registry-bound durable multi-operation production sequencing."""
from __future__ import annotations

from planning.digital_twin_registry import DigitalTwinRegistry
from planning.durable_production_operation_sequence import (
    DurableProductionOperationSequence,
    DurableProductionSequenceCheckpoint,
)


class RegistryBoundDurableProductionOperationSequence:
    """Require every sequence receipt to remain on the current canonical revision."""

    def __init__(self, operations, registry: DigitalTwinRegistry, checkpoint=None):
        if not isinstance(registry, DigitalTwinRegistry):
            raise TypeError("registry must be a DigitalTwinRegistry")
        values = tuple(operations)
        if not values:
            raise ValueError("operations must contain at least one production operation")
        self.registry = registry
        self._sequence = DurableProductionOperationSequence(values, checkpoint=checkpoint)
        self._validate_registry_binding()

    def _validate_registry_binding(self):
        for snapshot in self._sequence.checkpoint.completed_receipts:
            twin_id = snapshot.get("twin_id")
            revision_id = snapshot.get("revision_id")
            if not twin_id or not revision_id:
                raise ValueError("completed receipt is missing canonical revision binding")
            canonical = self.registry.canonical_revision(twin_id)
            if canonical.revision_id != revision_id:
                raise ValueError("durable sequence checkpoint is bound to a stale Digital Twin revision")

        for operation in self._sequence.operations[self._sequence.next_operation_index:]:
            self.registry.require_canonical_revision(operation.task.revision)

    @property
    def checkpoint(self):
        return self._sequence.checkpoint

    @property
    def next_operation_index(self):
        return self._sequence.next_operation_index

    def run(self, max_steps: int = 16):
        self._validate_registry_binding()
        result = self._sequence.run(max_steps=max_steps)
        self._validate_registry_binding()
        return result
