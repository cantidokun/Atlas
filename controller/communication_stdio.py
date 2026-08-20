"""Dependency-free stdin/stdout transport for the controller communication gateway.

The transport remains deliberately unaware of Blender, Unreal, Ollama, or
another execution environment.  A host supplies the already-authorized local
tool executor and, optionally, a bounded model executor.
"""

from __future__ import annotations

import json
import sys
from typing import Callable, Dict, Iterable, TextIO

from controller.aider_model_client import AiderModelClient
from controller.communication_gateway import (
    CommunicationProtocolError,
    ControllerCommunicationGateway,
)
from controller.communication_runtime import (
    ControllerCommunicationRuntime,
    DEFAULT_MAX_MODEL_TURN_SECONDS,
    ModelTurnExecutor,
)


ToolExecutor = Callable[[str, Dict[str, object]], Dict[str, object]]


def process_lines(
    gateway: ControllerCommunicationGateway,
    lines: Iterable[str],
    output: TextIO,
) -> None:
    """Read JSON objects from lines and emit one JSON response per message.

    A malformed message never reaches the command handler.  When a usable
    request id can be recovered, the error response carries that id so the
    remote caller can correlate the failure without human intervention.

    Unexpected command-handler failures are isolated to the current request.
    The communication process must remain alive after a local executor or
    integration defect so an autonomous caller can receive a structured error
    and decide how to recover instead of losing the bridge entirely.
    """
    for line in lines:
        if not line.strip():
            continue

        message = None
        try:
            message = json.loads(line)
            response = gateway.handle_message(message)
        except (json.JSONDecodeError, CommunicationProtocolError) as exc:
            response = _error_response(message, "protocol_error", str(exc))
        except Exception as exc:  # pragma: no cover - exercised by integration tests
            response = _error_response(
                message,
                "internal_error",
                f"{type(exc).__name__}: {exc}",
            )

        output.write(json.dumps(response, sort_keys=True, separators=(",", ":")) + "\n")
        output.flush()


def run_stdio(
    handle_command: Callable[[str, str, Dict[str, object]], Dict[str, object]],
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
) -> None:
    """Run the gateway as a local process using newline-delimited JSON."""
    gateway = ControllerCommunicationGateway(handle_command)
    process_lines(gateway, stdin, stdout)


def run_controller_stdio(
    execute_tool: ToolExecutor,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    *,
    model_executor: ModelTurnExecutor | None = None,
    clock=None,
    max_model_turn_seconds: float = DEFAULT_MAX_MODEL_TURN_SECONDS,
) -> None:
    """Run the controller communication runtime over newline-delimited JSON.

    This is the transport-neutral local composition point: the transport owns
    only message framing, the gateway owns protocol/session semantics, and the
    controller runtime owns task state and model-turn supervision.  The caller
    supplies the concrete local executor and may optionally supply a bounded
    model executor.  The host-level model-turn limit prevents a remote caller
    from requesting an unbounded model process lifetime.
    """
    runtime = ControllerCommunicationRuntime(
        execute_tool,
        model_executor=model_executor,
        clock=clock,
        max_model_turn_seconds=max_model_turn_seconds,
    )
    gateway = ControllerCommunicationGateway(runtime.handle_command)
    process_lines(gateway, stdin, stdout)


def run_aider_controller_stdio(
    execute_tool: ToolExecutor,
    working_directory: str,
    *,
    executable: str = "aider",
    extra_args=(),
    environment=None,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    clock=None,
    max_model_turn_seconds: float = DEFAULT_MAX_MODEL_TURN_SECONDS,
) -> None:
    """Run the controller gateway with Aider as its bounded model executor.

    This is the first provider-specific host composition.  Aider remains a
    local model-process adapter; protocol, controller authorization, session
    state, and timeout/recovery semantics remain in the generic layers.
    """
    aider = AiderModelClient(
        executable=executable,
        working_directory=working_directory,
        extra_args=extra_args,
        environment=environment,
    )
    run_controller_stdio(
        execute_tool,
        stdin,
        stdout,
        model_executor=aider.run_turn,
        clock=clock,
        max_model_turn_seconds=max_model_turn_seconds,
    )


def _error_response(message: object, code: str, error: str) -> Dict[str, object]:
    response: Dict[str, object] = {
        "protocol_version": "1",
        "status": "error",
        "error": {"code": code, "message": error},
    }

    if isinstance(message, dict):
        request_id = message.get("id")
        if isinstance(request_id, str) and request_id:
            response["id"] = request_id

        session_id = message.get("session_id")
        if isinstance(session_id, str) and session_id:
            response["session_id"] = session_id

    return response
