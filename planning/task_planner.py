"""Validate structured task plans before they reach Python execution."""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from action_plan import ActionPlan, ActionSpec
from action_authorization import ActionAuthorization
from evidence_plan import EvidencePlan, EvidenceRequest
from planning.tool_schema import validate_tool_arguments

@dataclass(frozen=True)
class TaskPlanProposal:
    evidence: List[EvidenceRequest]
    actions: List[ActionSpec]

class TaskPlanValidationError(ValueError):
    """Raised when a model-produced plan is not safe to load."""

def _validate_tool(tool: Any, allowed_tools: Optional[set]) -> str:
    if not isinstance(tool, str) or not tool:
        raise TaskPlanValidationError("Every planned tool must have a name.")
    if allowed_tools is not None and tool not in allowed_tools:
        raise TaskPlanValidationError(f"Tool is not allowed: {tool}")
    return tool

def _validate_arguments(arguments: Any) -> Dict[str, Any]:
    if not isinstance(arguments, dict):
        raise TaskPlanValidationError("Tool arguments must be an object.")
    return arguments

def _validate_item(item: Any, kind: str, allowed_tools: Optional[set]) -> tuple[str, Dict[str, Any], str]:
    if not isinstance(item, dict):
        raise TaskPlanValidationError(f"Each {kind} request must be an object.")
    tool = _validate_tool(item.get("tool"), allowed_tools)
    arguments = _validate_arguments(item.get("arguments", {}))
    name = item.get("name", "")
    if not isinstance(name, str):
        raise TaskPlanValidationError(f"{kind} name must be a string.")
    if allowed_tools is not None:
        # The planning bridge is the trust boundary: admitted tools must have
        # an exact argument schema before an executor can ever see the plan.
        validate_tool_arguments(tool, arguments)
    return tool, arguments, name

def build_task_plan(proposal: Dict[str, Any], allowed_tools: Optional[set] = None) -> TaskPlanProposal:
    if not isinstance(proposal, dict):
        raise TaskPlanValidationError("Task plan proposal must be an object.")
    raw_evidence = proposal.get("evidence", [])
    raw_actions = proposal.get("actions", [])
    if not isinstance(raw_evidence, list) or not isinstance(raw_actions, list):
        raise TaskPlanValidationError("Evidence and actions must both be lists.")
    evidence: List[EvidenceRequest] = []
    for item in raw_evidence:
        tool, arguments, name = _validate_item(item, "evidence", allowed_tools)
        evidence.append(EvidenceRequest(tool=tool, arguments=arguments, name=name))
    actions: List[ActionSpec] = []
    for item in raw_actions:
        tool, arguments, name = _validate_item(item, "action", allowed_tools)
        actions.append(ActionSpec(tool=tool, arguments=arguments, name=name))
    return TaskPlanProposal(evidence=evidence, actions=actions)

def instantiate_plans(proposal: TaskPlanProposal) -> tuple[EvidencePlan, ActionPlan]:
    """Instantiate plans without granting execution authorization."""
    return EvidencePlan(proposal.evidence), ActionPlan(proposal.actions)

def instantiate_authorized_plans(
    proposal: TaskPlanProposal,
    *,
    authorization_id: str,
) -> tuple[EvidencePlan, ActionPlan]:
    """Instantiate a task plan and bind its exact actions to one receipt.

    Authorization is deliberately explicit and occurs after proposal validation.
    Callers that only need inspection can continue using ``instantiate_plans``;
    execution-capable callers must opt into this boundary.
    """
    evidence_plan, action_plan = instantiate_plans(proposal)
    authorization = ActionAuthorization.issue(proposal.actions, authorization_id)
    action_plan.authorize(authorization)
    return evidence_plan, action_plan
