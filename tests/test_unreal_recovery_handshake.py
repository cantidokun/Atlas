"""Tests for Unreal capability handshake and recovery contract compatibility."""

import pytest

from planning.unreal_adapter_production import (
    REQUIRED_RECOVERY_CAPABILITIES,
    UnrealAdapterError,
    UnrealAdapterProduction,
)
from planning.unreal_transport_contract import (
    UnrealTransportRequest,
    UnrealTransportResponse,
)


class MockTransport:
    def __init__(self, handler=None):
        self.handler = handler or self.default_handler
        self.sent_requests = []

    def default_handler(self, request: UnrealTransportRequest) -> UnrealTransportResponse:
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=True,
            observed_state={
                "capabilities": list(REQUIRED_RECOVERY_CAPABILITIES),
            },
            error="",
            source="unreal-editor-5.6",
            schema_version=1,
            error_code="",
            session_identity={
                "editor_session_id": "sess-test-001",
                "process_id": 9999,
                "process_creation_time_utc": "2026-09-05T20:00:00Z",
                "server_start_time_utc": "2026-09-05T20:00:01Z",
                "engine_version": "5.6",
                "project_identity": "AtlasUnrealHarness",
            },
        )

    def send(self, request: UnrealTransportRequest) -> UnrealTransportResponse:
        self.sent_requests.append(request)
        return self.handler(request)


class TestUnrealRecoveryHandshake:
    def test_query_capabilities_success(self):
        transport = MockTransport()
        adapter = UnrealAdapterProduction(transport)
        caps = adapter.query_capabilities(authorization_id="auth-test-01")
        assert caps == REQUIRED_RECOVERY_CAPABILITIES
        assert len(transport.sent_requests) == 1
        req = transport.sent_requests[0]
        assert req.operation_name == "get_capabilities"
        assert req.schema_version == 1

    def test_assert_recovery_capable_success(self):
        transport = MockTransport()
        adapter = UnrealAdapterProduction(transport)
        # Should not raise
        adapter.assert_recovery_capable(authorization_id="auth-test-01")

    def test_assert_recovery_capable_missing_feature(self):
        def handler(request):
            return UnrealTransportResponse(
                request_id=request.request_id,
                operation_name=request.operation_name,
                entity_ids=request.entity_ids,
                success=True,
                observed_state={
                    # Missing reconcile_render_jobs
                    "capabilities": ["atlas_job_id", "session_identity", "durable_journal"],
                },
                error="",
                source="unreal-editor-5.6",
                schema_version=1,
                error_code="",
                session_identity={},
            )

        transport = MockTransport(handler)
        adapter = UnrealAdapterProduction(transport)
        with pytest.raises(UnrealAdapterError, match="lacks required recovery capabilities"):
            adapter.assert_recovery_capable(authorization_id="auth-test-01")

    def test_query_capabilities_server_error(self):
        def handler(request):
            return UnrealTransportResponse(
                request_id=request.request_id,
                operation_name=request.operation_name,
                entity_ids=request.entity_ids,
                success=False,
                observed_state={},
                error="Unknown operation",
                source="unreal-editor-5.6",
                schema_version=1,
                error_code="ERR_UNKNOWN_OPERATION",
                session_identity={},
            )

        transport = MockTransport(handler)
        adapter = UnrealAdapterProduction(transport)
        with pytest.raises(UnrealAdapterError, match="get_capabilities failed"):
            adapter.query_capabilities(authorization_id="auth-test-01")
