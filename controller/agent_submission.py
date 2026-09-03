"""Provider-neutral submission seam for Atlas agent-originated tasks.

This module is deliberately thin. It combines construction of the canonical
AgentTaskRequest with dispatch through the already-established agent entrypoint
runtime.

It does not:
- select capabilities
- create authorizations
- execute provider work directly
- alter the legacy Blender/Qwen agent loop
"""

from typing import Any, Mapping, Optional

from controller.agent_entrypoint_adapter import build_agent_task_request
from controller.agent_entrypoint_runtime import (
    AgentEntrypointExecution,
    AtlasAgentEntrypointRuntime,
)


def submit_agent_task(
    runtime: AtlasAgentEntrypointRuntime,
    capability: str,
    *,
    provider: Optional[str] = None,
    context: Optional[Mapping[str, Any]] = None,
    intent: Optional[str] = None,
) -> AgentEntrypointExecution:
    """Submit one explicit agent capability intent to the Atlas controller boundary."""
    if not isinstance(runtime, AtlasAgentEntrypointRuntime):
        raise TypeError(
            "runtime must be an AtlasAgentEntrypointRuntime instance"
        )

    request = build_agent_task_request(
        capability,
        provider=provider,
        context=context,
        intent=intent,
    )

    return runtime.dispatch(request)
