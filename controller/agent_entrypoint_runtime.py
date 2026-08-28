"""Explicit agent-entrypoint execution seam for controller-owned requests.

This module is intentionally thin. It converts an explicit task request into
an agent-process classification and, only for controller-owned routes, invokes
the already-admitted controller execution boundary. Legacy agent routes are
returned to the caller without execution.
"""

from dataclasses import dataclass

from controller.agent_process_runtime import AgentProcessRouteContext, AtlasAgentProcessRuntime
from controller.agent_task_request import AgentTaskRequest
from controller.capability_execution import CapabilityExecutionResult


@dataclass(frozen=True)
class AgentEntrypointExecution:
    """Stable result describing whether the entrypoint executed a controller route."""

    classified: AgentProcessRouteContext
    result: CapabilityExecutionResult | None

    @property
    def controller_executed(self) -> bool:
        return self.result is not None


class AtlasAgentEntrypointRuntime:
    """Execute explicit controller-owned agent requests without touching legacy routes."""

    def __init__(self, process: AtlasAgentProcessRuntime) -> None:
        if not isinstance(process, AtlasAgentProcessRuntime):
            raise TypeError("process must be an AtlasAgentProcessRuntime instance")
        self._process = process

    def dispatch(self, request: AgentTaskRequest) -> AgentEntrypointExecution:
        """Classify one request and execute it only when the route is controller-owned."""
        if not isinstance(request, AgentTaskRequest):
            raise TypeError("request must be an AgentTaskRequest instance")
        classified = self._process.classify(request)
        if not classified.controller_owned:
            return AgentEntrypointExecution(classified=classified, result=None)
        return AgentEntrypointExecution(
            classified=classified,
            result=self._process.execute_classified(classified),
        )
