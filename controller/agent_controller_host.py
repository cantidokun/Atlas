"""Host-owned lifecycle for the Atlas agent controller boundary.

This layer owns the controller runtime and trusted execution context for
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
from planning.unreal_autonomous_executor import UnrealAutonomousExecutor
from planning.unreal_execution_boundary import UnrealExecutionBoundary
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
            execution_context = execution_context or AgentExecutionContext()
            runtime = AtlasAgentEntrypointRuntime(
                process,
                execution_context=execution_context,
            )
        elif execution_context is None:
            execution_context = runtime.execution_context
        elif execution_context is not runtime.execution_context:
            runtime.bind_execution_context(execution_context)

        self._runtime = runtime
        self._execution_context = execution_context
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

        host = cls(
            process=process,
            execution_context=execution_context,
        )
        host._unreal_integration = integration
        host._trusted_unreal_context = trusted_context
        return host

    def build_unreal_autonomous_executor(
        self,
        *,
        default_authorization_id: Optional[str] = None,
    ) -> UnrealAutonomousExecutor:
        """Construct an UnrealAutonomousExecutor wired through this host's trusted integration.

        Uses the adapter from the host's registered UnrealProductionControllerIntegration
        and binds the host's authoritative authorization ID if not explicitly overridden.
        """
        integration = getattr(self, "_unreal_integration", None)
        if integration is None:
            raise RuntimeError(
                "Unreal autonomous executor requires a host initialized with for_unreal_production"
            )

        runtime_adapter = getattr(integration, "_runtime", None)
        executor = getattr(runtime_adapter, "_executor", None)
        adapter = getattr(executor, "_adapter", None)
        if adapter is None:
            bridge = getattr(runtime_adapter, "_bridge", None)
            if bridge is not None:
                adapter = getattr(bridge._executor, "_adapter", None)

        if adapter is None:
            raise RuntimeError(
                "Could not extract UnrealAdapterProduction from host's integration"
            )

        auth_id = default_authorization_id
        if auth_id is None and hasattr(self, "_trusted_unreal_context"):
            auth = getattr(self._trusted_unreal_context.authorized_production, "authorization", None)
            auth_id = getattr(auth, "authorization_id", None)

        boundary = UnrealExecutionBoundary(adapter)
        return UnrealAutonomousExecutor(boundary, default_authorization_id=auth_id)

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

    def _bind_trusted_request_context(
        self,
        request: AgentTaskRequest,
    ) -> AgentTaskRequest:
        """Return the request with host-owned context bound over model input."""
        trusted_context = self._execution_context.context_for_request(
            request.provider,
        )
        if not trusted_context:
            return request

        context = dict(request.context)
        context.update(trusted_context)
        return AgentTaskRequest(
            capability=request.capability,
            provider=request.provider,
            context=context,
            intent=request.intent,
        )

    def dispatch(
        self,
        request: AgentTaskRequest,
    ) -> AgentEntrypointExecution:
        """Dispatch one explicit controller request through the host runtime.

        The host binds any already-installed trusted provider context before
        handing the request to the entrypoint runtime. Caller/model context can
        therefore supply request metadata, but cannot replace host-owned
        authorization, intent, or other trusted provider values.
        """
        if not isinstance(request, AgentTaskRequest):
            raise TypeError(
                "request must be an AgentTaskRequest instance"
            )

        return self._runtime.dispatch(
            self._bind_trusted_request_context(request)
        )
