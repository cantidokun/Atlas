"""Production operation completion boundaries.

Executor success and planner convergence are not authoritative completion. A
production operation reaches COMPLETED only after an explicit authoritative
verification callback accepts the final observed state.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Iterable, Tuple

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from planning.production_completion_receipt import ProductionCompletionReceipt


class ProductionOperationState(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ProductionOperationResult:
    state: ProductionOperationState
    task_result: CorrectiveTaskResult
    reason: str
    receipt: ProductionCompletionReceipt | None = None

    @property
    def completed(self) -> bool:
        return self.state is ProductionOperationState.COMPLETED


class ProductionOperationLifecycle:
    """Promote a corrective-task result to production completion only after verification."""

    def __init__(
        self,
        task: DurableResumableCorrectiveTask,
        verify_final: Callable[[Any], bool],
    ) -> None:
        if not isinstance(task, DurableResumableCorrectiveTask):
            raise TypeError("task must be a DurableResumableCorrectiveTask")
        if not callable(verify_final):
            raise TypeError("verify_final must be callable")
        self.task = task
        self.verify_final = verify_final
        self.state = ProductionOperationState.RUNNING
        self.receipt: ProductionCompletionReceipt | None = None

    def run(self, max_steps: int = 16) -> ProductionOperationResult:
        result = self.task.resume(max_steps=max_steps)
        if not result.converged:
            self.state = ProductionOperationState.BLOCKED
            self.receipt = None
            return ProductionOperationResult(
                self.state,
                result,
                "corrective execution did not converge",
            )
        try:
            verified = bool(self.verify_final(result.final_evidence))
        except Exception as exc:
            self.state = ProductionOperationState.BLOCKED
            self.receipt = None
            return ProductionOperationResult(
                self.state,
                result,
                f"authoritative verification failed: {exc}",
            )
        if not verified:
            self.state = ProductionOperationState.BLOCKED
            self.receipt = None
            return ProductionOperationResult(
                self.state,
                result,
                "authoritative verification rejected final evidence",
            )
        self.receipt = ProductionCompletionReceipt.create(
            self.task.checkpoint,
            self.task.revision,
            result.final_evidence,
        )
        self.state = ProductionOperationState.COMPLETED
        return ProductionOperationResult(
            self.state,
            result,
            "authoritative verification accepted final evidence",
            receipt=self.receipt,
        )


@dataclass(frozen=True)
class ProductionOperationSequenceResult:
    state: ProductionOperationState
    results: Tuple[ProductionOperationResult, ...]
    reason: str

    @property
    def completed(self) -> bool:
        return self.state is ProductionOperationState.COMPLETED

    @property
    def receipts(self) -> Tuple[ProductionCompletionReceipt, ...]:
        return tuple(
            result.receipt
            for result in self.results
            if result.receipt is not None
        )


class ProductionOperationSequence:
    """Run production operations in order and fail closed on the first blocked step.

    Each operation retains its own checkpoint and authoritative completion receipt.
    The sequence itself is complete only when every operation completes. A blocked
    operation stops the sequence; successful earlier operations remain represented
    in ``results`` but do not promote the overall sequence to completion.
    """

    def __init__(self, operations: Iterable[ProductionOperationLifecycle]) -> None:
        values = tuple(operations)
        if not values:
            raise ValueError("operations must contain at least one production operation")
        if any(not isinstance(operation, ProductionOperationLifecycle) for operation in values):
            raise TypeError("operations must contain ProductionOperationLifecycle values")
        self.operations = values
        self.state = ProductionOperationState.RUNNING
        self.results: Tuple[ProductionOperationResult, ...] = ()

    def run(self, max_steps: int = 16) -> ProductionOperationSequenceResult:
        results = []
        for operation in self.operations:
            result = operation.run(max_steps=max_steps)
            results.append(result)
            if result.state is ProductionOperationState.BLOCKED:
                self.results = tuple(results)
                self.state = ProductionOperationState.BLOCKED
                return ProductionOperationSequenceResult(
                    self.state,
                    self.results,
                    f"production operation sequence blocked at step {len(results)}: {result.reason}",
                )
        self.results = tuple(results)
        self.state = ProductionOperationState.COMPLETED
        return ProductionOperationSequenceResult(
            self.state,
            self.results,
            "all production operations completed with authoritative verification",
        )
