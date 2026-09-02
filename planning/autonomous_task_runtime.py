"""Task-aware autonomous runtime binding declarative tasks to continuations.

The generic autonomous future runtime intentionally knows nothing about task
verification semantics. This adapter owns that task-level binding: it acquires
initial evidence, evaluates the target, requires authorization for writes,
creates the deterministic future, and supplies fresh task evidence at the
verification checkpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from action_plan import ActionSpec
from planning.action_authorization import ActionAuthorization
from planning.autonomous_runtime import AutonomousFutureRuntime, ToolExecutor
from planning.future_generator import DeterministicFutureGenerator
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore
from planning.task_definition import AtlasTaskDefinition
from planning.task_runtime import prepare_task_runtime


@dataclass
class AutonomousTaskRuntime:
    """Bind a declarative Atlas task to the generic autonomous future runtime."""

    task: AtlasTaskDefinition
    runtime: AutonomousFutureRuntime
    executor: ToolExecutor
    authorization: Optional[ActionAuthorization]

    @classmethod
    def start(
        cls,
        task: AtlasTaskDefinition,
        state_store: FutureRuntimeStateStore,
        runtime_context: RuntimeContext,
        executor: ToolExecutor,
        authorization_id: str,
    ) -> "AutonomousTaskRuntime":
        """Run task preflight, authorize writes, and construct a continuation."""
        orchestrator = prepare_task_runtime(task)

        evidence: Dict[str, Any] = {}
        while not orchestrator.evidence_complete:
            result = orchestrator.acquire_next_evidence(executor)
            evidence = result

        target = orchestrator.evaluate_target_state(evidence)
        authorization = None
        actions = [
            ActionSpec(action.tool, dict(action.arguments), action.name, action.requires_success)
            for action in task.actions
        ]
        if not target.satisfied:
            authorization = orchestrator.authorize_execution(authorization_id)

        steps = DeterministicFutureGenerator(task.evaluator).generate(
            target.satisfied,
            actions,
        )
        runtime = AutonomousFutureRuntime(
            steps,
            state_store,
            runtime_context,
        )
        return cls(task, runtime, executor, authorization)

    def _verification(self) -> Dict[str, Any]:
        """Acquire fresh authoritative evidence and return the evaluator input."""
        evidence: Dict[str, Any] = {}
        for request in self.task.evidence:
            evidence = self.executor(request.tool, dict(request.arguments))
            if not isinstance(evidence, dict):
                raise TypeError("Task evidence executor must return a dictionary.")
            if "error" in evidence:
                raise RuntimeError(str(evidence["error"]))
        return evidence

    def run_until_pause(self) -> Dict[str, Any]:
        """Advance through actions, then acquire and evaluate fresh evidence."""
        target_satisfied = self.runtime.steps[2].phase == "SKIP_WRITES"
        acknowledgements: Dict[str, Dict[str, Any]] = {
            "evidence.authoritative": {
                "source": "task_runtime",
                "task": self.task.name,
            },
            "target.evaluated": {"satisfied": target_satisfied},
        }
        if target_satisfied:
            acknowledgements["writes.skipped"] = {"skipped": True}

        paused = self.runtime.run_until_pause(
            self.executor,
            acknowledgements=acknowledgements,
        )
        if paused.get("current_step", {}).get("phase") != "VERIFICATION":
            return paused

        evidence = self._verification()
        result = self.task.evaluator.evaluate(evidence)
        return self.runtime.run_until_pause(
            self.executor,
            verifications={"verification.pending": result.snapshot()},
        )

    def resume_and_run(self) -> Dict[str, Any]:
        """Resume the persisted continuation and provide fresh verification."""
        resumed = self.runtime.resume()
        paused = resumed.run_until_pause(self.executor)
        if paused.get("current_step", {}).get("phase") != "VERIFICATION":
            return paused
        evidence = self._verification()
        result = self.task.evaluator.evaluate(evidence)
        return resumed.run_until_pause(
            self.executor,
            verifications={"verification.pending": result.snapshot()},
        )
