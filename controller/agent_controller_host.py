"""Host-owned lifecycle for the Atlas agent controller boundary.

This layer owns the controller runtime and the trusted execution context for
one agent execution. It deliberately does not create authorization; callers
must install already-authorized provider context explicitly.
"""

from typing import Optional

from controller.agent_controller_loop import AgentControllerLoopAdapter
from controller.agent_entrypoint_runtime import (
    AgentEntrypointExecution,
    AtlasAgentEntrypointRuntime,
)
from controller.agent_execution_context import AgentExecutionContext
from controller.agent_process_runtime import AtlasAgentProcessRuntime
from controller.trusted_unreal_context import TrustedUnrealContext


class AgentControllerHost:
    """Own one controller runtime plus its trusted execution context."""

    def __init__(
        self,
        *,
        runtime: Optional[AtlasAgentEntrypointRuntime] = None,
        execution_context: Optional[AgentExecutionContext] = None,
        process: Optional[AtlasAgentProcessRuntime] = None,
    ) -> None:
        if runtime is not None and not isinstance(
            runtime,
            AtlasAgentEntrypointRuntime,
        ):
            raise TypeError(
                "runtime must be an AtlasAgentEntrypointRuntime instance"
            )

        if process is not None and not isinstance(
            process,
            AtlasAgentProcessRuntime,
        ):
            raise TypeError(
                "process must be an AtlasAgentProcessRuntime instance"
            )

        if execution_context is not None and not isinstance(
            execution_context,
            AgentExecutionContext,
        ):
            raise TypeError(
                "execution_context must be an AgentExecutionContext instance"
            )

        if runtime is not None and process is not None:
            raise ValueError(
                "provide runtime or process, not both"
            )

        if runtime is None:
            runtime = AtlasAgentEntrypointRuntime(process)

        self._runtime = runtime
        self._execution_context = (
            execution_context or AgentExecutionContext()
        )
        self._loop = AgentControllerLoopAdapter(
            self._runtime,
            execution_context=self._execution_context,
        )

    @property
    def runtime(self) -> AtlasAgentEntrypointRuntime:
        return self._runtime

    @property
    def process(self) -> AtlasAgentProcessRuntime:
        return self._runtime.process

    @property
    def execution_context(self) -> AgentExecutionContext:
        return self._execution_context

    @property
    def loop(self) -> AgentControllerLoopAdapter:
        return self._loop

    def install_unreal_context(
        self,
        context: TrustedUnrealContext,
    ) -> None:
        """Install an already-authorized Unreal context for this run."""
        self._execution_context.install_unreal(context)

    def process_model_response(
        self,
        content: str,
    ) -> Optional[AgentEntrypointExecution]:
        """Process one model response at the controller boundary."""
        return self._loop.process_model_response(content)
