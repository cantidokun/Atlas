"""Execute validated Atlas plans with a read-only safety boundary.

This module intentionally supports evidence-only plans. It refuses action steps
and any tool that is not explicitly marked as read-only.
"""

from typing import Any, Dict

from task_planner import TaskPlanProposal
from tools import TOOLS

READ_ONLY_TOOLS = {
    "inspect_scene",
    "inspect_mesh",
    "inspect_scene_health",
    "inspect_scene_settings",
    "inspect_object_relationship",
    "inspect_soccer_components",
}


def _plan_parts(proposal: Any):
    if isinstance(proposal, TaskPlanProposal):
        return proposal.actions, proposal.evidence
    if isinstance(proposal, dict):
        return proposal.get("actions", []), proposal.get("evidence", [])
    raise ValueError("Proposal must be a validated TaskPlanProposal or dictionary")


def execute_read_only_plan(proposal: Any) -> Dict[str, Any]:
    """Execute only validated evidence requests from a Qwen-derived proposal."""
    actions, evidence = _plan_parts(proposal)
    if actions:
        raise PermissionError("Read-only executor refuses action steps")
    if not isinstance(evidence, list):
        raise ValueError("Evidence must be a list")

    results = []
    for request in evidence:
        if isinstance(request, dict):
            tool_name = request.get("tool")
            arguments = request.get("arguments", {})
        else:
            tool_name = getattr(request, "tool", None)
            arguments = getattr(request, "arguments", {})

        if tool_name not in READ_ONLY_TOOLS:
            raise PermissionError(f"Tool is not read-only: {tool_name}")
        tool = TOOLS.get(tool_name)
        if tool is None:
            raise ValueError(f"Unknown Atlas tool: {tool_name}")
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be an object")
        results.append({
            "tool": tool_name,
            "result": tool(**arguments),
        })

    return {
        "execution_authorized": False,
        "read_only": True,
        "results": results,
    }
