"""Explicit agent-to-controller production request boundary.

This module provides the smallest concrete bridge for an agent-originated
Unreal production request. It intentionally accepts only the normalized
AgentControllerHandoff contract and delegates to the existing controller
entrypoint runtime; it does not re-select or directly execute provider capabilities.
"""

from controller.agent_entrypoint_contract import AgentControllerHandoff
from controller.agent_entrypoint_runtime import AtlasAgentEntrypointRuntime


class AgentControllerProductionRequest:
    """Submit one explicit controller-owned production request."""

    def __init__(self, runtime: AtlasAgentEntrypointRuntime) -> None:
        self.runtime = runtime

    def submit(self, handoff: AgentControllerHandoff):
        if not isinstance(handoff, AgentControllerHandoff):
            raise TypeError("handoff must be an AgentControllerHandoff")
        return self.runtime.dispatch(handoff.request)
