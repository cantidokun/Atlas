"""Registry-backed production resume lifecycle.

This is the narrow integration boundary between persisted registry state and the
production completion lifecycle. It rehydrates the checkpoint through the
canonical registry before constructing the durable task, then delegates terminal
completion authority to ProductionOperationLifecycle.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from action_plan import ActionSpec
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.production_checkpoint_lifecycle import ProductionCheckpointLifecycle
from planning.production_operation_lifecycle import ProductionOperationLifecycle, ProductionOperationResult
from planning.production_task_checkpoint import ProductionTaskCheckpoint


class ProductionRegistryResumeLifecycle:
    """Rehydrate, resume, and authorize production completion from registry state."""

    def __init__(
        self,
        registry: DigitalTwinRegistry,
        checkpoint_snapshot: Mapping[str, Any],
        revision: DigitalTwinRevision,
        observe: Callable[[], Any],
        plan: Callable[[Any], Sequence[ActionSpec]],
        verify_final: Callable[[Any], bool],
        executor: Any = None,
        parent_checkpoint: ProductionTaskCheckpoint | None = None,
    ) -> None:
        if not isinstance(registry, DigitalTwinRegistry):
            raise TypeError("registry must be a DigitalTwinRegistry")
        self.registry = registry
        self.checkpoint_lifecycle = ProductionCheckpointLifecycle(registry)
        checkpoint = self.checkpoint_lifecycle.rehydrate_checkpoint(
            checkpoint_snapshot,
            revision,
            parent_checkpoint=parent_checkpoint,
        )
        self.task = DurableResumableCorrectiveTask(
            checkpoint,
            revision,
            observe,
            plan,
            executor=executor,
            registry=registry,
            checkpoint_lifecycle=self.checkpoint_lifecycle,
            parent_checkpoint=parent_checkpoint,
        )
        self.lifecycle = ProductionOperationLifecycle(self.task, verify_final)

    @property
    def checkpoint(self) -> ProductionTaskCheckpoint:
        return self.task.checkpoint

    def run(self, max_steps: int = 16) -> ProductionOperationResult:
        return self.lifecycle.run(max_steps=max_steps)
