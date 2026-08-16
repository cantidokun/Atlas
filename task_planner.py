"""Validate structured task plans before they reach Python execution.

Qwen may propose evidence requests and actions, but this module does not
execute anything and does not grant authorization. It converts a small,
strictly structured proposal into Atlas planning primitives only after the
proposal passes basic safety checks.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from action_plan import ActionPlan, ActionSpec
from evidence_plan import EvidencePlan, EvidenceRequest


@dataclass(frozen=True)
class TaskPlanProposal:
    """Untrusted planning output proposed by the reasoning model."""

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


def build_task_plan(
    proposal: Dict[str, Any],
    allowed_tools: Optional[set] = None,
) -> TaskPlanProposal:
    """Validate a structured model proposal without authorizing execution.

    Expected shape::

        {
            "evidence": [{"tool": "...", "arguments": {...}, "name": "..."}],
            "actions": [{"tool": "...", "arguments": {...}, "name": "..."}]
        }

    The returned plans are still inert. Authorization and execution happen in
    a separate Python-controlled step.
    """
    if not isinstance(proposal, dict):
        raise TaskPlanValidationError("Task plan proposal must be an object.")

    raw_evidence = proposal.get("evidence", [])
    raw_actions = proposal.get("actions", [])
    if not isinstance(raw_evidence, list) or not isinstance(raw_actions, list):
        raise TaskPlanValidationError("Evidence and actions must both be lists.")

    evidence: List[EvidenceRequest] = []
    for item in raw_evidence:
        if not isinstance(item, dict):
            raise TaskPlanValidationError("Each evidence request must be an object.")
        evidence.append(
            EvidenceRequest(
                tool=_validate_tool(item.get("tool"), allowed_tools),
                arguments=_validate_arguments(item.get("arguments", {})),
                name=str(item.get("name", "")),
            )
        )

    actions: List[ActionSpec] = []
    for item in raw_actions:
        if not isinstance(item, dict):
            raise TaskPlanValidationError("Each action must be an object.")
        actions.append(
            ActionSpec(
                tool=_validate_tool(item.get("tool"), allowed_tools),
                arguments=_validate_arguments(item.get("arguments", {})),
                name=str(item.get("name", "")),
            )
        )

    return TaskPlanProposal(evidence=evidence, actions=actions)


def instantiate_plans(proposal: TaskPlanProposal) -> tuple[EvidencePlan, ActionPlan]:
    """Create inert Python planning state from a validated proposal."""
    return EvidencePlan(proposal.evidence), ActionPlan(proposal.actions)
