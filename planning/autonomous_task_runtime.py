"""Task-aware autonomous runtime binding declarative tasks to continuations.

The generic autonomous future runtime intentionally knows nothing about task
verification semantics. This adapter owns that task-level binding: it acquires
initial evidence, evaluates the target, requires authorization for writes,
creates the deterministic future, supplies fresh task evidence at verification,
and exposes the existing fail-closed recovery/replan protocol without creating a
second executor or authorization system.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from action_plan import ActionSpec
from planning.action_authorization import ActionAuthorization
from planning.autonomous_runtime import AutonomousFutureRuntime, ToolExecutor
from planning.future_execution import FutureExecutionController
from planning.future_generator import DeterministicFutureGenerator
from planning.future_recovery import FutureRecoveryGate
from planning.replan_authorization import ReplanAuthorization
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
    recovery_gate: Optional[FutureRecoveryGate] = None
    replan_authorization: Optional[ReplanAuthorization] = None
    current_actions: Optional[List[ActionSpec]] = None

    @staticmethod
    def _actions(task: AtlasTaskDefinition) -> List[ActionSpec]:
        return [
            ActionSpec(action.tool, dict(action.arguments), action.name, action.requires_success)
            for action in task.actions
        ]

    @classmethod
    def start(cls, task: AtlasTaskDefinition, state_store: FutureRuntimeStateStore, runtime_context: RuntimeContext, executor: ToolExecutor, authorization_id: str) -> "AutonomousTaskRuntime":
        orchestrator = prepare_task_runtime(task)
        evidence: Dict[str, Any] = {}
        while not orchestrator.evidence_complete:
            evidence = orchestrator.acquire_next_evidence(executor)
        target = orchestrator.evaluate_target_state(evidence)
        actions = cls._actions(task)
        authorization = None if target.satisfied else orchestrator.authorize_execution(authorization_id)
        steps = DeterministicFutureGenerator(task.evaluator).generate(target.satisfied, actions)
        metadata: Dict[str, Any] = {"target_satisfied": target.satisfied, "target_evaluation": target.snapshot()}
        if authorization is not None:
            metadata["action_authorization"] = authorization.snapshot()
        runtime = AutonomousFutureRuntime(steps, state_store, runtime_context, metadata=metadata)
        cls._validate_persisted_binding(runtime, metadata, actions)
        return cls(task, runtime, executor, authorization, current_actions=actions)

    @staticmethod
    def _validate_persisted_binding(runtime: AutonomousFutureRuntime, metadata: Dict[str, Any], actions: List[ActionSpec]) -> None:
        target_satisfied = metadata.get("target_satisfied")
        if not isinstance(target_satisfied, bool):
            raise RuntimeError("persisted task target decision is missing or invalid")
        expected_step = runtime.steps[2]
        if target_satisfied and expected_step.phase != "SKIP_WRITES":
            raise RuntimeError("persisted task target decision does not match the generated future")
        if not target_satisfied and expected_step.phase != "ACTION":
            raise RuntimeError("persisted task target decision does not match the generated future")
        raw_authorization = metadata.get("action_authorization")
        if target_satisfied:
            if raw_authorization is not None:
                raise RuntimeError("satisfied task cannot persist write authorization")
            return
        if not isinstance(raw_authorization, dict):
            raise RuntimeError("unsatisfied task is missing persisted action authorization")
        authorization = ActionAuthorization.from_snapshot(raw_authorization)
        if not authorization.matches(actions):
            raise RuntimeError("persisted action authorization does not match the task action plan")

    @classmethod
    def resume_from_store(cls, task: AtlasTaskDefinition, state_store: FutureRuntimeStateStore, runtime_context: RuntimeContext, executor: ToolExecutor) -> "AutonomousTaskRuntime":
        prepare_task_runtime(task)
        actions = cls._actions(task)
        envelope = state_store.load()
        metadata = envelope.get("metadata") or {}
        target_satisfied = metadata.get("target_satisfied")
        if not isinstance(target_satisfied, bool):
            raise RuntimeError("persisted task target decision is missing or invalid")
        steps = DeterministicFutureGenerator(task.evaluator).generate(target_satisfied, actions)
        raw_authorization = metadata.get("action_authorization")
        authorization = None
        if target_satisfied:
            if raw_authorization is not None:
                raise RuntimeError("satisfied task cannot resume with write authorization")
        else:
            if not isinstance(raw_authorization, dict):
                raise RuntimeError("unsatisfied task cannot resume without persisted action authorization")
            authorization = ActionAuthorization.from_snapshot(raw_authorization)
            if not authorization.matches(actions):
                raise RuntimeError("persisted action authorization does not match the task action plan")
        runtime = AutonomousFutureRuntime.resume_from_store(steps, state_store, runtime_context)
        if runtime.metadata != metadata:
            raise RuntimeError("persisted task metadata changed during runtime reconstruction")
        cls._validate_persisted_binding(runtime, metadata, actions)
        recovery_gate = FutureRecoveryGate(runtime.controller) if runtime.controller.blocked else None
        if recovery_gate is not None:
            recovery_gate.classify_failure()
        return cls(task, runtime, executor, authorization, recovery_gate=recovery_gate, current_actions=actions)

    def _execute_authorized(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute only when the immutable current authorization still binds the call."""
        if self.authorization is not None:
            authorized_actions = self.current_actions if self.current_actions is not None else self._actions(self.task)
            if not self.authorization.matches(authorized_actions):
                raise RuntimeError("task action authorization no longer matches the current authorized plan")
            next_action = self.runtime.snapshot().get("next_action")
            if next_action is None:
                raise RuntimeError("no authorized action is pending")
            if next_action.get("tool") != tool or next_action.get("arguments") != arguments:
                raise RuntimeError("autonomous action does not match the authorized future")
        return self.executor(tool, arguments)

    def _run_executor(self) -> ToolExecutor:
        return self._execute_authorized

    def _verification(self) -> Dict[str, Any]:
        evidence: Dict[str, Any] = {}
        for request in self.task.evidence:
            evidence = self.executor(request.tool, dict(request.arguments))
            if not isinstance(evidence, dict):
                raise TypeError("Task evidence executor must return a dictionary.")
            if "error" in evidence:
                raise RuntimeError(str(evidence["error"]))
        return evidence

    def _verification_failure(self, exc: Exception) -> Dict[str, Any]:
        step = self.runtime.controller.current_step
        if step is None or step.phase != "VERIFICATION":
            raise exc
        failure = {"satisfied": False, "error": str(exc), "exception_type": type(exc).__name__}
        return self.runtime.run_until_pause(self._run_executor(), verifications={"verification.pending": failure})

    def _perform_verification(self) -> Optional[Dict[str, Any]]:
        try:
            evidence = self._verification()
            return self.task.evaluator.evaluate(evidence).snapshot()
        except Exception as exc:
            return self._verification_failure(exc)

    def _ensure_recovery_gate(self) -> FutureRecoveryGate:
        if not self.runtime.controller.blocked:
            raise RuntimeError("Recovery can only begin after the autonomous future is blocked.")
        if self.recovery_gate is None:
            self.recovery_gate = FutureRecoveryGate(self.runtime.controller)
            self.recovery_gate.classify_failure()
        return self.recovery_gate

    def recover_with_fresh_evidence(self) -> Dict[str, Any]:
        gate = self._ensure_recovery_gate()
        if gate.fresh_evidence_acquired:
            return gate.snapshot()
        evidence = self._verification()
        gate.record_fresh_evidence(evidence)
        gate.advance_after_fresh_evidence()
        self.replan_authorization = None
        self.runtime.checkpoint_metadata({"recovery": gate.snapshot()})
        return gate.snapshot()

    def authorize_replan(self, authorized_actions: List[ActionSpec], authorization_id: str) -> ReplanAuthorization:
        gate = self._ensure_recovery_gate()
        if not gate.fresh_evidence_acquired:
            raise RuntimeError("Fresh authoritative recovery evidence is required before replanning.")
        if not isinstance(authorized_actions, list) or any(not isinstance(action, ActionSpec) for action in authorized_actions):
            raise TypeError("authorized_actions must be a list of ActionSpec objects.")
        allowed = set(self.task.allowed_action_tools)
        unauthorized = {action.tool for action in authorized_actions} - allowed
        if unauthorized:
            raise RuntimeError(f"unauthorized recovery action tools: {sorted(unauthorized)}")
        receipt = ReplanAuthorization.issue(gate.authorize_replan(), authorized_actions, authorization_id)
        self.replan_authorization = receipt
        return receipt

    def install_authorized_replan(self, authorization: ReplanAuthorization, authorized_actions: List[ActionSpec]) -> "AutonomousTaskRuntime":
        gate = self._ensure_recovery_gate()
        if self.replan_authorization != authorization:
            raise RuntimeError("Replan authorization does not match the current recovery authorization.")
        if not gate.fresh_evidence_acquired:
            raise RuntimeError("Fresh authoritative recovery evidence is required before replanning.")
        if not isinstance(authorized_actions, list) or any(not isinstance(action, ActionSpec) for action in authorized_actions):
            raise TypeError("authorized_actions must be a list of ActionSpec objects.")
        allowed = set(self.task.allowed_action_tools)
        unauthorized = {action.tool for action in authorized_actions} - allowed
        if unauthorized:
            raise RuntimeError(f"unauthorized recovery action tools: {sorted(unauthorized)}")
        evidence = gate.authorize_replan()
        if not authorization.matches(evidence, authorized_actions):
            raise RuntimeError("replacement actions do not match the authorized replan")
        target = self.task.evaluator.evaluate(evidence)
        actions = list(authorized_actions)
        execution_authorization = None if target.satisfied else ActionAuthorization.issue(actions, authorization.authorization_id)
        steps = DeterministicFutureGenerator(self.task.evaluator).generate(target.satisfied, actions)
        metadata: Dict[str, Any] = {
            "target_satisfied": target.satisfied,
            "target_evaluation": target.snapshot(),
            "replanned_from": authorization.snapshot(),
        }
        if execution_authorization is not None:
            metadata["action_authorization"] = execution_authorization.snapshot()
        controller = FutureExecutionController(steps)
        controller.acknowledge({"recovery_evidence": True})
        controller.acknowledge(target.snapshot())
        if target.satisfied:
            controller.acknowledge({"writes_skipped": True})
        self.runtime = AutonomousFutureRuntime(
            steps,
            self.runtime.state_store,
            self.runtime.runtime_context,
            controller=controller,
            metadata=metadata,
        )
        self.authorization = execution_authorization
        self.current_actions = actions
        self.recovery_gate = None
        self.replan_authorization = None
        self._validate_persisted_binding(self.runtime, metadata, actions)
        return self

    def run_until_pause(self) -> Dict[str, Any]:
        if self.runtime.controller.blocked:
            return self.runtime.snapshot()
        target_satisfied = self.runtime.steps[2].phase == "SKIP_WRITES"
        acknowledgements: Dict[str, Dict[str, Any]] = {
            "evidence.authoritative": {"source": "task_runtime", "task": self.task.name},
            "target.evaluated": {"satisfied": target_satisfied},
        }
        if target_satisfied:
            acknowledgements["writes.skipped"] = {"skipped": True}
        paused = self.runtime.run_until_pause(self._run_executor(), acknowledgements=acknowledgements)
        current_step = paused.get("current_step")
        if not isinstance(current_step, dict) or current_step.get("phase") != "VERIFICATION":
            return paused
        verification = self._perform_verification()
        if verification is None:
            return self.runtime.snapshot()
        return self.runtime.run_until_pause(self._run_executor(), verifications={"verification.pending": verification})

    def resume_and_run(self) -> Dict[str, Any]:
        self.runtime = self.runtime.resume()
        if self.runtime.controller.blocked:
            self.recovery_gate = FutureRecoveryGate(self.runtime.controller)
            self.recovery_gate.classify_failure()
            return self.runtime.snapshot()
        paused = self.runtime.run_until_pause(self._run_executor())
        current_step = paused.get("current_step")
        if not isinstance(current_step, dict) or current_step.get("phase") != "VERIFICATION":
            return paused
        verification = self._perform_verification()
        if verification is None:
            return self.runtime.snapshot()
        return self.runtime.run_until_pause(self._run_executor(), verifications={"verification.pending": verification})
