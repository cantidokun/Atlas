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
    """Build the generic conditional orchestrator from task data only."""
    return ConditionalPlanningOrchestrator(
        evidence_plan=EvidencePlan(list(task.evidence)),
        conditional_plan=ConditionalActionPlan(list(task.actions)),
        target_evaluator=task.evaluator,
        verification_plan=VerificationPlan(task.evaluator),
    )


def validate_task_runtime(task: AtlasTaskDefinition) -> Tuple[str, ...]:
    """Return deterministic runtime violations before any evidence or write occurs."""
    violations = []
    if task.allow_writes and not task.verify_after_action:
        violations.append("write-capable task requires verification")
    action_tools = {action.tool for action in task.actions}
    unauthorized = action_tools - set(task.allowed_action_tools)
    if unauthorized:
        violations.append(f"unauthorized action tools: {sorted(unauthorized)}")
    return tuple(violations)


def prepare_task_runtime(task: AtlasTaskDefinition) -> ConditionalPlanningOrchestrator:
    """Validate a task definition and create its deterministic runtime."""
    violations = validate_task_runtime(task)
    if violations:
        raise ValueError("; ".join(violations))
    return build_orchestrator(task)


class TaskRuntimeSession:
    """Generic lifecycle facade for evidence, authorization, action, and verification.

    Task-specific code supplies only the evidence reducer because different Blender
    tasks expose different evidence shapes. Ordering and safety checks remain in
    the shared orchestrator.
    """

    def __init__(
        self,
        task: AtlasTaskDefinition,
        execute: ToolExecutor,
        evidence_reducer: EvidenceReducer,
    ) -> None:
        self.task = task
        self.execute = execute
        self.evidence_reducer = evidence_reducer
        self.orchestrator = prepare_task_runtime(task)
        self.initial_evidence: List[Dict[str, Any]] = []
        self.evidence_state: Optional[Any] = None

    @property
    def phase(self) -> str:
        return self.orchestrator.next_phase()

    @property
    def complete(self) -> bool:
        return self.phase == "COMPLETE"

    def acquire_initial_evidence(self) -> Any:
        """Acquire every declared evidence request through the orchestrator."""
        while not self.orchestrator.evidence_complete:
            self.initial_evidence.append(self.orchestrator.acquire_next_evidence(self.execute))
        self.evidence_state = self.evidence_reducer(self.initial_evidence)
        return self.evidence_state

    def evaluate_target(self) -> Any:
        """Evaluate the task's target state from authoritative initial evidence."""
        if self.evidence_state is None:
            raise RuntimeError("Initial evidence must be acquired before target evaluation.")
        return self.orchestrator.evaluate_target_state(self.evidence_state)

    def authorize(self, authorization_id: str) -> Any:
        """Authorize exactly the action sequence declared by the task."""
        return self.orchestrator.authorize_execution(authorization_id)

    def execute_authorized_action(self) -> Dict[str, Any]:
        """Execute the next action only after the orchestrator's authorization gate."""
        return self.orchestrator.execute_next_action(self.execute)

    def verify_post_action(self, evidence: Any) -> Any:
        """Independently verify fresh post-action evidence."""
        return self.orchestrator.verify_post_action(evidence)

    def finalize(self) -> Dict[str, Any]:
        """Finalize only after the deterministic future reaches COMPLETE."""
        if not self.complete:
            raise RuntimeError(f"Task cannot finalize from phase {self.phase}.")
        return self.orchestrator.finalize_future()

    def snapshot(self) -> Dict[str, Any]:
        return self.orchestrator.snapshot()
