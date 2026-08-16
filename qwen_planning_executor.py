"""Execute validated Atlas plans with a read-only safety boundary.

This module intentionally supports evidence-only plans. It refuses action steps
and any tool that is not explicitly marked as read-only.
"""

from typing import Any, Dict, Iterable

from tools import TOOLS

READ_ONLY_TOOLS = {
    "inspect_scene",
    "inspect_mesh",
    "inspect_scene_health",
    "inspect_scene_settings",
    "inspect_object_relationship",
    "inspect_soccer_components",
}


def execute_read_only_plan(proposal: Dict[str, Any]) -> Dict[str, Any]:
    """Execute only validated evidence requests from a Qwen-derived proposal."""
    if not isinstance(proposal, dict):
        raise ValueError("Proposal must be a dictionary")

    actions = proposal.get("actions", [])
    evidence = proposal.get("evidence", [])
    if actions:
        raise PermissionError("Read-only executor refuses action steps")
    if not isinstance(evidence, list):
        raise ValueError("Evidence must be a list")

    results = []
    for request in evidence:
        if not isinstance(request, dict):
            raise ValueError("Evidence request must be an object")
        tool_name = request.get("tool")
        if tool_name not in READ_ONLY_TOOLS:
            raise PermissionError(f"Tool is not read-only: {tool_name}")
        tool = TOOLS.get(tool_name)
        if tool is None:
            raise ValueError(f"Unknown Atlas tool: {tool_name}")
        arguments = request.get("arguments", {})
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
