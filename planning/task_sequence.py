"""Deterministic composition and boundary-safe resume for Atlas tasks."""
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from planning.task_definition import AtlasTaskDefinition
from planning.task_runtime import EvidenceReducer, TaskRuntimeSession, ToolExecutor


@dataclass(frozen=True)
class TaskSequenceDefinition:
    """Immutable ordered task composition; each task keeps its own runtime policy."""

    tasks: Tuple[AtlasTaskDefinition, ...]

    def __post_init__(self) -> None:
        if not self.tasks:
            raise ValueError("task sequence must contain at least one task")
        names = [task.name for task in self.tasks]
        if len(names) != len(set(names)):
            raise ValueError("task sequence task names must be unique")

    def snapshot(self) -> Dict[str, Any]:
        return {"tasks": [task.snapshot() for task in self.tasks]}


class TaskSequenceSession:
    """Run declarative tasks sequentially without weakening each task's gates.

    A sequence advances only after the current TaskRuntimeSession has independently
    verified and finalized. Checkpoints are intentionally task-boundary only: an
    incomplete task cannot be skipped or resumed by inventing internal state.
    """

    def __init__(
        self,
        definition: TaskSequenceDefinition,
        execute: ToolExecutor,
        evidence_reducers: Sequence[EvidenceReducer],
        start_index: int = 0,
    ) -> None:
        if len(evidence_reducers) != len(definition.tasks):
            raise ValueError("one evidence reducer is required for each task")
        if not 0 <= start_index <= len(definition.tasks):
            raise ValueError("start_index is outside the task sequence")
        self.definition = definition
        self.execute = execute
        self.evidence_reducers = tuple(evidence_reducers)
        self.index = start_index
        self.session: Optional[TaskRuntimeSession] = None
        self.completed: List[Dict[str, Any]] = []

    @property
    def complete(self) -> bool:
        return self.index == len(self.definition.tasks)

    @property
    def current_task(self) -> Optional[AtlasTaskDefinition]:
        if self.complete:
            return None
        return self.definition.tasks[self.index]

    def start_current(self) -> TaskRuntimeSession:
        if self.complete:
            raise RuntimeError("Task sequence is already complete.")
        if self.session is None:
            self.session = TaskRuntimeSession(
                self.current_task, self.execute, self.evidence_reducers[self.index]
            )
        return self.session

    def checkpoint(self) -> Dict[str, Any]:
        return {
            "next_task_index": self.index,
            "completed": list(self.completed),
            "sequence": self.definition.snapshot(),
            "current_task": self.current_task.name if self.current_task else None,
        }

    def advance_after_completion(self) -> Dict[str, Any]:
        session = self.start_current()
        if not session.complete:
            raise RuntimeError("Cannot advance a task sequence before task completion.")
        task = self.current_task
        self.completed.append({"index": self.index, "task": task.name})
        self.index += 1
        self.session = None
        return self.checkpoint()

    def run_current(
        self,
        authorization_id: Optional[str] = None,
        authorization_callback: Optional[Callable[[AtlasTaskDefinition], None]] = None,
    ) -> Dict[str, Any]:
        """Drive one task through its full generic lifecycle, then advance.

        Authorization is required only when target state is unsatisfied. The callback
        is deliberately task-level and cannot execute tools; mutation remains owned
        by TaskRuntimeSession after its exact action authorization is issued.
        """
        session = self.start_current()
        session.acquire_initial_evidence()
        target = session.evaluate_target()
        if not target.satisfied:
            if authorization_callback is not None:
                authorization_callback(session.task)
            if not authorization_id:
                raise RuntimeError("authorization_id is required for an unsatisfied task")
            session.authorize(authorization_id)
            session.execute_authorized_action()

        verified = session.acquire_post_action_evidence()
        result = session.verify_post_action(verified)
        if not result.satisfied:
            raise RuntimeError(f"Task verification failed: {result.failed}")
        session.finalize()
        return self.advance_after_completion()

    @classmethod
    def resume_from_checkpoint(
        cls,
        definition: TaskSequenceDefinition,
        execute: ToolExecutor,
        evidence_reducers: Sequence[EvidenceReducer],
        checkpoint: Dict[str, Any],
    ) -> "TaskSequenceSession":
        expected = definition.snapshot()
        if checkpoint.get("sequence") != expected:
            raise ValueError("checkpoint does not match the task sequence definition")
        completed = checkpoint.get("completed", [])
        start_index = checkpoint.get("next_task_index")
        if not isinstance(start_index, int):
            raise ValueError("checkpoint next_task_index must be an integer")
        session = cls(definition, execute, evidence_reducers, start_index)
        session.completed = list(completed)
        if len(session.completed) != start_index:
            raise ValueError("checkpoint completion history does not match next task index")
        return session
