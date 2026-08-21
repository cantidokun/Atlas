"""Windows Named Pipe transport implementation for Atlas ↔ Unreal communication.

This module provides the production transport layer using Windows named pipes
for IPC between the Python Atlas system and the Unreal Editor.
"""

import json
import time
from typing import Optional

try:
    import win32file
    import win32pipe
    import win32event
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


class WindowsNamedPipeTransport:
    """Windows Named Pipe transport for Atlas ↔ Unreal communication.
    
    This transport connects to the Unreal Editor's named pipe server to
    send requests and receive responses.
    """
    
    PIPE_NAME = r"\\.\pipe\AtlasUnrealTransport"
    CONNECT_TIMEOUT_MS = 5000
    READ_TIMEOUT_MS = 30000
    
    def __init__(self, pipe_name: Optional[str] = None):
        if not WINDOWS_AVAILABLE:
            raise NamedPipeTransportError(
                "Windows named pipe transport requires pywin32 package"
            )
        
        self.pipe_name = pipe_name or self.PIPE_NAME
    
    def send(self, request: UnrealTransportRequest) -> UnrealTransportResponse:
        """Send a request to Unreal and return the response."""
        if not isinstance(request, UnrealTransportRequest):
            raise TypeError("request must be UnrealTransportRequest")
        
        # Serialize request
        json_request = serialize_request(request)
        
        # Connect to pipe and send/receive
        try:
            # Wait for pipe to become available
            win32pipe.WaitNamedPipe(self.pipe_name, self.CONNECT_TIMEOUT_MS)
            
            # Open pipe
            pipe_handle = win32file.CreateFile(
                self.pipe_name,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,  # No sharing
                None,  # Default security
                win32file.OPEN_EXISTING,
                0,  # Default attributes
                None  # No template
            )
            
            try:
                # Set pipe mode
                win32pipe.SetNamedPipeHandleState(
                    pipe_handle,
                    win32pipe.PIPE_READMODE_MESSAGE,
                    None,
                    None
                )
                
                # Write request
                win32file.WriteFile(pipe_handle, json_request.encode('utf-8'))
                win32file.FlushFileBuffers(pipe_handle)
                
                # Read response with timeout using overlapped I/O
                overlapped = pywintypes.OVERLAPPED()
                overlapped.hEvent = win32event.CreateEvent(None, True, False, None)
                buffer = win32file.AllocateReadBuffer(1024 * 1024)  # 1MB max
                
                try:
                    result, _ = win32file.ReadFile(pipe_handle, buffer, overlapped)
                    
                    # Handle immediate completion or ERROR_IO_PENDING
                    if result == 0:
                        # Operation completed immediately
                        nbytes = win32file.GetOverlappedResult(pipe_handle, overlapped, True)
                    else:
                        # Wait for completion with timeout
                        wait_result = win32event.WaitForSingleObject(overlapped.hEvent, self.READ_TIMEOUT_MS)
                        
                        if wait_result == win32event.WAIT_TIMEOUT:
                            # Cancel the operation and wait for it to complete
                            win32file.CancelIo(pipe_handle)
                            # Still need to get the final result to clean up properly
                            try:
                                win32file.GetOverlappedResult(pipe_handle, overlapped, True)
                            except pywintypes.error:
                                pass  # Expected after cancellation
                            raise NamedPipeTransportError(f"Read operation timed out after {self.READ_TIMEOUT_MS}ms")
                        elif wait_result != win32event.WAIT_OBJECT_0:
                            raise NamedPipeTransportError(f"Wait failed with result: {wait_result}")
                        
                        # Get the number of bytes read
                        nbytes = win32file.GetOverlappedResult(pipe_handle, overlapped, True)
                    
                    if nbytes == 0:
                        raise NamedPipeTransportError("No data read from pipe")
                    
                    # Extract the actual response data from the buffer
                    response_data = buffer[:nbytes]
                        
                finally:
                    win32file.CloseHandle(overlapped.hEvent)
                
                json_response = response_data.decode('utf-8')
                
            finally:
                win32file.CloseHandle(pipe_handle)
                
        except pywintypes.error as e:
            error_code, error_name, error_desc = e.args
            if error_code == 2:  # ERROR_FILE_NOT_FOUND
                raise NamedPipeTransportError(
                    "Unreal transport server not available (pipe not found)"
                )
            elif error_code == 231:  # ERROR_PIPE_BUSY
                raise NamedPipeTransportError(
                    "Unreal transport server busy (pipe in use)"
                )
            else:
                raise NamedPipeTransportError(
                    f"Named pipe error {error_code}: {error_desc}"
                )
        
        # Deserialize response
        try:
            response = deserialize_response(json_response)
        except TransportDeserializationError as e:
            raise NamedPipeTransportError(f"Failed to deserialize response: {e}")
        
        return response


def create_named_pipe_transport(pipe_name: Optional[str] = None) -> WindowsNamedPipeTransport:
    """Create a Windows named pipe transport instance."""
    return WindowsNamedPipeTransport(pipe_name)
