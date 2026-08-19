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
                
                # Read response
                result, response_data = win32file.ReadFile(pipe_handle, 1024 * 1024)  # 1MB max
                
                if result != 0:
                    raise NamedPipeTransportError(f"ReadFile failed with result: {result}")
                
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
