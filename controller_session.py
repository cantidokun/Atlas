"""Transport-neutral communication session for the Atlas controller.

This module is deliberately separate from ``ControllerRuntime``.  It owns
message validation and request lifecycle state, but it does not execute tools
and it does not make model decisions.

The transport (HTTP, socket, named pipe, etc.) can translate its native
messages into this contract without changing controller execution logic.
"""

from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Dict, Optional
from uuid import uuid4


PROTOCOL_VERSION = "1"
REQUEST_TYPE = "instruction"
TERMINAL_STATUSES = {"complete", "error"}


class ProtocolError(ValueError):
    """Raised when a bridge message violates the controller protocol."""


@dataclass
class SessionRequest:
    """Validated request tracked for the lifetime of one controller action."""

    request_id: str
    payload: Dict[str, Any]
    created_at: float = field(default_factory=monotonic)
    status: str = "pending"

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES


@dataclass
class ControllerSession:
    """Transport-neutral session state for one controller conversation."""

    session_id: str = field(default_factory=lambda: str(uuid4()))
    requests: Dict[str, SessionRequest] = field(default_factory=dict)
    closed: bool = False

    def accept(self, message: Dict[str, Any]) -> SessionRequest:
        """Validate and register one incoming instruction."""
        if self.closed:
            raise ProtocolError("Session is closed.")

        request_id = message.get("id")
        message_type = message.get("type")
        payload = message.get("payload")
        version = message.get("protocol_version", PROTOCOL_VERSION)

        if not isinstance(request_id, str) or not request_id:
            raise ProtocolError("Message requires a non-empty string id.")

        if not isinstance(message_type, str) or message_type != REQUEST_TYPE:
            raise ProtocolError(f"Unsupported message type: {message_type!r}.")

        if version != PROTOCOL_VERSION:
            raise ProtocolError(f"Unsupported protocol version: {version!r}.")

        if not isinstance(payload, dict):
            raise ProtocolError("Message payload must be an object.")

        if request_id in self.requests:
            raise ProtocolError(f"Duplicate request id: {request_id}.")

        request = SessionRequest(request_id=request_id, payload=payload)
        self.requests[request_id] = request
        return request

    def respond(
        self,
        request_id: str,
        status: str,
        *,
        phase: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build and record a response for a registered request."""
        request = self.requests.get(request_id)
        if request is None:
            raise ProtocolError(f"Unknown request id: {request_id}.")

        if request.terminal:
            raise ProtocolError(f"Request {request_id} is already terminal.")

        if status not in {"progress", "complete", "error"}:
            raise ProtocolError(f"Unsupported response status: {status!r}.")

        if status == "error" and error is None:
            raise ProtocolError("Error responses require an error object.")

        if status != "error" and error is not None:
            raise ProtocolError("Only error responses may contain an error object.")

        request.status = status

        response: Dict[str, Any] = {
            "protocol_version": PROTOCOL_VERSION,
            "session_id": self.session_id,
            "id": request_id,
            "status": status,
        }

        if phase is not None:
            response["phase"] = phase
        if result is not None:
            response["result"] = result
        if error is not None:
            response["error"] = error

        return response

    def close(self) -> None:
        """Close the session and reject all future incoming requests."""
        self.closed = True


def make_instruction(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a protocol-compliant instruction message."""
    if not isinstance(payload, dict):
        raise ProtocolError("Instruction payload must be an object.")

    return {
        "protocol_version": PROTOCOL_VERSION,
        "id": str(uuid4()),
        "type": REQUEST_TYPE,
        "payload": payload,
    }
