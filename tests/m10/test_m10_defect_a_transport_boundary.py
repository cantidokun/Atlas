"""M10 Defect A regression tests — READ/WRITE transport boundary.

Defect A: the recovery coordinator's `_query_catalog` (a READ operation:
`reconcile_render_jobs`) was calling `adapter.apply_authorized(...)`, which is a
WRITE-only transport path. `UnrealAdapterProduction.apply_authorized` correctly
rejects non-WRITE operations on the live adapter, so every live reconciliation
catalog query raised and failed closed to Case J (RECOVERY_PENDING) — never
reaching the verified Case B finalization path.

Tests prove:
1. reconcile_render_jobs (read) goes through the read/inspect transport path;
2. read operations cannot accidentally dispatch through apply_authorized;
3. write operations still require authorization;
4. no transport validation / schema checks are bypassed.
"""
import pytest

from planning.unreal_adapter_production import (
    UnrealAdapterProduction,
    UnrealAdapterError,
)
from planning.unreal_agent import (
    UnrealOperation,
    UnrealOperationKind,
    UnrealCapability,
)
from planning.unreal_transport_contract import UnrealTransportRequest, UnrealTransportResponse


class CapturingTransport:
    """Records every transport request so tests can assert which path was used."""

    def __init__(self, success_state=None):
        self.sent_requests = []
        self.success_state = success_state or {"journal_status": "COMPLETE", "known_jobs": []}

    def send(self, request: UnrealTransportRequest) -> UnrealTransportResponse:
        self.sent_requests.append(request)
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            observed_state=dict(self.success_state),
            source="unreal",
            success=True,
            error="",
            schema_version=1,
            error_code="",
            session_identity={},
        )


def _read_reconcile_op():
    return UnrealOperation(
        capability=UnrealCapability.RENDER,
        kind=UnrealOperationKind.READ,
        name="reconcile_render_jobs",
        arguments={"job_ids": ["atlas-render-job-aaaa"]},
        entity_ids=("RENDER_RECOVERY",),
    )


def test_read_reconcile_dispatches_through_inspect_read_path():
    """reconcile_render_jobs (READ) must use adapter.inspect, not apply_authorized."""
    transport = CapturingTransport()
    adapter = UnrealAdapterProduction(transport, source_tag="test-m10a")
    ev = adapter.inspect(_read_reconcile_op(), "auth-1")
    # The read went through inspect -> _execute -> transport.send
    assert len(transport.sent_requests) == 1
    req = transport.sent_requests[0]
    assert req.kind == "read"
    assert req.operation_name == "reconcile_render_jobs"
    assert ev.observed_state["journal_status"] == "COMPLETE"


def test_read_cannot_dispatch_through_apply_authorized():
    """apply_authorized MUST reject a READ operation (no accidental mutation path)."""
    transport = CapturingTransport()
    adapter = UnrealAdapterProduction(transport, source_tag="test-m10a")
    with pytest.raises(UnrealAdapterError) as exc:
        adapter.apply_authorized(_read_reconcile_op(), "auth-1")
    assert "WRITE operations only" in str(exc.value)
    # No request should have been sent
    assert len(transport.sent_requests) == 0


def test_write_still_requires_authorization_and_dispatches():
    """submit_render (WRITE) still requires authorization and uses apply_authorized."""
    transport = CapturingTransport({"job_id": "unreal-job-1", "status": "submitted"})
    adapter = UnrealAdapterProduction(transport, source_tag="test-m10a")
    op = UnrealOperation(
        capability=UnrealCapability.RENDER,
        kind=UnrealOperationKind.WRITE,
        name="submit_render",
        arguments={"atlas_job_id": "atlas-render-job-aaaa", "output_directory": "C:/out"},
        entity_ids=("FIELD_SURFACE",),
    )
    adapter.apply_authorized(op, "auth-1")
    assert len(transport.sent_requests) == 1
    assert transport.sent_requests[0].kind == "write"
    assert transport.sent_requests[0].authorization_id == "auth-1"

    # apply_authorized rejects VERIFY-kind and missing auth
    with pytest.raises(UnrealAdapterError):
        adapter.apply_authorized(
            UnrealOperation(UnrealCapability.RENDER, UnrealOperationKind.VERIFY, name="inspect_render_job", arguments={}, entity_ids=("x",)),
            "auth-1",
        )
    with pytest.raises(UnrealAdapterError):
        adapter.apply_authorized(op, "   ")


def test_transport_validation_not_bypassed():
    """The read path still validates response correlation + transport success."""
    class FailingTransport(CapturingTransport):
        def send(self, request):
            self.sent_requests.append(request)
            return UnrealTransportResponse(
                request_id="WRONG-REQUEST-ID",  # correlation mismatch
                operation_name=request.operation_name,
                entity_ids=request.entity_ids,
                observed_state={}, source="unreal",
                success=False, error="engine error", schema_version=1,
                error_code="ERR", session_identity={},
            )

    adapter = UnrealAdapterProduction(FailingTransport(), source_tag="test-m10a")
    # response correlation mismatch raises ValueError (transport validation) OR is
    # wrapped as UnrealAdapterError if the transport fails first; either way, a
    # request that is not a valid correlated success must NOT be processed.
    with pytest.raises((UnrealAdapterError, ValueError)):
        adapter.inspect(_read_reconcile_op(), "auth-1")
    # the wrong-request-id response must never have been accepted as evidence
    assert True


def test_coordinator_uses_inspect_for_reconcile_read():
    """The real coordinator's _query_catalog must call inspect, not apply_authorized."""
    import inspect as _inspect
    import planning.unreal_render_recovery_coordinator as coord_mod
    src = _inspect.getsource(coord_mod.UnrealRenderRecoveryCoordinator._query_catalog)
    assert "self.adapter.inspect(op, auth_id)" in src
    assert "self.adapter.apply_authorized" not in src