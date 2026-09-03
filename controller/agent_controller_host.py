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
from controller.agent_task_request import AgentTaskRequest
from controller.trusted_unreal_context import TrustedUnrealContext
from planning.unreal_production_controller_integration import (
    UnrealProductionControllerIntegration,
)


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

    @classmethod
    def for_unreal_production(
        cls,
        integration: UnrealProductionControllerIntegration,
        trusted_context: TrustedUnrealContext,
    ) -> "AgentControllerHost":
        """Build a host bound to one real Unreal production integration.

        The integration must already embody the production execution boundary,
        while the trusted context must already contain the host-approved
        authorization, intent, and sequence binding. This constructor performs
        no planning or authorization itself.
        """
        if not isinstance(
            integration,
            UnrealProductionControllerIntegration,
        ):
            raise TypeError(
                "integration must be a UnrealProductionControllerIntegration instance"
            )

        if not isinstance(trusted_context, TrustedUnrealContext):
            raise TypeError(
                "trusted_context must be a TrustedUnrealContext instance"
            )

        process = AtlasAgentProcessRuntime(
            unreal_production=integration,
        )
        execution_context = AgentExecutionContext()
        execution_context.install_unreal(trusted_context)

        return cls(
            process=process,
            execution_context=execution_context,
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

    def dispatch(
        self,
        request: AgentTaskRequest,
    ) -> AgentEntrypointExecution:
        """Dispatch one explicit controller request through the host runtime.

        This is the drop-in entrypoint seam for agent-facing code. The host
        retains ownership of the process runtime and trusted execution
        context while delegating request classification/execution to the
        existing entrypoint runtime.
        """
        if not isinstance(request, AgentTaskRequest):
            raise TypeError(
                "request must be an AgentTaskRequest instance"
            )
        return self._runtime.dispatch(request)
