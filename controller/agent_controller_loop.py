
"""Agent-loop adapter for explicit controller requests.

This adapter is intentionally narrow. It does not implement model reasoning,
Blender tool execution, authorization, or capability selection. It simply
hands a model response to the existing controller-response bridge.

Ordinary model responses return None and remain available to the existing
agent tool loop unchanged.
"""

from typing import Any, Mapping, Optional

from controller.agent_controller_response_bridge import (
    TrustedContextProvider,
    submit_controller_request_from_model_output,
)
from controller.agent_entrypoint_runtime import (
    AgentEntrypointExecution,
    AtlasAgentEntrypointRuntime,
)


class AgentControllerLoopAdapter:
    """Expose one explicit controller hook for an agent reasoning loop."""

    def __init__(
        self,
        runtime: AtlasAgentEntrypointRuntime,
        *,
        trusted_context_provider: Optional[TrustedContextProvider] = None,
    ) -> None:
        if not isinstance(runtime, AtlasAgentEntrypointRuntime):
            raise TypeError(
                "runtime must be an AtlasAgentEntrypointRuntime"
            )

        self._runtime = runtime
        self._trusted_context_provider = trusted_context_provider

    @property
    def runtime(self) -> AtlasAgentEntrypointRuntime:
        return self._runtime

    def process_model_response(
        self,
        content: str,
    ) -> Optional[AgentEntrypointExecution]:
        """Process one model response for an explicit controller request."""
        return submit_controller_request_from_model_output(
            self._runtime,
            content,
            trusted_context_provider=self._trusted_context_provider,
        )
