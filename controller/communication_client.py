"""Programmatic client for the Atlas controller stdio protocol.

This module is the caller-side counterpart to ``communication_stdio``.  It is
intentionally small: it owns process framing, request IDs, and response
correlation while the controller gateway remains authoritative for protocol
validation, sessions, authorization, and task state.

The client can drive the local communication host without a human copying
messages between processes.  It does not expose arbitrary tool execution; it
only sends controller protocol commands to the already-configured host.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any, Callable, Dict, Mapping, Sequence

from controller.communication_gateway import PROTOCOL_VERSION


ProcessFactory = Callable[..., subprocess.Popen]


class ControllerCommunicationError(RuntimeError):
    """Raised when the controller process cannot complete a protocol request."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        retryable: bool | None = None,
        response: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.response = None if response is None else dict(response)


class ControllerStdioClient:
    """Drive one long-lived controller communication process over stdio."""

    def __init__(
        self,
        process: subprocess.Popen,
        *,
        request_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if process.stdin is None or process.stdout is None:
            raise ValueError("controller process must expose stdin and stdout")
        self._process = process
        self._request_id_factory = request_id_factory or self._default_request_id
        self._request_counter = 0
        self._closed = False
        self._session_id: str | None = None

    @classmethod
    def launch(
        cls,
        command: Sequence[str],
        *,
        cwd: str | None = None,
        environment: Mapping[str, str] | None = None,
        process_factory: ProcessFactory = subprocess.Popen,
    ) -> "ControllerStdioClient":
        """Launch an already-configured local communication host.

        The command is passed as an argv sequence with ``shell=False``.  The
        host executable, working directory, and local executor configuration
        therefore remain local policy rather than remotely supplied data.
        """
        if not command:
            raise ValueError("command must not be empty")

        process = process_factory(
            list(command),
            cwd=cwd,
            env=None if environment is None else dict(environment),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            shell=False,
            bufsize=1,
        )
        return cls(process)

    def open_session(self, session_id: str | None = None) -> Dict[str, Any]:
        """Open a controller session and retain its negotiated session id."""
        payload: Dict[str, Any] = {}
        if session_id is not None:
            payload["session_id"] = session_id
        response = self._request("open", payload)
        self._session_id = response.get("session_id")
        if not isinstance(self._session_id, str) or not self._session_id:
            raise ControllerCommunicationError("controller did not return a session_id")
        return response

    def command(self, command: str, arguments: Mapping[str, Any] | None = None) -> Dict[str, Any]:
        """Send one controller-owned command and return its response payload."""
        if not isinstance(command, str) or not command:
            raise ValueError("command must be a non-empty string")
        if self._session_id is None:
            raise ControllerCommunicationError("open_session must be called first")
        if self._closed:
            raise ControllerCommunicationError("controller client is closed")

        response = self._request(
            "command",
            {
                "command": command,
                "arguments": dict(arguments or {}),
            },
            session_id=self._session_id,
        )
        return response["payload"]

    def close(self) -> Dict[str, Any]:
        """Close the active controller session."""
        if self._closed:
            return {"status": "closed"}
        if self._session_id is None:
            self._closed = True
            self._terminate_process()
            return {"status": "closed"}

        try:
            response = self._request(
                "close",
                {},
                session_id=self._session_id,
            )
        finally:
            self._closed = True
            self._terminate_process()
        return response.get("payload", response)

    def terminate(self) -> None:
        """Stop the local communication host without sending a protocol close."""
        if self._closed:
            return
        self._closed = True
        self._terminate_process()

    def _request(
        self,
        message_type: str,
        payload: Mapping[str, Any],
        *,
        session_id: str | None = None,
    ) -> Dict[str, Any]:
        request_id = self._request_id_factory()
        message: Dict[str, Any] = {
            "protocol_version": PROTOCOL_VERSION,
            "type": message_type,
            "id": request_id,
            "payload": dict(payload),
        }
        if session_id is not None:
            message["session_id"] = session_id

        line = json.dumps(message, sort_keys=True, separators=(",", ":"))
        try:
            self._process.stdin.write(line + "\n")
            self._process.stdin.flush()
            response_line = self._process.stdout.readline()
        except (BrokenPipeError, OSError) as exc:
            raise ControllerCommunicationError("controller process is unavailable") from exc

        if not response_line:
            returncode = self._process.poll()
            raise ControllerCommunicationError(
                f"controller process closed its output (returncode={returncode})"
            )

        try:
            response = json.loads(response_line)
        except json.JSONDecodeError as exc:
            raise ControllerCommunicationError("controller returned invalid JSON") from exc

        if not isinstance(response, dict):
            raise ControllerCommunicationError("controller response must be an object")
        if response.get("protocol_version") != PROTOCOL_VERSION:
            raise ControllerCommunicationError("controller response used an unsupported protocol version")
        if response.get("id") != request_id:
            raise ControllerCommunicationError("controller response id did not match request")
        if session_id is not None and response.get("session_id") != session_id:
            raise ControllerCommunicationError("controller response session_id did not match request")

        if response.get("status") == "error":
            error = response.get("error")
            if error is None:
                payload_error = response.get("payload", {}).get("error")
                error = payload_error
            if isinstance(error, Mapping):
                code = error.get("code")
                message = error.get("message") or "controller request failed"
                retryable = error.get("retryable")
                raise ControllerCommunicationError(
                    str(message),
                    code=code if isinstance(code, str) else None,
                    retryable=retryable if isinstance(retryable, bool) else None,
                    response=response,
                )
            raise ControllerCommunicationError(
                str(error or "controller request failed"),
                response=response,
            )
        if response.get("status") != "ok":
            raise ControllerCommunicationError("controller returned an unexpected status")
        return response

    def _terminate_process(self) -> None:
        if self._process.poll() is not None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()

    def _default_request_id(self) -> str:
        self._request_counter += 1
        return f"client-{self._request_counter}"
