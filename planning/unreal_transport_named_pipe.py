"""Windows Named Pipe transport implementation for Atlas ↔ Unreal communication.

This module provides the production transport layer using Windows named pipes
for IPC between the Python Atlas system and the Unreal Editor.
"""

import json
from typing import Optional

try:
    import win32file
    import win32pipe
    import win32event
    import winerror
    import pywintypes
    WINDOWS_AVAILABLE = True
except ImportError:
    WINDOWS_AVAILABLE = False

from planning.unreal_transport_contract import (
    UnrealTransportRequest,
    UnrealTransportResponse,
)
from planning.unreal_transport_serialization import (
    serialize_request,
    deserialize_response,
    TransportDeserializationError,
)


class NamedPipeTransportError(RuntimeError):
    """Raised when the named pipe transport encounters an error."""


class NamedPipeTransportTimeoutError(NamedPipeTransportError):
    """Raised when a named-pipe operation exceeds its configured timeout."""


class NamedPipeTransportDisconnectedError(NamedPipeTransportError):
    """Raised when the Unreal named-pipe server disconnects mid-request."""


def _translate_pipe_error(error: "pywintypes.error") -> NamedPipeTransportError:
    """Translate a Windows pipe error into a stable Atlas transport error."""
    error_code, _error_name, error_desc = error.args

    if error_code == 2:
        return NamedPipeTransportError(
            "Unreal transport server not available (pipe not found)"
        )
    if error_code == 121:
        return NamedPipeTransportTimeoutError(
            "Timed out waiting for Unreal transport server"
        )
    if error_code == 231:
        return NamedPipeTransportError(
            "Unreal transport server busy (pipe in use)"
        )
    if error_code in (109, 232, 233):
        return NamedPipeTransportDisconnectedError(
            "Unreal transport server disconnected while processing the request"
        )

    return NamedPipeTransportError(
        f"Named pipe error {error_code}: {error_desc}"
    )


class WindowsNamedPipeTransport:
    """Windows Named Pipe transport for Atlas ↔ Unreal communication.

    Connection, write, and read phases are bounded so a stalled Unreal peer
    cannot leave the Atlas caller blocked indefinitely.
    """

    PIPE_NAME = r"\\.\pipe\AtlasUnrealTransport"
    CONNECT_TIMEOUT_MS = 5000
    WRITE_TIMEOUT_MS = 30000
    READ_TIMEOUT_MS = 30000

    def __init__(
        self,
        pipe_name: Optional[str] = None,
        *,
        connect_timeout_ms: Optional[int] = None,
        write_timeout_ms: Optional[int] = None,
        read_timeout_ms: Optional[int] = None,
    ):
        if not WINDOWS_AVAILABLE:
            raise NamedPipeTransportError(
                "Windows named pipe transport requires pywin32 package"
            )

        self.pipe_name = pipe_name or self.PIPE_NAME
        self._connect_timeout_ms = self._validate_timeout(
            "connect_timeout_ms", connect_timeout_ms
        )
        self._write_timeout_ms = self._validate_timeout(
            "write_timeout_ms", write_timeout_ms
        )
        self._read_timeout_ms = self._validate_timeout(
            "read_timeout_ms", read_timeout_ms
        )

    @staticmethod
    def _validate_timeout(name: str, value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"{name} must be a positive integer number of milliseconds"
            )
        return value

    @property
    def connect_timeout_ms(self) -> int:
        return self.CONNECT_TIMEOUT_MS if self._connect_timeout_ms is None else self._connect_timeout_ms

    @property
    def write_timeout_ms(self) -> int:
        return self.WRITE_TIMEOUT_MS if self._write_timeout_ms is None else self._write_timeout_ms

    @property
    def read_timeout_ms(self) -> int:
        return self.READ_TIMEOUT_MS if self._read_timeout_ms is None else self._read_timeout_ms

    def send(self, request: UnrealTransportRequest) -> UnrealTransportResponse:
        """Send a request to Unreal and return the response."""
        if not isinstance(request, UnrealTransportRequest):
            raise TypeError("request must be UnrealTransportRequest")

        json_request = serialize_request(request)
        request_data = json_request.encode("utf-8")

        # Tests and failure-boundary probes may intentionally construct an
        # instance with __new__ to exercise error translation before normal
        # initialization. Fall back to class defaults in that case.
        connect_timeout_ms = getattr(
            self, "connect_timeout_ms", self.CONNECT_TIMEOUT_MS
        )
        write_timeout_ms = getattr(
            self, "write_timeout_ms", self.WRITE_TIMEOUT_MS
        )
        read_timeout_ms = getattr(
            self, "read_timeout_ms", self.READ_TIMEOUT_MS
        )

        try:
            win32pipe.WaitNamedPipe(self.pipe_name, connect_timeout_ms)

            pipe_handle = win32file.CreateFile(
                self.pipe_name,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                win32file.FILE_FLAG_OVERLAPPED,
                None,
            )

            try:
                win32pipe.SetNamedPipeHandleState(
                    pipe_handle,
                    win32pipe.PIPE_READMODE_MESSAGE,
                    None,
                    None,
                )

                write_overlapped = pywintypes.OVERLAPPED()
                write_overlapped.hEvent = win32event.CreateEvent(
                    None, True, False, None
                )
                try:
                    write_result, _ = win32file.WriteFile(
                        pipe_handle, request_data, write_overlapped
                    )
                    if write_result == winerror.ERROR_IO_PENDING:
                        wait_result = win32event.WaitForSingleObject(
                            write_overlapped.hEvent, write_timeout_ms
                        )
                        if wait_result == win32event.WAIT_TIMEOUT:
                            win32file.CancelIo(pipe_handle)
                            try:
                                win32file.GetOverlappedResult(
                                    pipe_handle, write_overlapped, True
                                )
                            except pywintypes.error as cancel_error:
                                if cancel_error.winerror != winerror.ERROR_OPERATION_ABORTED:
                                    raise
                            raise NamedPipeTransportTimeoutError(
                                f"Write operation timed out after {write_timeout_ms}ms"
                            )
                        if wait_result != win32event.WAIT_OBJECT_0:
                            raise NamedPipeTransportError(
                                f"Write wait failed with result: {wait_result}"
                            )
                        win32file.GetOverlappedResult(
                            pipe_handle, write_overlapped, True
                        )
                    elif write_result != 0:
                        raise NamedPipeTransportError(
                            f"WriteFile failed with result: {write_result}"
                        )
                    else:
                        win32file.GetOverlappedResult(
                            pipe_handle, write_overlapped, True
                        )
                finally:
                    win32file.CloseHandle(write_overlapped.hEvent)

                win32file.FlushFileBuffers(pipe_handle)

                overlapped = pywintypes.OVERLAPPED()
                overlapped.hEvent = win32event.CreateEvent(None, True, False, None)
                buffer = win32file.AllocateReadBuffer(1024 * 1024)

                try:
                    result, _ = win32file.ReadFile(pipe_handle, buffer, overlapped)

                    if result == winerror.ERROR_IO_PENDING:
                        wait_result = win32event.WaitForSingleObject(
                            overlapped.hEvent, read_timeout_ms
                        )

                        if wait_result == win32event.WAIT_TIMEOUT:
                            win32file.CancelIo(pipe_handle)
                            try:
                                win32file.GetOverlappedResult(
                                    pipe_handle, overlapped, True
                                )
                            except pywintypes.error as cancel_error:
                                if cancel_error.winerror != winerror.ERROR_OPERATION_ABORTED:
                                    raise
                            raise NamedPipeTransportTimeoutError(
                                f"Read operation timed out after {read_timeout_ms}ms"
                            )
                        if wait_result != win32event.WAIT_OBJECT_0:
                            raise NamedPipeTransportError(
                                f"Wait failed with result: {wait_result}"
                            )

                        nbytes = win32file.GetOverlappedResult(
                            pipe_handle, overlapped, True
                        )
                    elif result == 0:
                        nbytes = win32file.GetOverlappedResult(
                            pipe_handle, overlapped, True
                        )
                    else:
                        raise NamedPipeTransportError(
                            f"ReadFile failed with result: {result}"
                        )

                    if nbytes == 0:
                        raise NamedPipeTransportDisconnectedError(
                            "Unreal transport server disconnected without returning data"
                        )

                    response_data = bytes(buffer[:nbytes])
                finally:
                    win32file.CloseHandle(overlapped.hEvent)

                json_response = response_data.decode("utf-8")
            finally:
                win32file.CloseHandle(pipe_handle)

        except pywintypes.error as e:
            raise _translate_pipe_error(e) from e

        try:
            response = deserialize_response(json_response)
        except TransportDeserializationError as e:
            raise NamedPipeTransportError(f"Failed to deserialize response: {e}") from e

        return response


def create_named_pipe_transport(
    pipe_name: Optional[str] = None,
    *,
    connect_timeout_ms: Optional[int] = None,
    write_timeout_ms: Optional[int] = None,
    read_timeout_ms: Optional[int] = None,
) -> WindowsNamedPipeTransport:
    """Create a Windows named pipe transport instance."""
    return WindowsNamedPipeTransport(
        pipe_name,
        connect_timeout_ms=connect_timeout_ms,
        write_timeout_ms=write_timeout_ms,
        read_timeout_ms=read_timeout_ms,
    )
