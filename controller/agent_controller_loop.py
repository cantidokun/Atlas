
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
from controller.agent_controller_intent import AgentControllerIntent
from controller.agent_execution_context import AgentExecutionContext
from controller.agent_entrypoint_runtime import (
    AgentEntrypointExecution,
    AtlasAgentEntrypointRuntime,
)
from controller.agent_trusted_context import AgentTrustedContext
from controller.trusted_unreal_context import TrustedUnrealContext


class AgentControllerLoopAdapter:
    """Expose one explicit controller hook for an agent reasoning loop."""

    def __init__(
        self,
        runtime: AtlasAgentEntrypointRuntime,
        *,
        trusted_context_provider: Optional[TrustedContextProvider] = None,
        execution_context: Optional[AgentExecutionContext] = None,
    ) -> None:
        if not isinstance(runtime, AtlasAgentEntrypointRuntime):
            raise TypeError(
                "runtime must be an AtlasAgentEntrypointRuntime"
            )

        if (
            trusted_context_provider is not None
            and execution_context is not None
        ):
            raise ValueError(
                "provide trusted_context_provider or execution_context, not both"
            )

        if execution_context is not None and not isinstance(
            execution_context,
            AgentExecutionContext,
        ):
            raise TypeError(
                "execution_context must be an AgentExecutionContext instance"
            )

        # The real agent-facing loop always owns an execution context when
        # callers have not supplied a legacy provider callback. The default
        # context is deliberately empty, so protected capabilities remain
        # fail-closed until the host installs already-authorized state.
        if (
            execution_context is None
            and trusted_context_provider is None
        ):
            execution_context = AgentExecutionContext()

        self._runtime = runtime
        self._execution_context = execution_context

        if execution_context is not None:
            self._trusted_context_provider = (
                execution_context.context_for_controller_intent
            )
        else:
            self._trusted_context_provider = trusted_context_provider

    @property
    def runtime(self) -> AtlasAgentEntrypointRuntime:
        return self._runtime

    @property
    def execution_context(self) -> Optional[AgentExecutionContext]:
        return self._execution_context

    def install_unreal_context(
        self,
        context: TrustedUnrealContext,
    ) -> None:
        """Install an already-authorized Unreal context for this loop."""
        if self._execution_context is None:
            raise RuntimeError(
                "cannot install trusted context when a legacy trusted_context_provider is configured"
            )

        self._execution_context.install_unreal(context)

    def install_trusted_context(
        self,
        provider: str,
        context: AgentTrustedContext,
    ) -> None:
        """Install typed trusted provider state for this loop."""
        if self._execution_context is None:
            raise RuntimeError(
                "cannot install trusted context when a legacy trusted_context_provider is configured"
            )

        self._execution_context.install(provider, context)

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
