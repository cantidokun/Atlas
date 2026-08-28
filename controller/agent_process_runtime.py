"""Agent-process boundary for normalized Atlas task requests."""

from dataclasses import dataclass
from typing import Optional

from controller.agent_capability_bootstrap import build_agent_capability_runtime
from controller.agent_entrypoint_router import AgentEntrypointRoute, AgentEntrypointRouter
from controller.agent_task_request import AgentTaskRequest
from controller.atlas_controller_runtime import AtlasControllerRuntime
from controller.capability_execution import CapabilityExecutionResult
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration


@dataclass(frozen=True)
class AgentProcessRouteContext:
    """Stable routing context returned by the agent-process boundary."""

    route: AgentEntrypointRoute
    runtime: AtlasControllerRuntime
    request: AgentTaskRequest

    @property
    def controller_owned(self) -> bool:
        return self.route.controller_owned


class AtlasAgentProcessRuntime:
    """Own capability routing for one agent process without executing capabilities."""

    def __init__(
        self,
        *,
        unreal_production: Optional[UnrealProductionControllerIntegration] = None,
    ) -> None:
        self.runtime = build_agent_capability_runtime(
            unreal_production=unreal_production,
        )
        self.router = AgentEntrypointRouter(self.runtime)

    def classify(self, request: AgentTaskRequest) -> AgentProcessRouteContext:
        """Resolve a normalized task request without invoking a capability handler."""
        if not isinstance(request, AgentTaskRequest):
            raise TypeError("request must be an AgentTaskRequest instance")
        return AgentProcessRouteContext(
            route=self.router.route_request(request),
            runtime=self.runtime,
            request=request,
        )

    def route(
        self,
        capability: str,
        *,
        provider: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> AgentProcessRouteContext:
        """Backward-compatible convenience wrapper for explicit capability routing."""
        return self.classify(
            AgentTaskRequest(
                capability=capability,
                provider=provider,
                context={} if context is None else context,
            )
        )

    def execute_classified(
        self,
        classified: AgentProcessRouteContext,
    ) -> CapabilityExecutionResult:
        """Execute a previously classified controller-owned request."""
        if not isinstance(classified, AgentProcessRouteContext):
            raise TypeError("classified must be an AgentProcessRouteContext instance")
        if not classified.controller_owned:
            raise ValueError("only controller-owned routes may be executed here")
        if classified.runtime is not self.runtime:
            raise ValueError("classified route belongs to a different agent-process runtime")
        return self.runtime.execute_request(classified.request)
