"""M10 Defect C regression tests — `_query_catalog` / adapter argument shape.

Defect C root cause (from the live S1 verification run):
`UnrealTransportRequest.arguments` is built by the adapter as a verbatim copy of
`operation.arguments`, with `entity_ids` carried ONLY at the top level of the
request. The C++ `ValidateRequest` generic validator requires `arguments.entity_ids`
(a nested array) to exist and match the top-level `entity_ids` for EVERY operation
(reconcile_render_jobs, inspect_render_job, etc.). Because the coordinator's
`reconcile_render_jobs` operation carries `arguments={"job_ids":[...]}` and
`entity_ids=("RENDER_RECOVERY",)` (entity_ids NOT nested under arguments), the
engine rejected the live request with:

    arguments.entity_ids must be an array of strings (ERR_MISSING_ARGUMENT)

i.e. the same requests the deterministic tests accepted via MagicMock were REJECTED
by the live C++ engine, because the mocks never enforced the nested `arguments.
entity_ids` contract.

Fix (adapter transport boundary, not coordinator): `UnrealAdapterProduction.
_build_request` ensures the nested `arguments.entity_ids` array matches the
operation's `entity_ids`, so every READ (and WRITE) carries the entity_ids the
engine requires. No coordinator transport-detail knowledge; no special-case; no
value synthesis.
"""
import pytest

from planning.unreal_adapter_production import (
    UnrealAdapterProduction,
    UnrealAdapterError,
)
from planning.unreal_agent import UnrealOperation, UnrealOperationKind, UnrealCapability
from planning.unreal_transport_contract import (
    UnrealTransportRequest,
    UnrealTransportResponse,
)


class EngineLikeTransport:
    """Transport that enforces the REAL C++ ValidateRequest contract:
    arguments.entity_ids must be a string array matching the top-level entity_ids.
    Derived from the live failure (ERR_MISSING_ARGUMENT)."""

    def __init__(self):
        self.sent_requests = []

    def _validate(self, request):
        if not request.arguments or "entity_ids" not in request.arguments:
            raise ValueError(
                "arguments.entity_ids must be an array of strings (ERR_MISSING_ARGUMENT)")
        a = request.arguments["entity_ids"]
        if not isinstance(a, (list, tuple)) or not all(isinstance(x, str) for x in a):
            raise ValueError("arguments.entity_ids must be an array of strings")
        if list(a) != list(request.entity_ids):
            raise ValueError("arguments.entity_ids must match entity_ids")

    def send(self, request):
        self.sent_requests.append(request)
        self._validate(request)
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            observed_state={"journal_status": "COMPLETE", "known_jobs": []},
            source="unreal",
            success=True,
            schema_version=1,
            error="",
            error_code="",
            session_identity={},
        )


def _reconcile_op():
    """THE EXACT live-shaped operation the coordinator builds for reconcile."""
    return UnrealOperation(
        capability=UnrealCapability.RENDER,
        kind=UnrealOperationKind.READ,
        name="reconcile_render_jobs",
        arguments={"job_ids": ["atlas-render-job-d2a8c855-af47-4dc7-8953-d48cb3964e60"]},
        entity_ids=("RENDER_RECOVERY",),
    )


def _require_nested_entity_ids(adapter, transport, op):
    """Run the operation through the adapter and return the built+validated request."""
    try:
        ev = adapter.inspect(op, "auth-1")
    except Exception as exc:
        assert False, f"adapter.inspect raised under engine-like transport: {exc}"
    return transport.sent_requests[-1]


def test_defect_c_exact_live_request_accept_after_fix():
    """The exact live reconcile request must be ACCEPTED by an engine-like transport
    (arguable only with a correct adapter; this is the regression that failed live)."""
    transport = EngineLikeTransport()
    adapter = UnrealAdapterProduction(transport, source_tag="test-c")
    req = _require_nested_entity_ids(adapter, transport, _reconcile_op())
    assert req.kind == "read"
    assert req.operation_name == "reconcile_render_jobs"
    # FIX asserts: nested arguments.entity_ids present + matches top-level
    assert req.arguments["entity_ids"] == list(req.entity_ids) == ["RENDER_RECOVERY"]


def test_defect_c_engine_rejects_wrong_shape():
    """A transport built WITHOUT injecting entity_ids must be REJECTED by the
    engine-like validator (reproduces the live ERR_MISSING_ARGUMENT)."""
    transport = EngineLikeTransport()
    # bypass the adapter fix: hand-build a request missing nested entity_ids
    op = _reconcile_op()
    bad = UnrealTransportRequest(
        request_id="bad-1", operation_name=op.name, capability="render", kind="read",
        arguments=dict(op.arguments),  # no entity_ids injected
        entity_ids=op.entity_ids, authorization_id="auth-1", schema_version=1,
    )
    with pytest.raises(ValueError) as exc:
        transport.send(bad)
    assert "entity_ids" in str(exc.value)


def test_defect_c_coordinator_constructs_read_request():
    """The coordinator's _query_catalog must still build a READ op; entity_ids at
    operation level (the adapter adds the nested copy)."""
    import inspect as _inspect
    import planning.unreal_render_recovery_coordinator as coord_mod
    src = _inspect.getsource(coord_mod.UnrealRenderRecoveryCoordinator._query_catalog)
    assert 'name="reconcile_render_jobs"' in src or '"reconcile_render_jobs"' in src
    assert "UnrealOperationKind.READ" in src
    assert "entity_ids=(\"RENDER_RECOVERY\",)" in src


def test_defect_c_adapter_builds_nested_entity_ids_for_reads():
    """inspect() receives a request whose arguments.entity_ids matches operation
    entity_ids for a READ-only path."""
    transport = EngineLikeTransport()
    adapter = UnrealAdapterProduction(transport, source_tag="test-c")
    op = _reconcile_op()
    ev = adapter.inspect(op, "auth-1")
    req = transport.sent_requests[-1]
    assert req.arguments["entity_ids"] == ["RENDER_RECOVERY"]


def test_defect_c_write_ops_also_get_nested_entity_ids_but_stay_authorized():
    """WRITE operations through apply_authorized also carry nested entity_ids, and
    still require authorization."""
    transport = EngineLikeTransport()
    adapter = UnrealAdapterProduction(transport, source_tag="test-c")
    op = UnrealOperation(
        capability=UnrealCapability.RENDER, kind=UnrealOperationKind.WRITE,
        name="submit_render",
        arguments={"atlas_job_id": "atlas-x", "output_directory": "C:/out"},
        entity_ids=("FIELD_SURFACE",),
    )
    adapter.apply_authorized(op, "auth-1")
    req = transport.sent_requests[-1]
    assert req.arguments["entity_ids"] == ["FIELD_SURFACE"]
    assert req.authorization_id == "auth-1"
    # missing auth still rejected
    with pytest.raises(UnrealAdapterError):
        adapter.apply_authorized(op, "   ")


def test_defect_c_correlation_schema_checks_still_active():
    """Schema/version/correlation validation must remain intact after the fix."""
    class BadTransport(EngineLikeTransport):
        def send(self, request):
            self.sent_requests.append(request)
            self._validate(request)
            return UnrealTransportResponse(
                request_id="WRONG-ID",  # correlation mismatch
                operation_name=request.operation_name,
                entity_ids=request.entity_ids,
                observed_state={}, source="unreal", success=False,
                schema_version=1, error="e", error_code="ERR", session_identity={},
            )
    adapter = UnrealAdapterProduction(BadTransport(), source_tag="test-c")
    # wrong request_id correlation must raise (ValueError from correlation validator)
    with pytest.raises((UnrealAdapterError, ValueError)):
        adapter.inspect(_reconcile_op(), "auth-1")


def test_defect_c_malformed_catalog_response_fails_closed():
    """A malformed reconcile response (missing known_jobs framing) still fails
    closed in the coordinator (no synthesized values)."""
    import sys, pathlib, tempfile
    sys.path.insert(0, r"C:/Users/Gavin's PC/Desktop/Atlas")
    from unittest.mock import MagicMock
    from planning.unreal_evidence_contract import UnrealEvidence
    from planning.unreal_render_recovery_coordinator import UnrealRenderRecoveryCoordinator
    from planning.unreal_render_job_store import AtlasRenderJobStore
    from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
    from scripts.run_unreal_supervisor import AtlasProcessSupervisor
    import tests.m6.fault_fixtures as ff
    import sys

    tmp = pathlib.Path(tempfile.mkdtemp())
    store = AtlasRenderJobStore(tmp / "store")
    record = ff.make_submitted_record(tmp, attempt_nonce="c-nonce-1234567890abcdef")
    store.create(record)

    adapter = MagicMock()
    adapter.assert_recovery_capable = MagicMock(return_value=None)
    # malformed / unreadable framing -> fail closed (Case J)
    adapter.inspect.return_value = UnrealEvidence(
        operation_name="reconcile_render_jobs", entity_ids=("RENDER_RECOVERY",),
        observed_state={"journal_status": "UNREADABLE", "known_jobs": []},
        source="unreal", verified=True,
    )
    sv = MagicMock(spec=AtlasProcessSupervisor); sv.job_handle = 1; sv.query_active_processes.return_value = 2
    coord = UnrealRenderRecoveryCoordinator(
        store=store, adapter=adapter,
        receipt_store=UnrealRenderReceiptStore(tmp / "rcpt.json"),
        supervisor=sv, deployment_mode="CONTAINED_JOB_OBJECT")
    res = coord.reconcile_single_job(record.atlas_job_id)
    assert res.case_classified == "Case J"
    assert len(list(store.receipts_dir.glob("*.json"))) == 0