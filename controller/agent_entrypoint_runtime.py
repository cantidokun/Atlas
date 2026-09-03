"""Explicit agent-entrypoint execution seam for controller-owned requests.

This module owns the process runtime and its execution context for the default
agent-facing lifecycle. The explicit AgentControllerHost can still supply a
pre-authorized context, while legacy construction remains fail-closed.
"""

from dataclasses import dataclass
from typing import Optional

from controller.agent_execution_context import AgentExecutionContext
from controller.agent_process_runtime import (
    AgentProcessRouteContext,
    AtlasAgentProcessRuntime,
)
from controller.agent_task_request import AgentTaskRequest
from controller.capability_execution import CapabilityExecutionResult


@dataclass(frozen=True)
class AgentEntrypointExecution:
    """Stable result describing whether the entrypoint executed a controller route."""

    classified: AgentProcessRouteContext
    result: Optional[CapabilityExecutionResult]

    @property
    def controller_executed(self) -> bool:
        return self.result is not None


class AtlasAgentEntrypointRuntime:
    """Own one agent-process runtime plus its execution context."""

    def __init__(
        self,
        process: Optional[AtlasAgentProcessRuntime] = None,
        execution_context: Optional[AgentExecutionContext] = None,
    ) -> None:
        if process is None:
            process = AtlasAgentProcessRuntime()

        if not isinstance(process, AtlasAgentProcessRuntime):
            raise TypeError(
                "process must be an AtlasAgentProcessRuntime instance"
            )

        if execution_context is None:
            execution_context = AgentExecutionContext()

        if not isinstance(execution_context, AgentExecutionContext):
            raise TypeError(
                "execution_context must be an AgentExecutionContext instance"
            )

        self._process = process
        self._execution_context = execution_context

    @property
    def process(self) -> AtlasAgentProcessRuntime:
        """Return the process runtime owned by this entrypoint."""
        return self._process

    @property
    def execution_context(self) -> AgentExecutionContext:
        """Return the execution context owned by this entrypoint."""
        return self._execution_context

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
