"""Integration tests for the Atlas ↔ Unreal production transport.

These tests verify the complete transport pipeline including:
- Named pipe connectivity
- Request/response serialization
- Unreal Editor integration
- Actor inspection functionality
- Authorized Actor mutation with post-write evidence
"""

import pytest
from unittest.mock import Mock, patch

from planning.unreal_transport_contract import UnrealTransportRequest, UnrealTransportResponse
from planning.unreal_agent import UnrealOperation, UnrealCapability, UnrealOperationKind

# Import production components
try:
    from planning.unreal_transport_named_pipe import (
        WindowsNamedPipeTransport,
        NamedPipeTransportError,
        NamedPipeTransportTimeoutError,
        NamedPipeTransportDisconnectedError,
        _translate_pipe_error,
        create_named_pipe_transport,
    )
    TRANSPORT_AVAILABLE = True
except ImportError:
    TRANSPORT_AVAILABLE = False


@pytest.mark.skipif(not TRANSPORT_AVAILABLE, reason="Named pipe transport not available")
class TestNamedPipeTransport:
    """Test the Windows named pipe transport implementation."""

    def test_transport_creation(self):
        """Test that transport can be created."""
        transport = create_named_pipe_transport()
        assert isinstance(transport, WindowsNamedPipeTransport)
        assert transport.pipe_name == r"\\.\pipe\AtlasUnrealTransport"
        assert transport.connect_timeout_ms == 5000
        assert transport.write_timeout_ms == 30000
        assert transport.read_timeout_ms == 30000

    def test_transport_creation_custom_pipe(self):
        """Test transport creation with custom pipe name."""
        custom_pipe = r"\\.\pipe\TestPipe"
        transport = create_named_pipe_transport(custom_pipe)
        assert transport.pipe_name == custom_pipe

    @pytest.mark.parametrize("timeout_name", [
        "connect_timeout_ms",
        "write_timeout_ms",
        "read_timeout_ms",
    ])
    def test_transport_rejects_non_positive_timeouts(self, timeout_name):
        with pytest.raises(ValueError, match="positive integer"):
            create_named_pipe_transport(**{timeout_name: 0})

    def test_send_requires_transport_request(self):
        """Test that send() validates input type."""
        transport = create_named_pipe_transport()

        with pytest.raises(TypeError, match="UnrealTransportRequest"):
            transport.send({"not": "a request"})

    def test_send_unavailable_server(self):
        """Test behavior when a known-unused pipe has no Unreal server."""
        # Do not use the production pipe here: when Unreal Editor is running,
        # the production server is intentionally available. A dedicated test
        # pipe keeps this negative test deterministic in both local and CI
        # environments without requiring the Editor to be stopped.
        transport = create_named_pipe_transport(r"\\.\pipe\AtlasUnrealTransport_TestUnavailable")

        request = UnrealTransportRequest(
            request_id="test-001",
            operation_name="inspect_target_actors",
            capability="inspect_actor",
            kind="read",
            arguments={"entity_ids": ("FIELD_SURFACE",)},
            entity_ids=("FIELD_SURFACE",),
            authorization_id="auth-test-123",
        )

        with pytest.raises(NamedPipeTransportError, match="not available"):
            transport.send(request)

    def test_send_write_timeout_cancels_inflight_write(self):
        """A stalled overlapped write must be bounded and explicitly cancelled."""
        transport = create_named_pipe_transport(write_timeout_ms=17)
        request = UnrealTransportRequest(
            request_id="write-timeout-001",
            operation_name="set_actor_location",
            capability="modify_actor",
            kind="write",
            arguments={
                "entity_ids": ("FIELD_SURFACE",),
                "location": {"x": 1.0, "y": 2.0, "z": 3.0},
            },
            entity_ids=("FIELD_SURFACE",),
            authorization_id="auth-write-timeout",
        )

        with patch("planning.unreal_transport_named_pipe.win32pipe.WaitNamedPipe"), \
             patch("planning.unreal_transport_named_pipe.win32file.CreateFile", return_value=Mock()), \
             patch("planning.unreal_transport_named_pipe.win32pipe.SetNamedPipeHandleState"), \
             patch("planning.unreal_transport_named_pipe.win32file.WriteFile", return_value=(
                 __import__("planning.unreal_transport_named_pipe", fromlist=["winerror"]).winerror.ERROR_IO_PENDING,
                 0,
             )), \
             patch("planning.unreal_transport_named_pipe.win32event.WaitForSingleObject", return_value=
                 __import__("planning.unreal_transport_named_pipe", fromlist=["win32event"]).win32event.WAIT_TIMEOUT), \
             patch("planning.unreal_transport_named_pipe.win32file.CancelIo") as cancel_io, \
             patch("planning.unreal_transport_named_pipe.win32file.GetOverlappedResult", return_value=0), \
             patch("planning.unreal_transport_named_pipe.win32file.CloseHandle"):
            with pytest.raises(NamedPipeTransportTimeoutError, match="Write operation timed out after 17ms"):
                transport.send(request)

        cancel_io.assert_called_once()


@pytest.mark.skipif(not TRANSPORT_AVAILABLE, reason="Named pipe transport not available")
class TestNamedPipeErrorTranslation:
    """Test stable classification of Windows named-pipe failures."""

    @staticmethod
    def _win32_error(code):
        error = Mock()
        error.args = (code, "mock_error", "mock description")
        return error

    def test_missing_pipe_remains_connection_error(self):
        error = _translate_pipe_error(self._win32_error(2))
        assert type(error) is NamedPipeTransportError
        assert "not available" in str(error)

    def test_wait_named_pipe_timeout_is_classified_as_timeout(self):
        error = _translate_pipe_error(self._win32_error(121))
        assert isinstance(error, NamedPipeTransportTimeoutError)
        assert "Timed out waiting" in str(error)

    def test_busy_pipe_remains_connection_error(self):
        error = _translate_pipe_error(self._win32_error(231))
        assert type(error) is NamedPipeTransportError
        assert "busy" in str(error)

    @pytest.mark.parametrize("error_code", [109, 232, 233])
    def test_server_disconnect_codes_are_distinguished(self, error_code):
        error = _translate_pipe_error(self._win32_error(error_code))
        assert isinstance(error, NamedPipeTransportDisconnectedError)
        assert "disconnected" in str(error)

    def test_timeout_error_is_distinct_transport_failure(self):
        error = NamedPipeTransportTimeoutError("Read operation timed out after 30ms")
        assert isinstance(error, NamedPipeTransportError)
        assert "timed out" in str(error)
