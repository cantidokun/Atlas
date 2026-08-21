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
    
    Protocol:
    - Messages are prefixed with 4-byte little-endian length
    - Request/response payloads are UTF-8 encoded JSON
    - Maximum request size: 1MB
    - Maximum response size: 10MB
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
        try:
            json_request = serialize_request(request)
        except Exception as e:
            raise NamedPipeTransportError(f"Failed to serialize request: {e}")
        
        # Validate request size
        request_bytes = json_request.encode('utf-8')
        if len(request_bytes) > 1024 * 1024:  # 1MB limit
            raise NamedPipeTransportError("Request too large (exceeds 1MB limit)")
        
        # Connect to pipe and send/receive
        pipe_handle = None
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
            
            # Set pipe mode
            win32pipe.SetNamedPipeHandleState(
                pipe_handle,
                win32pipe.PIPE_READMODE_MESSAGE,
                None,
                None
            )
            
            # Write request with length prefix
            request_length = len(request_bytes)
            length_bytes = request_length.to_bytes(4, byteorder='little')
            win32file.WriteFile(pipe_handle, length_bytes + request_bytes)
            win32file.FlushFileBuffers(pipe_handle)
            
            # Read response length first
            result, length_data = win32file.ReadFile(pipe_handle, 4)
            if result != 0:
                raise NamedPipeTransportError(f"Failed to read response length: {result}")
            
            response_length = int.from_bytes(length_data, byteorder='little')
            if response_length > 10 * 1024 * 1024:  # 10MB limit
                raise NamedPipeTransportError("Response too large (exceeds 10MB limit)")
            
            # Read response data
            result, response_data = win32file.ReadFile(pipe_handle, response_length)
            if result != 0:
                raise NamedPipeTransportError(f"Failed to read response data: {result}")
            
            json_response = response_data.decode('utf-8')
                
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
            elif error_code == 121:  # ERROR_SEM_TIMEOUT
                raise NamedPipeTransportError(
                    "Timeout waiting for Unreal transport server"
                )
            else:
                raise NamedPipeTransportError(
                    f"Named pipe error {error_code}: {error_desc}"
                )
        except UnicodeDecodeError as e:
            raise NamedPipeTransportError(f"Invalid UTF-8 in response: {e}")
        finally:
            if pipe_handle is not None:
                try:
                    win32file.CloseHandle(pipe_handle)
                except:
                    pass  # Best effort cleanup
        
        # Deserialize response
        try:
            response = deserialize_response(json_response)
        except TransportDeserializationError as e:
            raise NamedPipeTransportError(f"Failed to deserialize response: {e}")
        
        return response


def create_named_pipe_transport(pipe_name: Optional[str] = None) -> WindowsNamedPipeTransport:
    """Create a Windows named pipe transport instance.
    
    Args:
        pipe_name: Custom pipe name, defaults to standard Atlas pipe
        
    Returns:
        Configured transport instance
        
    Raises:
        NamedPipeTransportError: If Windows named pipe support unavailable
    """
    return WindowsNamedPipeTransport(pipe_name)


def is_transport_available() -> bool:
    """Check if Windows named pipe transport is available on this system."""
    return WINDOWS_AVAILABLE
