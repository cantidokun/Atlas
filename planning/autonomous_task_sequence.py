"""Generalized autonomous task sequencing over existing production boundaries."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Tuple

from planning.production_operation_lifecycle import ProductionOperationLifecycle, ProductionOperationState


@dataclass(frozen=True)
class AutonomousTaskStep:
    """One ordered autonomous production step."""

    name: str
    operation: ProductionOperationLifecycle

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("step name must be a non-empty string")
        if not isinstance(self.operation, ProductionOperationLifecycle):
            raise TypeError("operation must be a ProductionOperationLifecycle")


@dataclass(frozen=True)
class AutonomousTaskSequenceResult:
    state: ProductionOperationState
    completed_steps: Tuple[str, ...]
    next_step_index: int
    reason: str

    @property
    def completed(self) -> bool:
        return self.state is ProductionOperationState.COMPLETED


class AutonomousTaskSequence:
    """Run an ordered task sequence without creating a second execution mechanism.

    Existing production-operation lifecycle objects remain responsible for execution,
    authorization, verification, receipts, and blocking. This coordinator only decides
    which already-admitted operation is next.
    """

    def __init__(self, steps: Iterable[AutonomousTaskStep]) -> None:
        values = tuple(steps)
        if not values:
            raise ValueError("steps must contain at least one task step")
        if len({step.name for step in values}) != len(values):
            raise ValueError("step names must be unique")
        self.steps = values
        self.next_step_index = 0

    def run(
        self,
        max_steps: int = 16,
        before_step: Optional[Callable[[int, AutonomousTaskStep], None]] = None,
    ) -> AutonomousTaskSequenceResult:
        if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 1:
            raise ValueError("max_steps must be a positive integer")
        if before_step is not None and not callable(before_step):
            raise TypeError("before_step must be callable")

        completed = []
        while self.next_step_index < len(self.steps):
            index = self.next_step_index
            step = self.steps[index]
            if before_step is not None:
                before_step(index, step)
            result = step.operation.run(max_steps=max_steps)
            if result.state is not ProductionOperationState.COMPLETED or result.receipt is None:
                return AutonomousTaskSequenceResult(
                    ProductionOperationState.BLOCKED,
                    tuple(completed),
                    index,
                    f"autonomous task sequence blocked at step {index + 1}: {result.reason}",
                )
            completed.append(step.name)
            self.next_step_index = index + 1

        return AutonomousTaskSequenceResult(
            ProductionOperationState.COMPLETED,
            tuple(completed),
            self.next_step_index,
            "all autonomous task steps completed with authoritative verification",
        )
