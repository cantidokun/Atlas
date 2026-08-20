"""Local communication bridge for the Atlas controller.

The bridge is the boundary between an external model/client and the
transport-neutral controller session.  It deliberately does not know about
Blender, Unreal, HTTP, sockets, or any model provider.

A host supplies the tool executor.  The bridge owns request identity and
serializes controller progress into protocol responses, removing the need for
a human to relay each controller action between the model and the local
machine.
"""

from typing import Any, Callable, Dict, Optional

from controller_runtime import ControllerRuntime
from controller_session import ControllerSession, ProtocolError


ToolExecutor = Callable[[str, Dict[str, Any]], Dict[str, Any]]


class ControllerBridge:
    """Connect protocol messages to one deterministic controller runtime."""

    def __init__(self, execute: ToolExecutor):
        self.session = ControllerSession()
        self.execute = execute
        self._runtimes: Dict[str, ControllerRuntime] = {}

    def receive(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Accept one protocol message and return its next protocol response."""
        message_type = message.get("type")

        if message_type == "instruction":
            request = self.session.accept(message)
            file_name = request.payload.get("file_name")

            if not isinstance(file_name, str) or not file_name:
                return self.session.respond(
                    request.request_id,
                    "error",
                    error={"code": "invalid_payload", "message": "Instruction requires file_name."},
                )

            self._runtimes[request.request_id] = ControllerRuntime(file_name)
            return self._advance(request.request_id)

        if message_type == "close":
            self.session.close()
            return {
                "protocol_version": "1",
                "session_id": self.session.session_id,
                "status": "complete",
                "event": "session_closed",
            }

        raise ProtocolError(f"Unsupported incoming message type: {message_type!r}.")

    def _advance(self, request_id: str) -> Dict[str, Any]:
        runtime = self._runtimes[request_id]
        result = runtime.step(self.execute)

        if result["status"] == "error":
            return self.session.respond(
                request_id,
                "error",
                phase=result.get("phase"),
                error=result.get("error", {"code": "controller_error"}),
            )

        if result["status"] == "complete":
            return self.session.respond(
                request_id,
                "complete",
                phase=result.get("phase"),
                result=result,
            )

        return self.session.respond(
            request_id,
            "progress",
            phase=result.get("phase"),
            result=result,
        )


def handle_json_line(bridge: ControllerBridge, line: str) -> Dict[str, Any]:
    """Decode one JSON protocol line and dispatch it through the bridge."""
    import json

    try:
        message = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"Invalid JSON: {exc.msg}.") from exc

    if not isinstance(message, dict):
        raise ProtocolError("Protocol message must be a JSON object.")

    return bridge.receive(message)


def encode_response(response: Dict[str, Any]) -> str:
    """Encode one bridge response as a single JSON line."""
    import json

    return json.dumps(response, separators=(",", ":"), sort_keys=True)
