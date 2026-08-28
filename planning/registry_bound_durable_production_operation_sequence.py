"""Registry-bound durable multi-operation production sequencing."""

from typing import Callable, Optional

from planning.digital_twin_registry import DigitalTwinRegistry
from planning.durable_production_operation_sequence import DurableProductionOperationSequence


class RegistryBoundDurableProductionOperationSequence:
    """Require every sequence checkpoint and unfinished operation to bind to the current canonical revision."""

    def __init__(self, operations, registry: DigitalTwinRegistry, checkpoint=None):
        if not isinstance(registry, DigitalTwinRegistry):
            raise TypeError("registry must be a DigitalTwinRegistry")
        values = tuple(operations)
        if not values:
            raise ValueError("operations must contain at least one production operation")
        self.registry = registry
        self._sequence = DurableProductionOperationSequence(values, checkpoint=checkpoint)
        self._validate_registry_binding()

    def _validate_registry_binding(self) -> None:
        completed = self._sequence.checkpoint.completed_receipts
        if len(completed) > len(self._sequence.operations):
            raise ValueError("durable sequence checkpoint contains too many completed operations")

        for index, snapshot in enumerate(completed):
            twin_id = snapshot.get("twin_id")
            revision_id = snapshot.get("revision_id")
            if not twin_id or not revision_id:
                raise ValueError("completed receipt is missing canonical revision binding")
            canonical = self.registry.canonical_revision(twin_id)
            if canonical.revision_id != revision_id:
                raise ValueError("durable sequence checkpoint is bound to a stale Digital Twin revision")

            operation = self._sequence.operations[index]
            task_checkpoint = operation.task.checkpoint
            if (
                snapshot.get("task_id") != task_checkpoint.task_id
                or twin_id != task_checkpoint.twin_id
                or revision_id != task_checkpoint.revision_id
                or snapshot.get("checkpoint_digest") != task_checkpoint.checkpoint_digest
            ):
                raise ValueError(
                    "completed receipt is not bound to its corresponding production operation"
                )

        for operation in self._sequence.operations[self._sequence.next_operation_index:]:
            self.registry.require_canonical_revision(operation.task.revision)

    @property
    def checkpoint(self):
        return self._sequence.checkpoint

    @property
    def next_operation_index(self):
        return self._sequence.next_operation_index

    def run(
        self,
        max_steps: int = 16,
        checkpoint_sink: Optional[Callable[[object], None]] = None,
    ):
        if checkpoint_sink is not None and not callable(checkpoint_sink):
            raise TypeError("checkpoint_sink must be callable")
        self._validate_registry_binding()
        result = self._sequence.run(
            max_steps=max_steps,
            checkpoint_sink=checkpoint_sink,
        )
        self._validate_registry_binding()
        return result
