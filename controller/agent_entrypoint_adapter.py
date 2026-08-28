"""Explicit task-request adapter for the Atlas agent entrypoint.

This module does not execute controller capabilities and does not alter the
legacy agent/tool loop. It provides a small, provider-neutral way for an outer
entrypoint to turn an already-decided capability intent into the canonical
``AgentTaskRequest`` consumed by the controller routing stack.
"""

from typing import Any, Mapping, Optional

from controller.agent_task_request import AgentTaskRequest


def build_agent_task_request(
    capability: str,
    *,
    provider: Optional[str] = None,
    context: Optional[Mapping[str, Any]] = None,
    intent: Optional[str] = None,
) -> AgentTaskRequest:
    """Build one explicit agent task request without routing or execution."""
    if context is None:
        context_dict = {}
    elif isinstance(context, dict):
        context_dict = dict(context)
    else:
        raise TypeError("context must be a dictionary when supplied")

    return AgentTaskRequest(
        capability=capability,
        provider=provider,
        context=context_dict,
        intent=intent,
    )
