"""Explicit contract for agent-to-controller capability handoff.

This module contains no provider execution logic. It documents the narrow
boundary at which an outer agent may hand an explicit AgentTaskRequest to the
Atlas controller entrypoint runtime.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from controller.agent_entrypoint_runtime import (
    AgentEntrypointExecution,
    AtlasAgentEntrypointRuntime,
)
from controller.agent_task_request import AgentTaskRequest


@dataclass(frozen=True)
class AgentControllerHandoff:
    """Stable input wrapper for an explicit controller-owned task request."""

    request: AgentTaskRequest

    @classmethod
    def build(
        cls,
        capability: str,
        *,
        provider: Optional[str] = None,
        context: Optional[Mapping[str, Any]] = None,
        intent: Optional[str] = None,
    ) -> "AgentControllerHandoff":
        """Construct one explicit task request without selecting or executing a capability."""
        return cls(
            AgentTaskRequest(
                capability=capability,
                provider=provider,
                context=dict(context or {}),
                intent=intent,
            )
        )


def dispatch_controller_handoff(
    runtime: AtlasAgentEntrypointRuntime,
    handoff: AgentControllerHandoff,
) -> AgentEntrypointExecution:
    """Dispatch one explicit controller handoff through the established entrypoint runtime."""
    if not isinstance(runtime, AtlasAgentEntrypointRuntime):
        raise TypeError("runtime must be an AtlasAgentEntrypointRuntime instance")
    if not isinstance(handoff, AgentControllerHandoff):
        raise TypeError("handoff must be an AgentControllerHandoff instance")
    return runtime.dispatch(handoff.request)
