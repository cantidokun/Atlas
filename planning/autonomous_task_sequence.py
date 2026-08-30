"""Generalized autonomous task sequencing over existing production boundaries."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional, Tuple

from planning.production_operation_lifecycle import ProductionOperationLifecycle, ProductionOperationState


def _operation_identity(operation: ProductionOperationLifecycle) -> str:
    """Return a stable identity for the production operation's persisted task context."""
    task = operation.task
    checkpoint = task.checkpoint
    revision = task.revision
    return "|".join(
        (
            str(checkpoint.task_id),
            str(revision.twin_id),
            str(revision.revision_id),
        )
    )


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
class AutonomousTaskSequenceCheckpoint:
    """Durable, execution-free position of an autonomous task sequence."""

    sequence_id: str
    step_names: Tuple[str, ...]
    operation_identities: Tuple[str, ...]
    next_step_index: int

    def snapshot(self) -> dict[str, Any]:
        return {
            "sequence_id": self.sequence_id,
            "step_names": list(self.step_names),
            "operation_identities": list(self.operation_identities),
            "next_step_index": self.next_step_index,
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any]) -> "AutonomousTaskSequenceCheckpoint":
        if not isinstance(snapshot, dict):
            raise TypeError("sequence checkpoint must be a mapping")
        if set(snapshot) != {"sequence_id", "step_names", "operation_identities", "next_step_index"}:
            raise ValueError("invalid autonomous task sequence checkpoint")
        sequence_id = snapshot["sequence_id"]
        step_names = snapshot["step_names"]
        operation_identities = snapshot["operation_identities"]
        next_step_index = snapshot["next_step_index"]
        if not isinstance(sequence_id, str) or not sequence_id.strip():
            raise ValueError("sequence_id must be a non-empty string")
        if not isinstance(step_names, list) or not step_names or any(
            not isinstance(name, str) or not name.strip() for name in step_names
        ):
            raise ValueError("step_names must contain non-empty strings")
        if len(set(step_names)) != len(step_names):
            raise ValueError("step_names must be unique")
        if not isinstance(operation_identities, list) or len(operation_identities) != len(step_names) or any(
            not isinstance(identity, str) or not identity.strip() for identity in operation_identities
        ):
            raise ValueError("operation_identities must contain one non-empty identity per step")
        if isinstance(next_step_index, bool) or not isinstance(next_step_index, int):
            raise TypeError("next_step_index must be an integer")
        if next_step_index < 0 or next_step_index > len(step_names):
            raise ValueError("next_step_index is outside the sequence")
        return cls(sequence_id, tuple(step_names), tuple(operation_identities), next_step_index)


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
    which already-admitted operation is next. The checkpoint stores position and step
    identity only; execution credentials and receipts remain owned by the operations.
    """

    def __init__(self, steps: Iterable[AutonomousTaskStep], sequence_id: str = "default") -> None:
        values = tuple(steps)
        if not values:
            raise ValueError("steps must contain at least one task step")
        if len({step.name for step in values}) != len(values):
            raise ValueError("step names must be unique")
        if not isinstance(sequence_id, str) or not sequence_id.strip():
            raise ValueError("sequence_id must be a non-empty string")
        self.steps = values
        self.sequence_id = sequence_id
        self.next_step_index = 0

    def checkpoint(self) -> AutonomousTaskSequenceCheckpoint:
        return AutonomousTaskSequenceCheckpoint(
            self.sequence_id,
            tuple(step.name for step in self.steps),
            tuple(_operation_identity(step.operation) for step in self.steps),
            self.next_step_index,
        )

    @classmethod
    def from_checkpoint(
        cls,
        steps: Iterable[AutonomousTaskStep],
        checkpoint: AutonomousTaskSequenceCheckpoint,
    ) -> "AutonomousTaskSequence":
        if not isinstance(checkpoint, AutonomousTaskSequenceCheckpoint):
            raise TypeError("checkpoint must be an AutonomousTaskSequenceCheckpoint")
        sequence = cls(steps, sequence_id=checkpoint.sequence_id)
        actual_names = tuple(step.name for step in sequence.steps)
        if actual_names != checkpoint.step_names:
            raise ValueError("checkpoint step identity does not match supplied sequence")
        actual_operation_identities = tuple(_operation_identity(step.operation) for step in sequence.steps)
        if actual_operation_identities != checkpoint.operation_identities:
            raise ValueError("checkpoint operation identity does not match supplied sequence")
        sequence.next_step_index = checkpoint.next_step_index
        return sequence

    def run(
        self,
        max_steps: int = 16,
        before_step: Optional[Callable[[int, AutonomousTaskStep], None]] = None,
        checkpoint_sink: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> AutonomousTaskSequenceResult:
        if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 1:
            raise ValueError("max_steps must be a positive integer")
        if before_step is not None and not callable(before_step):
            raise TypeError("before_step must be callable")
        if checkpoint_sink is not None and not callable(checkpoint_sink):
            raise TypeError("checkpoint_sink must be callable")

        completed = [step.name for step in self.steps[: self.next_step_index]]
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
            if checkpoint_sink is not None:
                checkpoint_sink(self.checkpoint().snapshot())

        return AutonomousTaskSequenceResult(
            ProductionOperationState.COMPLETED,
            tuple(completed),
            self.next_step_index,
            "all autonomous task steps completed with authoritative verification",
        )
