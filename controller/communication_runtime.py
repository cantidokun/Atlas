"""Controller-facing command service behind the machine communication gateway.

This module is the integration point between the transport-neutral
``ControllerCommunicationGateway`` and the existing Atlas controller.  It
keeps the transport unaware of task state and keeps the controller unaware of
stdin/stdout or another future transport.

Only controller-owned operations are exposed.  The remote caller cannot ask
this service to execute an arbitrary tool; it can create a controller task,
inspect controller state, request the next controller-owned action, and ask
the controller to execute that action through the locally supplied executor.

Model turns are supervised separately from controller execution.  A remote
reasoning model may take time to think, but the communication bridge owns an
explicit deadline and can detect timeout without blocking the controller.
A host may either drive the model lifecycle explicitly or supply a bounded
model executor for a complete local turn.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping

from controller.communication_gateway import CommunicationProtocolError
from controller.communication_turn import ModelTurnSupervisor
from controller.controller_integration import AgentControllerIntegration


ToolExecutor = Callable[[str, Dict[str, Any]], Dict[str, Any]]
ModelTurnExecutor = Callable[[str, float], Any]


@dataclass
class _ControllerSession:
    """State owned by one communication session."""

    file_name: str
    task_text: str
    evidence_ledger: List[dict]
    tool_execution_history: List[dict]
    integration: AgentControllerIntegration
    model_turn: ModelTurnSupervisor


class ControllerCommunicationRuntime:
    """Expose the existing controller through a narrow remote command API."""

    def __init__(
        self,
        execute_tool: ToolExecutor,
        *,
        model_executor: ModelTurnExecutor | None = None,
        clock=None,
    ):
        self._execute_tool = execute_tool
        self._model_executor = model_executor
        self._clock = clock
        self._sessions: Dict[str, _ControllerSession] = {}

    def handle_command(
        self,
        session_id: str,
        request_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle one validated gateway command."""
        del request_id
        command = payload["command"]
        arguments = payload["arguments"]

        if command == "health":
            return {
                "command": command,
                "runtime": "controller_communication",
                "status": "ready",
                "model_executor_configured": self._model_executor is not None,
            }

        if command == "start_task":
            return self._start_task(session_id, arguments)

        if command == "status":
            return self._status(session_id)

        if command == "next_action":
            return self._next_action(session_id)

        if command == "execute_next":
            return self._execute_next(session_id)

        if command == "model_run":
            return self._model_run(session_id, arguments)

        if command == "model_begin":
            return self._model_begin(session_id, arguments)

        if command == "model_heartbeat":
            return self._model_heartbeat(session_id, arguments)

        if command == "model_complete":
            return self._model_complete(session_id, arguments)

        if command == "model_fail":
            return self._model_fail(session_id, arguments)

        if command == "model_cancel":
            return self._model_cancel(session_id, arguments)

        if command == "model_status":
            return self._model_status(session_id)

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
        if any(not isinstance(item, dict) for item in evidence_ledger):
            raise CommunicationProtocolError("start_task.evidence_ledger items must be objects")

        ledger = [dict(item) for item in evidence_ledger]
        history: List[dict] = []
        integration = AgentControllerIntegration(
            file_name=file_name,
            task_text=task_text,
            evidence_ledger=ledger,
            tool_execution_history=history,
        )
        model_turn = (
            ModelTurnSupervisor()
            if self._clock is None
            else ModelTurnSupervisor(clock=self._clock)
        )
        session = _ControllerSession(
            file_name=file_name,
            task_text=task_text,
            evidence_ledger=ledger,
            tool_execution_history=history,
            integration=integration,
            model_turn=model_turn,
        )
        self._sessions[session_id] = session

        return {
            "command": "start_task",
            "status": "started",
            "controller_active": integration.active,
            "controller_complete": integration.complete,
            "next_action": integration.before_model_tool_execution(),
            "model_turn": self._turn_payload(model_turn.snapshot()),
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
            "model_turn": self._turn_payload(session.model_turn.poll()),
        }

    def _next_action(self, session_id: str) -> Dict[str, Any]:
        session = self._require_session(session_id)
        action = session.integration.before_model_tool_execution()
        if action is None:
            return {
                "command": "next_action",
                "status": "model_may_reason",
                "controller_active": session.integration.active,
                "model_turn": self._turn_payload(session.model_turn.poll()),
            }
        return {
            "command": "next_action",
            "status": "controller_action",
            "action": action,
            "model_turn": self._turn_payload(session.model_turn.poll()),
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
            "model_turn": self._turn_payload(session.model_turn.poll()),
        }

    def _model_run(self, session_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Run one bounded local model turn and close its lifecycle deterministically."""
        session = self._require_session(session_id)
        if self._model_executor is None:
            raise CommunicationProtocolError("model executor is not configured")

        turn_id = arguments.get("turn_id")
        message = arguments.get("message")
        timeout_seconds = arguments.get("timeout_seconds")

        if not isinstance(message, str) or not message.strip():
            raise CommunicationProtocolError("model_run.message must be a non-empty string")

        snapshot = session.model_turn.begin(turn_id, timeout_seconds)
        del snapshot

        try:
            raw_result = self._model_executor(message, float(timeout_seconds))
        except Exception as exc:
            snapshot = session.model_turn.fail(turn_id, f"model executor failed: {exc}")
            return {
                "command": "model_run",
                "status": snapshot.state.value,
                "model_turn": self._turn_payload(snapshot),
                "result": {"error": str(exc)},
            }

        result = self._normalize_model_result(raw_result)
        if result["timed_out"]:
            snapshot = session.model_turn.timeout(turn_id, "model executor timed out")
            return {
                "command": "model_run",
                "status": snapshot.state.value,
                "model_turn": self._turn_payload(snapshot),
                "result": result,
            }

        returncode = result["returncode"]
        if returncode != 0:
            error = result["stderr"] or f"model executor exited with code {returncode}"
            snapshot = session.model_turn.fail(turn_id, error)
            return {
                "command": "model_run",
                "status": snapshot.state.value,
                "model_turn": self._turn_payload(snapshot),
                "result": result,
            }

        snapshot = session.model_turn.complete(turn_id)
        return {
            "command": "model_run",
            "status": snapshot.state.value,
            "model_turn": self._turn_payload(snapshot),
            "result": result,
        }

    @staticmethod
    def _normalize_model_result(raw_result: Any) -> Dict[str, Any]:
        if isinstance(raw_result, Mapping):
            result = dict(raw_result)
        else:
            result = {
                "returncode": getattr(raw_result, "returncode", None),
                "stdout": getattr(raw_result, "stdout", ""),
                "stderr": getattr(raw_result, "stderr", ""),
                "timed_out": getattr(raw_result, "timed_out", False),
            }

        return {
            "returncode": result.get("returncode"),
            "stdout": result.get("stdout") or "",
            "stderr": result.get("stderr") or "",
            "timed_out": bool(result.get("timed_out", False)),
        }

    def _model_begin(self, session_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        session = self._require_session(session_id)
        turn_id = arguments.get("turn_id")
        timeout_seconds = arguments.get("timeout_seconds")
        snapshot = session.model_turn.begin(turn_id, timeout_seconds)
        return {
            "command": "model_begin",
            "status": "running",
            "model_turn": self._turn_payload(snapshot),
        }

    def _model_heartbeat(self, session_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        session = self._require_session(session_id)
        snapshot = session.model_turn.heartbeat(arguments.get("turn_id"))
        return {
            "command": "model_heartbeat",
            "status": snapshot.state.value,
            "model_turn": self._turn_payload(snapshot),
        }

    def _model_complete(self, session_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        session = self._require_session(session_id)
        snapshot = session.model_turn.complete(arguments.get("turn_id"))
        return {
            "command": "model_complete",
            "status": snapshot.state.value,
            "model_turn": self._turn_payload(snapshot),
        }

    def _model_fail(self, session_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        session = self._require_session(session_id)
        snapshot = session.model_turn.fail(arguments.get("turn_id"), arguments.get("error"))
        return {
            "command": "model_fail",
            "status": snapshot.state.value,
            "model_turn": self._turn_payload(snapshot),
        }

    def _model_cancel(self, session_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        session = self._require_session(session_id)
        snapshot = session.model_turn.cancel(arguments.get("turn_id"))
        return {
            "command": "model_cancel",
            "status": snapshot.state.value,
            "model_turn": self._turn_payload(snapshot),
        }

    def _model_status(self, session_id: str) -> Dict[str, Any]:
        session = self._require_session(session_id)
        snapshot = session.model_turn.poll()
        return {
            "command": "model_status",
            "status": snapshot.state.value,
            "model_turn": self._turn_payload(snapshot),
        }

    @staticmethod
    def _turn_payload(snapshot) -> Dict[str, Any]:
        return {
            "turn_id": snapshot.turn_id,
            "state": snapshot.state.value,
            "deadline": snapshot.deadline,
            "last_heartbeat": snapshot.last_heartbeat,
            "expired": snapshot.expired,
            "error": snapshot.error,
        }
