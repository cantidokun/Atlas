"""Production operation completion boundary.

Executor success and planner convergence are not authoritative completion. A
production operation reaches COMPLETED only after an explicit authoritative
verification callback accepts the final observed state.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask


class ProductionOperationState(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ProductionOperationResult:
    state: ProductionOperationState
    task_result: CorrectiveTaskResult
    reason: str

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

    def run(self, max_steps: int = 16) -> ProductionOperationResult:
        result = self.task.resume(max_steps=max_steps)
        if not result.converged:
            self.state = ProductionOperationState.BLOCKED
            return ProductionOperationResult(
                self.state,
                result,
                "corrective execution did not converge",
            )
        try:
            verified = bool(self.verify_final(result.final_evidence))
        except Exception as exc:
            self.state = ProductionOperationState.BLOCKED
            return ProductionOperationResult(
                self.state,
                result,
                f"authoritative verification failed: {exc}",
            )
        if not verified:
            self.state = ProductionOperationState.BLOCKED
            return ProductionOperationResult(
                self.state,
                result,
                "authoritative verification rejected final evidence",
            )
        self.state = ProductionOperationState.COMPLETED
        return ProductionOperationResult(
            self.state,
            result,
            "authoritative verification accepted final evidence",
        )
