"""Machine-facing JSON-lines transport for the Atlas controller bridge.

This module is intentionally limited to transport concerns.  It reads one JSON
message per line, hands it to ``ControllerBridge``, and writes one JSON
response per line.  The host supplies the tool executor, so this layer does
not know about Blender, Unreal, sockets, HTTP, or any model provider.

Keeping stdin/stdout as the first concrete transport gives the local machine a
small, dependency-free communication boundary that can later be wrapped by a
socket, process manager, or model adapter without changing controller logic.
"""

import sys
from typing import Any, Callable, Dict, Iterable, TextIO

from controller_bridge import ControllerBridge, encode_response, handle_json_line
from controller_session import ProtocolError


ToolExecutor = Callable[[str, Dict[str, Any]], Dict[str, Any]]


def process_lines(
    bridge: ControllerBridge,
    lines: Iterable[str],
    output: TextIO,
) -> None:
    """Process JSON-lines input and write exactly one response per input line.

    Protocol errors are converted into JSON error responses when a request id
    can be recovered.  Malformed input without a usable id is reported as a
    transport-level error and does not invoke the controller executor.
    """
    import json

    for line in lines:
        if not line.strip():
            continue

        try:
            response = handle_json_line(bridge, line)
        except ProtocolError as exc:
            request_id = None
            try:
                candidate = json.loads(line)
                if isinstance(candidate, dict) and isinstance(candidate.get("id"), str):
                    request_id = candidate["id"]
            except json.JSONDecodeError:
                pass

            response = {
                "protocol_version": "1",
                "status": "error",
                "error": {"code": "protocol_error", "message": str(exc)},
            }
            if request_id is not None:
                response["id"] = request_id
                response["session_id"] = bridge.session.session_id

        output.write(encode_response(response) + "\n")
        output.flush()


def run_stdio(execute: ToolExecutor, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> None:
    """Run the controller bridge over stdin/stdout JSON-lines transport."""
    bridge = ControllerBridge(execute)
    process_lines(bridge, stdin, stdout)
