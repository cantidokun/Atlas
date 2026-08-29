"""Generic runtime bridge from declarative task definitions to orchestration."""
from typing import Any, Callable, Dict, List, Optional, Tuple

from conditional_action_plan import ConditionalActionPlan
from evidence_plan import EvidencePlan
from planning.planning_orchestrator import ConditionalPlanningOrchestrator
from planning.task_definition import AtlasTaskDefinition
from planning.verification_plan import VerificationPlan

ToolExecutor = Callable[[str, Dict[str, Any]], Dict[str, Any]]
EvidenceReducer = Callable[[List[Dict[str, Any]]], Any]


def build_orchestrator(task: AtlasTaskDefinition) -> ConditionalPlanningOrchestrator:
    return ConditionalPlanningOrchestrator(
        evidence_plan=EvidencePlan(list(task.evidence)),
        conditional_plan=ConditionalActionPlan(list(task.actions)),
        target_evaluator=task.evaluator,
        verification_plan=VerificationPlan(task.evaluator),
    )


def validate_task_runtime(task: AtlasTaskDefinition) -> Tuple[str, ...]:
    violations = []
    if task.allow_writes and not task.verify_after_action:
        violations.append("write-capable task requires verification")
    action_tools = {action.tool for action in task.actions}
    unauthorized = action_tools - set(task.allowed_action_tools)
    if unauthorized:
        violations.append(f"unauthorized action tools: {sorted(unauthorized)}")
    return tuple(violations)


def prepare_task_runtime(task: AtlasTaskDefinition) -> ConditionalPlanningOrchestrator:
    violations = validate_task_runtime(task)
    if violations:
        raise ValueError("; ".join(violations))
    return build_orchestrator(task)


class TaskRuntimeSession:
    """Single generic lifecycle for declarative Atlas tasks."""

    def __init__(self, task: AtlasTaskDefinition, execute: ToolExecutor, evidence_reducer: EvidenceReducer) -> None:
        self.task = task
        self.execute = execute
        self.evidence_reducer = evidence_reducer
        self.orchestrator = prepare_task_runtime(task)
        self.initial_evidence: List[Dict[str, Any]] = []
        self.post_action_evidence: List[Dict[str, Any]] = []
        self.evidence_state: Optional[Any] = None
        self.last_execution: Optional[Dict[str, Any]] = None

    @property
    def phase(self) -> str:
        return self.orchestrator.next_phase()

    @property
    def complete(self) -> bool:
        return self.phase == "COMPLETE"

    def acquire_initial_evidence(self) -> Any:
        while not self.orchestrator.evidence_complete:
            self.initial_evidence.append(self.orchestrator.acquire_next_evidence(self.execute))
        self.evidence_state = self.evidence_reducer(self.initial_evidence)
        return self.evidence_state

    def evaluate_target(self) -> Any:
        if self.evidence_state is None:
            raise RuntimeError("Initial evidence must be acquired before target evaluation.")
        return self.orchestrator.evaluate_target_state(self.evidence_state)

    def authorize(self, authorization_id: str) -> Any:
        return self.orchestrator.authorize_execution(authorization_id)

    def execute_authorized_action(self) -> Dict[str, Any]:
        self.last_execution = self.orchestrator.execute_next_action(self.execute)
        return self.last_execution

    def acquire_post_action_evidence(self) -> Any:
        if not self.task.verify_after_action:
            raise RuntimeError("Post-action evidence is disabled by the task definition.")
        self.post_action_evidence = [self.execute(request.tool, dict(request.arguments)) for request in self.task.evidence]
        return self.evidence_reducer(self.post_action_evidence)

    def verify_post_action(self, evidence: Any) -> Any:
        return self.orchestrator.verify_post_action(evidence)

    def run_conditional_lifecycle(self, authorization_id: str) -> Tuple[Any, Optional[Dict[str, Any]], Any]:
        """Run the shared inspect -> decide -> authorize/skip -> execute -> verify lifecycle.

        Task-specific planning, authorization-policy checks, execution receipts, and audit logging
        remain outside this session. This method only centralizes the deterministic runtime phases
        already defined by ``TaskRuntimeSession``.
        """
        state = self.evaluate_target()
        execution: Optional[Dict[str, Any]] = None
        if not state.satisfied:
            self.authorize(authorization_id)
            execution = self.execute_authorized_action()
        verified = self.verify_post_action(self.acquire_post_action_evidence())
        self.finalize()
        return state, execution, verified

    def finalize(self) -> Dict[str, Any]:
        if not self.complete:
            raise RuntimeError(f"Task cannot finalize from phase {self.phase}.")
        return self.orchestrator.finalize_future()

    def snapshot(self) -> Dict[str, Any]:
        return self.orchestrator.snapshot()
