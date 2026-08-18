"""Generic runtime bridge from declarative task definitions to orchestration."""
from typing import Any, Dict, Tuple

from conditional_action_plan import ConditionalActionPlan
from evidence_plan import EvidencePlan
from planning.planning_orchestrator import ConditionalPlanningOrchestrator
from planning.task_definition import AtlasTaskDefinition
from planning.verification_plan import VerificationPlan


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
