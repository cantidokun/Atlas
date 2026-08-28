"""Optional capability routing bootstrap for an Atlas agent process.

This module is intentionally additive. It gives an agent process an explicit
controller capability router, while leaving the existing legacy agent loop and
its midpoint controller integration unchanged.
"""

from dataclasses import dataclass
from typing import Optional

from controller.agent_capability_bootstrap import build_agent_capability_runtime
from controller.agent_entrypoint_router import AgentEntrypointRoute, AgentEntrypointRouter
from controller.atlas_controller_runtime import AtlasControllerRuntime
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration


@dataclass(frozen=True)
class AgentProcessRouteContext:
    """Stable routing context returned by the agent-process boundary."""

    route: AgentEntrypointRoute
    runtime: AtlasControllerRuntime


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

    def route(
        self,
        capability: str,
        *,
        provider: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> AgentProcessRouteContext:
        """Resolve the next agent route without invoking a capability handler."""
        return AgentProcessRouteContext(
            route=self.router.route(
                capability,
                provider=provider,
                context=context,
            ),
            runtime=self.runtime,
        )
