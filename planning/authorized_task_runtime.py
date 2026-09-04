"""Generic bootstrap for feeding an Atlas-issued authorization into the task runtime.

This module adds no execution engine and no new authorization mechanism. It
exists as a narrow compatibility seam while the established
``AutonomousTaskRuntime.start`` API continues to accept the legacy
``authorization_id`` flow. The supplied receipt must already be issued by Atlas
and must match the exact compiled action plan before a runtime is constructed.
"""

from __future__ import annotations

from typing import Any, Dict

from planning.action_authorization import ActionAuthorization
from planning.autonomous_task_runtime import AutonomousTaskRuntime
from planning.autonomous_runtime import AutonomousFutureRuntime
from planning.future_generator import DeterministicFutureGenerator
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore
from planning.task_definition import AtlasTaskDefinition
from planning.task_runtime import prepare_task_runtime


class AuthorizedTaskRuntimeError(RuntimeError):
    """Raised when a pre-authorized runtime cannot be constructed safely."""


def start_authorized_task_runtime(
    task: AtlasTaskDefinition,
    state_store: FutureRuntimeStateStore,
    runtime_context: RuntimeContext,
    executor,
    authorization: ActionAuthorization,
) -> AutonomousTaskRuntime:
    """Start the existing task runtime from an Atlas-issued authorization receipt.

    Evidence and target evaluation happen before the autonomous future is
    constructed. No tool write is performed by this bootstrap itself.
    """
    if not isinstance(authorization, ActionAuthorization):
        raise TypeError("authorization must be an Atlas ActionAuthorization")

    orchestrator = prepare_task_runtime(task)
    evidence = AutonomousTaskRuntime._acquire_task_evidence(task, orchestrator, executor)
    target = orchestrator.evaluate_target_state(evidence)
    actions = AutonomousTaskRuntime._actions(task)

    if target.satisfied:
        raise AuthorizedTaskRuntimeError("satisfied task cannot start with write authorization")
    if not authorization.matches(actions):
        raise AuthorizedTaskRuntimeError("pre-issued action authorization does not match the task action plan")

    steps = DeterministicFutureGenerator(task.evaluator).generate(False, actions)
    metadata: Dict[str, Any] = {
        "target_satisfied": target.satisfied,
        "target_evaluation": target.snapshot(),
        "task_metadata": AutonomousTaskRuntime._task_metadata(task),
        "action_authorization": authorization.snapshot(),
        "authorization_source": "atlas_preissued",
    }
    runtime = AutonomousFutureRuntime(
        steps,
        state_store,
        runtime_context,
        metadata=metadata,
    )
    AutonomousTaskRuntime._validate_persisted_binding(runtime, metadata, actions, task=task)
    return AutonomousTaskRuntime(
        task,
        runtime,
        executor,
        authorization,
        current_actions=actions,
    )


__all__ = ["AuthorizedTaskRuntimeError", "start_authorized_task_runtime"]
