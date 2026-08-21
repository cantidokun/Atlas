"""Safe machine-to-controller communication boundary.

This module owns protocol/session semantics only.  It deliberately does not
know about Blender, Unreal, Ollama, HTTP, sockets, or a particular task.

A host supplies a command handler.  The gateway validates every message,
creates an explicit session, and deduplicates request IDs so a transport retry
cannot cause the same controller command to execute twice.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from controller.command_registry import ControllerCommandRegistry, CommandRegistryError


PROTOCOL_VERSION = "1"

CommandHandler = Callable[[str, str, Dict[str, Any]], Dict[str, Any]]


class CommunicationProtocolError(ValueError):
    """Raised when a message violates the controller communication contract."""


@dataclass
class _Session:
    session_id: str
    closed: bool = False
    request_fingerprints: Dict[str, str] = field(default_factory=dict)
    responses: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class ControllerCommunicationGateway:
    """Validate and dispatch machine-facing controller messages.

    The gateway is intentionally synchronous.  The caller owns the transport
    and may run this gateway over stdin/stdout, a local socket, or another
    process boundary without changing protocol or controller semantics.

    When a command registry is supplied, command dispatch is fail-closed:
    unknown commands are rejected before the host handler can see them.
    """

    def __init__(
        self,
        handle_command: CommandHandler,
        command_registry: Optional[ControllerCommandRegistry] = None,
    ):
        self._handle_command = handle_command
        self._command_registry = command_registry
        self._sessions: Dict[str, _Session] = {}

    def open_session(self, requested_session_id: Optional[str] = None) -> Dict[str, Any]:
        session_id = requested_session_id or uuid.uuid4().hex
        if not isinstance(session_id, str) or not session_id:
            raise CommunicationProtocolError("session_id must be a non-empty string")
        if session_id in self._sessions and not self._sessions[session_id].closed:
            raise CommunicationProtocolError("session_id is already active")

        self._sessions[session_id] = _Session(session_id=session_id)
        return {
            "protocol_version": PROTOCOL_VERSION,
            "status": "ok",
            "event": "session_opened",
            "session_id": session_id,
        }

    def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle one decoded protocol message and return one response."""
        if not isinstance(message, dict):
            raise CommunicationProtocolError("message must be an object")

        if message.get("protocol_version") != PROTOCOL_VERSION:
            raise CommunicationProtocolError("unsupported protocol_version")

        message_type = message.get("type")
        if message_type == "open":
            request_id = self._require_id(message)
            payload = message.get("payload") or {}
            if not isinstance(payload, dict):
                raise CommunicationProtocolError("open payload must be an object")
            response = self.open_session(payload.get("session_id"))
            response["id"] = request_id
            return response

        session_id = message.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise CommunicationProtocolError("session_id is required")

        session = self._sessions.get(session_id)
        if session is None:
            raise CommunicationProtocolError("unknown session_id")

        request_id = self._require_id(message)

        if message_type == "close":
            if session.closed:
                return self._response(session_id, request_id, "ok", {"event": "session_closed"})
            session.closed = True
            return self._response(session_id, request_id, "ok", {"event": "session_closed"})

        if message_type != "command":
            raise CommunicationProtocolError("unsupported message type")

        if session.closed:
            raise CommunicationProtocolError("session is closed")

        payload = message.get("payload")
        if not isinstance(payload, dict):
            raise CommunicationProtocolError("command payload must be an object")

        fingerprint = self._fingerprint(message_type, session_id, payload)
        previous = session.request_fingerprints.get(request_id)
        if previous is not None:
            if previous != fingerprint:
                raise CommunicationProtocolError("request_id was reused with different content")
            return session.responses[request_id]

        command = payload.get("command")
        arguments = payload.get("arguments", {})
        if not isinstance(command, str) or not command:
            raise CommunicationProtocolError("payload.command must be a non-empty string")
        if not isinstance(arguments, dict):
            raise CommunicationProtocolError("payload.arguments must be an object")

        if self._command_registry is not None:
            try:
                self._command_registry.resolve(command)
            except CommandRegistryError as exc:
                raise CommunicationProtocolError(str(exc)) from exc

        result = self._handle_command(session_id, request_id, {
            "command": command,
            "arguments": arguments,
        })
        if not isinstance(result, dict):
            raise CommunicationProtocolError("command handler must return an object")

        response = self._response(session_id, request_id, "ok", result)
        session.request_fingerprints[request_id] = fingerprint
        session.responses[request_id] = response
        return response

    @staticmethod
    def _require_id(message: Dict[str, Any]) -> str:
        request_id = message.get("id")
        if not isinstance(request_id, str) or not request_id:
            raise CommunicationProtocolError("id must be a non-empty string")
        return request_id

    @staticmethod
    def _fingerprint(message_type: str, session_id: str, payload: Dict[str, Any]) -> str:
        canonical = json.dumps(
            {"type": message_type, "session_id": session_id, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _response(
        session_id: str,
        request_id: str,
        status: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "protocol_version": PROTOCOL_VERSION,
            "status": status,
            "id": request_id,
            "session_id": session_id,
            "payload": payload,
        }
