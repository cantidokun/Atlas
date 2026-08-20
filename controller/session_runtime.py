"""Session-backed controller runtime composition without task-specific knowledge."""

from __future__ import annotations

from typing import Any, Dict

from controller.communication_gateway import ControllerCommunicationGateway


class SessionControllerRuntime:
    """Bind communication sessions to a host command handler."""

    def __init__(self, handle_command):
        self.gateway = ControllerCommunicationGateway(handle_command)

    def open(self, session_id: str) -> Dict[str, Any]:
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session_id must be a non-empty string")
        return self.gateway.handle_message({
            "protocol_version": "1",
            "id": f"open:{session_id}",
            "type": "open",
            "payload": {"session_id": session_id},
        })

    def command(self, session_id: str, request_id: str, command: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return self.gateway.handle_message({
            "protocol_version": "1",
            "id": request_id,
            "type": "command",
            "session_id": session_id,
            "payload": {"command": command, "arguments": arguments},
        })

    def close(self, session_id: str, request_id: str = "close") -> Dict[str, Any]:
        return self.gateway.handle_message({
            "protocol_version": "1",
            "id": request_id,
            "type": "close",
            "session_id": session_id,
        })
