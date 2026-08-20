"""Controller-facing command service behind the machine communication gateway.

This module is the integration point between the transport-neutral
``ControllerCommunicationGateway`` and the existing Atlas controller.  It
keeps the transport unaware of task state and keeps the controller unaware of
stdin/stdout or another future transport.

Only controller-owned operations are exposed.  The remote caller cannot ask
this service to execute an arbitrary tool; it can create a controller task,
inspect controller state, request the next controller-owned action, and ask
the controller to execute that action through the locally supplied executor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from controller.controller_integration import AgentControllerIntegration
from controller.communication_gateway import CommunicationProtocolError


ToolExecutor = Callable[[str, Dict[str, Any]], Dict[str, Any]]


@dataclass
class _ControllerSession:
    """State owned by one communication session."""

    file_name: str
    task_text: str
    evidence_ledger: List[dict]
    tool_execution_history: List[dict]
    integration: AgentControllerIntegration


class ControllerCommunicationRuntime:
    """Expose the existing controller through a narrow remote command API."""

    def __init__(self, execute_tool: ToolExecutor):
        self._execute_tool = execute_tool
        self._sessions: Dict[str, _ControllerSession] = {}

    def handle_command(
        self,
        session_id: str,
        request_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle one validated gateway command."""
        command = payload["command"]
        arguments = payload["arguments"]

        if command == "health":
            return {
                "command": command,
                "runtime": "controller_communication",
                "status": "ready",
            }

        if command == "start_task":
            return self._start_task(session_id, arguments)

        if command == "status":
            return self._status(session_id)

        if command == "next_action":
            return self._next_action(session_id)

        if command == "execute_next":
            return self._execute_next(session_id)

        raise CommunicationProtocolError("unsupported controller command")

    def _start_task(self, session_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if session_id in self._sessions:
            raise CommunicationProtocolError("controller task is already active")

        file_name = arguments.get("file_name")
        task_text = arguments.get("task_text")
        evidence_ledger = arguments.get("evidence_ledger", [])

        if not isinstance(file_name, str) or not file_name:
            raise CommunicationProtocolError("start_task.file_name must be a non-empty string")
        if not isinstance(task_text, str) or not task_text:
            raise CommunicationProtocolError("start_task.task_text must be a non-empty string")
        if not isinstance(evidence_ledger, list):
            raise CommunicationProtocolError("start_task.evidence_ledger must be a list")

        ledger = [dict(item) for item in evidence_ledger if isinstance(item, dict)]
        history: List[dict] = []
        integration = AgentControllerIntegration(
            file_name=file_name,
            task_text=task_text,
            evidence_ledger=ledger,
            tool_execution_history=history,
        )
        session = _ControllerSession(
            file_name=file_name,
            task_text=task_text,
            evidence_ledger=ledger,
            tool_execution_history=history,
            integration=integration,
        )
        self._sessions[session_id] = session

        return {
            "command": "start_task",
            "status": "started",
            "controller_active": integration.active,
            "controller_complete": integration.complete,
            "next_action": integration.before_model_tool_execution(),
        }

    def _require_session(self, session_id: str) -> _ControllerSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise CommunicationProtocolError("no controller task is active for this session")
        return session

    def _status(self, session_id: str) -> Dict[str, Any]:
        session = self._require_session(session_id)
        next_action = session.integration.before_model_tool_execution()
        return {
            "command": "status",
            "status": "active",
            "controller_active": session.integration.active,
            "controller_complete": session.integration.complete,
            "next_action": next_action,
            "evidence_count": len(session.evidence_ledger),
            "tool_execution_count": len(session.tool_execution_history),
        }

    def _next_action(self, session_id: str) -> Dict[str, Any]:
        session = self._require_session(session_id)
        action = session.integration.before_model_tool_execution()
        if action is None:
            return {
                "command": "next_action",
                "status": "model_may_reason",
                "controller_active": session.integration.active,
            }
        return {
            "command": "next_action",
            "status": "controller_action",
            "action": action,
        }

    def _execute_next(self, session_id: str) -> Dict[str, Any]:
        session = self._require_session(session_id)
        if not session.integration.active:
            return {
                "command": "execute_next",
                "status": "inactive",
                "controller_active": False,
            }

        if session.integration.complete:
            return {
                "command": "execute_next",
                "status": "complete",
                "controller_complete": True,
            }

        result = session.integration.execute_forced_action(self._execute_tool)
        return {
            "command": "execute_next",
            "status": result.get("status"),
            "controller_active": session.integration.active,
            "controller_complete": session.integration.complete,
            "result": result,
        }
