"""Pure routing facade for the Atlas agent entrypoint.

The router only classifies an explicit capability request. It does not execute
provider work, create authorizations, or alter the legacy controller path.
"""

from dataclasses import dataclass
from typing import Optional

from controller.agent_task_request import AgentTaskRequest
from controller.atlas_controller_runtime import AtlasControllerRuntime
from controller.capability_selection import CapabilitySelection


@dataclass(frozen=True)
class AgentEntrypointRoute:
    """Stable route decision returned to the outer agent process."""

    route: str
    selection: CapabilitySelection

    @property
    def controller_owned(self) -> bool:
        return self.route == "controller"


class AgentEntrypointRouter:
    """Select controller capability only for an explicitly matched request."""

    def __init__(self, runtime: AtlasControllerRuntime) -> None:
        if not isinstance(runtime, AtlasControllerRuntime):
            raise TypeError("runtime must be an AtlasControllerRuntime instance")
        self._runtime = runtime

    def route(
        self,
        capability: str,
        *,
        provider: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> AgentEntrypointRoute:
        """Return a route without invoking the selected capability handler."""
        selection = self._runtime.select_capability(
            capability,
            provider=provider,
            context=context,
        )
        return AgentEntrypointRoute(
            route="controller" if selection.matched else "agent",
            selection=selection,
        )

    def route_request(self, request: AgentTaskRequest) -> AgentEntrypointRoute:
        """Route one explicit agent task request without reconstructing its fields."""
        if not isinstance(request, AgentTaskRequest):
            raise TypeError("request must be an AgentTaskRequest instance")
        return self.route(**request.routing_kwargs())
