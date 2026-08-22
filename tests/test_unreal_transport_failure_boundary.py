"""Focused regression coverage for Named Pipe failure classification and adapter propagation."""

from unittest.mock import Mock, patch

import pywintypes
import pytest

from planning.unreal_adapter_production import UnrealAdapterError, UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_transport_contract import UnrealTransportRequest
from planning.unreal_transport_named_pipe import (
    NamedPipeTransportDisconnectedError,
    NamedPipeTransportError,
    NamedPipeTransportTimeoutError,
    WindowsNamedPipeTransport,
    _translate_pipe_error,
)


class TestPipeErrorTranslation:
    @staticmethod
    def _win32_error(code):
        error = Mock()
        error.args = (code, "mock_error", "mock description")
        return error

    def test_wait_timeout_is_classified_as_timeout(self):
        error = _translate_pipe_error(self._win32_error(121))
        assert isinstance(error, NamedPipeTransportTimeoutError)
        assert "Timed out waiting" in str(error)

    @pytest.mark.parametrize("error_code", [109, 232, 233])
    def test_disconnect_codes_are_classified_as_disconnect(self, error_code):
        error = _translate_pipe_error(self._win32_error(error_code))
        assert isinstance(error, NamedPipeTransportDisconnectedError)


class TestAdapterFailurePropagation:
    def test_transport_timeout_is_preserved_as_adapter_cause(self):
        timeout = NamedPipeTransportTimeoutError("read timed out")
        transport = Mock()
        transport.send.side_effect = timeout
        adapter = UnrealAdapterProduction(transport)
        operation = UnrealOperation(
            name="inspect_target_actors",
            capability=UnrealCapability.INSPECT_ACTOR,
            kind=UnrealOperationKind.READ,
            arguments={"entity_ids": ("FIELD_SURFACE",)},
            entity_ids=("FIELD_SURFACE",),
        )

        with pytest.raises(UnrealAdapterError) as exc_info:
            adapter.inspect(operation, "auth-timeout")

        assert "inspect_target_actors" in str(exc_info.value)
        assert exc_info.value.__cause__ is timeout

    def test_transport_disconnect_is_preserved_as_adapter_cause(self):
        disconnect = NamedPipeTransportDisconnectedError("server disconnected")
        transport = Mock()
        transport.send.side_effect = disconnect
        adapter = UnrealAdapterProduction(transport)
        operation = UnrealOperation(
            name="inspect_target_actors",
            capability=UnrealCapability.INSPECT_ACTOR,
            kind=UnrealOperationKind.READ,
            arguments={"entity_ids": ("FIELD_SURFACE",)},
            entity_ids=("FIELD_SURFACE",),
        )

        with pytest.raises(UnrealAdapterError) as exc_info:
            adapter.inspect(operation, "auth-disconnect")

        assert "inspect_target_actors" in str(exc_info.value)
        assert exc_info.value.__cause__ is disconnect


class TestWaitNamedPipeBoundary:
    def test_real_wait_named_pipe_timeout_is_translated_before_create_file(self):
        transport = WindowsNamedPipeTransport.__new__(WindowsNamedPipeTransport)
        transport.pipe_name = r"\\.\pipe\AtlasUnrealTransport"

        error = pywintypes.error(121, "WaitNamedPipe", "timed out")

        with patch("planning.unreal_transport_named_pipe.win32pipe.WaitNamedPipe", side_effect=error) as wait:
            with pytest.raises(NamedPipeTransportTimeoutError):
                transport.send(
                    UnrealTransportRequest(
                        request_id="timeout-001",
                        operation_name="inspect_target_actors",
                        capability="inspect_actor",
                        kind="read",
                        arguments={"entity_ids": ("FIELD_SURFACE",)},
                        entity_ids=("FIELD_SURFACE",),
                        authorization_id="auth-timeout",
                    )
                )

        wait.assert_called_once()
