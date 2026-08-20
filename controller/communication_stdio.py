"""Dependency-free stdin/stdout transport for ControllerCommunicationGateway."""

from __future__ import annotations

import json
import sys
from typing import Callable, Dict, Iterable, TextIO

from controller.communication_gateway import (
    CommunicationProtocolError,
    ControllerCommunicationGateway,
)


def process_lines(
    gateway: ControllerCommunicationGateway,
    lines: Iterable[str],
    output: TextIO,
) -> None:
    """Read JSON objects from lines and emit one JSON response per message.

    A malformed message never reaches the command handler.  When a usable
    request id can be recovered, the error response carries that id so the
    remote caller can correlate the failure without human intervention.
    """
    for line in lines:
        if not line.strip():
            continue

        try:
            message = json.loads(line)
            response = gateway.handle_message(message)
        except (json.JSONDecodeError, CommunicationProtocolError) as exc:
            response = _error_response(message if "message" in locals() else None, str(exc))

        output.write(json.dumps(response, sort_keys=True, separators=(",", ":")) + "\n")
        output.flush()

        if "message" in locals():
            del message


def run_stdio(
    handle_command: Callable[[str, str, Dict[str, object]], Dict[str, object]],
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
) -> None:
    """Run the gateway as a local process using newline-delimited JSON."""
    gateway = ControllerCommunicationGateway(handle_command)
    process_lines(gateway, stdin, stdout)


def _error_response(message: object, error: str) -> Dict[str, object]:
    response: Dict[str, object] = {
        "protocol_version": "1",
        "status": "error",
        "error": {"code": "protocol_error", "message": error},
    }

    if isinstance(message, dict):
        request_id = message.get("id")
        if isinstance(request_id, str) and request_id:
            response["id"] = request_id

        session_id = message.get("session_id")
        if isinstance(session_id, str) and session_id:
            response["session_id"] = session_id

    return response
