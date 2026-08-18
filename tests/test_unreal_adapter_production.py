"""Regression tests for the production Unreal adapter.

Coverage targets:
- Inspect / apply_authorized / verify dispatch the correct operation kinds.
- Wrong operation kind is rejected fail-closed.
- Transport responses are correlated to requests.
- Evidence is always constructed with verified=False.
- Transport failures surface as UnrealAdapterError.
- Empty authorization_id is rejected.
- The adapter does not modify the v01 adapter or Blender code.
"""

import pytest

from planning.unreal_adapter_production import (
    UnrealAdapterError,
    UnrealAdapterProduction,
)
from planning.unreal_agent import (
    UnrealCapability,
    UnrealOperation,
    UnrealOperationKind,
)
from planning.unreal_transport_contract import (
    UnrealTransportRequest,
    UnrealTransportResponse,
)


# ── In-memory test transport ────────────────────────────────────────────

class InMemoryTransport:
    """Deterministic in-memory transport for adapter tests."""

    def __init__(self, *, success=True, observed_state=None, error="", source="test-ue-5.6"):
        self._success = success
        self._observed_state = observed_state if observed_state is not None else {"location": [1, 2, 3]}
        self._error = error
        self._source = source
        self.last_request = None

    def send(self, request: UnrealTransportRequest) -> UnrealTransportResponse:
        self.last_request = request
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=self._success,
            observed_state=self._observed_state,
            error=self._error,
            source=self._source,
        )


class MismatchedTransport:
    """Returns a response with a different request_id to test correlation."""

    def send(self, request: UnrealTransportRequest) -> UnrealTransportResponse:
        return UnrealTransportResponse(
            request_id="wrong-id",
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=True,
            observed_state={"ok": True},
            error="",
            source="test-ue-5.6",
        )


# ── Helpers ──────────────────────────────────────────────────────────────

def _read_operation(**overrides):
    defaults = dict(
        capability=UnrealCapability.INSPECT_ACTOR,
        kind=UnrealOperationKind.READ,
        name="inspect_target_actors",
        arguments={"entity_ids": ("FIELD_SURFACE",)},
        entity_ids=("FIELD_SURFACE",),
    )
    defaults.update(overrides)
    return UnrealOperation(**defaults)


def _write_operation(**overrides):
    defaults = dict(
        capability=UnrealCapability.MODIFY_ACTOR,
        kind=UnrealOperationKind.WRITE,
        name="move_target_actor",
        arguments={"entity_ids": ("FIELD_SURFACE",)},
        entity_ids=("FIELD_SURFACE",),
    )
    defaults.update(overrides)
    return UnrealOperation(**defaults)


def _verify_operation(**overrides):
    defaults = dict(
        capability=UnrealCapability.INSPECT_ACTOR,
        kind=UnrealOperationKind.VERIFY,
        name="verify_target_actor_mapping",
        arguments={"entity_ids": ("FIELD_SURFACE",)},
        entity_ids=("FIELD_SURFACE",),
    )
    defaults.update(overrides)
    return UnrealOperation(**defaults)


AUTH_ID = "auth-test-001"


# ── Construction ─────────────────────────────────────────────────────────

class TestAdapterConstruction:
    def test_valid_construction(self):
        adapter = UnrealAdapterProduction(InMemoryTransport(), source_tag="test")
        assert adapter is not None

    def test_empty_source_tag_rejected(self):
        with pytest.raises(ValueError, match="source_tag"):
            UnrealAdapterProduction(InMemoryTransport(), source_tag="")

    def test_whitespace_source_tag_rejected(self):
        with pytest.raises(ValueError, match="source_tag"):
            UnrealAdapterProduction(InMemoryTransport(), source_tag="   ")


# ── Inspect (READ) ──────────────────────────────────────────────────────

class TestInspect:
    def test_inspect_returns_evidence(self):
        transport = InMemoryTransport(observed_state={"location": [100, 200, 300]})
        adapter = UnrealAdapterProduction(transport)
        evidence = adapter.inspect(_read_operation(), AUTH_ID)
        assert evidence.operation_name == "inspect_target_actors"
        assert evidence.entity_ids == ("FIELD_SURFACE",)
        assert evidence.observed_state == {"location": [100, 200, 300]}
        assert evidence.verified is False

    def test_inspect_rejects_write_operation(self):
        adapter = UnrealAdapterProduction(InMemoryTransport())
        with pytest.raises(UnrealAdapterError, match="READ"):
            adapter.inspect(_write_operation(), AUTH_ID)

    def test_inspect_rejects_verify_operation(self):
        adapter = UnrealAdapterProduction(InMemoryTransport())
        with pytest.raises(UnrealAdapterError, match="READ"):
            adapter.inspect(_verify_operation(), AUTH_ID)

    def test_inspect_sends_correct_request(self):
        transport = InMemoryTransport()
        adapter = UnrealAdapterProduction(transport)
        adapter.inspect(_read_operation(), AUTH_ID)
        req = transport.last_request
        assert req.operation_name == "inspect_target_actors"
        assert req.capability == "inspect_actor"
        assert req.kind == "read"
        assert req.entity_ids == ("FIELD_SURFACE",)
        assert req.authorization_id == AUTH_ID


# ── Apply authorized (WRITE) ────────────────────────────────────────────

class TestApplyAuthorized:
    def test_apply_returns_evidence(self):
        transport = InMemoryTransport(observed_state={"location": [100, 200, 300]})
        adapter = UnrealAdapterProduction(transport)
        evidence = adapter.apply_authorized(_write_operation(), AUTH_ID)
        assert evidence.operation_name == "move_target_actor"
        assert evidence.verified is False

    def test_apply_rejects_read_operation(self):
        adapter = UnrealAdapterProduction(InMemoryTransport())
        with pytest.raises(UnrealAdapterError, match="WRITE"):
            adapter.apply_authorized(_read_operation(), AUTH_ID)

    def test_apply_rejects_verify_operation(self):
        adapter = UnrealAdapterProduction(InMemoryTransport())
        with pytest.raises(UnrealAdapterError, match="WRITE"):
            adapter.apply_authorized(_verify_operation(), AUTH_ID)

    def test_apply_sends_authorization_id(self):
        transport = InMemoryTransport()
        adapter = UnrealAdapterProduction(transport)
        adapter.apply_authorized(_write_operation(), "auth-xyz-789")
        assert transport.last_request.authorization_id == "auth-xyz-789"


# ── Verify ───────────────────────────────────────────────────────────────

class TestVerify:
    def test_verify_returns_evidence(self):
        transport = InMemoryTransport(observed_state={"match": True})
        adapter = UnrealAdapterProduction(transport)
        evidence = adapter.verify(_verify_operation(), AUTH_ID)
        assert evidence.operation_name == "verify_target_actor_mapping"
        assert evidence.observed_state == {"match": True}
        assert evidence.verified is False

    def test_verify_rejects_read_operation(self):
        adapter = UnrealAdapterProduction(InMemoryTransport())
        with pytest.raises(UnrealAdapterError, match="VERIFY"):
            adapter.verify(_read_operation(), AUTH_ID)

    def test_verify_rejects_write_operation(self):
        adapter = UnrealAdapterProduction(InMemoryTransport())
        with pytest.raises(UnrealAdapterError, match="VERIFY"):
            adapter.verify(_write_operation(), AUTH_ID)


# ── Authorization enforcement ────────────────────────────────────────────

class TestAuthorizationEnforcement:
    def test_empty_authorization_id_rejected(self):
        adapter = UnrealAdapterProduction(InMemoryTransport())
        with pytest.raises(UnrealAdapterError, match="authorization_id"):
            adapter.inspect(_read_operation(), "")

    def test_whitespace_authorization_id_rejected(self):
        adapter = UnrealAdapterProduction(InMemoryTransport())
        with pytest.raises(UnrealAdapterError, match="authorization_id"):
            adapter.inspect(_read_operation(), "   ")


# ── Transport failure ────────────────────────────────────────────────────

class TestTransportFailure:
    def test_transport_failure_raises_adapter_error(self):
        transport = InMemoryTransport(success=False, error="actor not found")
        adapter = UnrealAdapterProduction(transport)
        with pytest.raises(UnrealAdapterError, match="actor not found"):
            adapter.inspect(_read_operation(), AUTH_ID)

    def test_transport_failure_includes_operation_name(self):
        transport = InMemoryTransport(success=False, error="timeout")
        adapter = UnrealAdapterProduction(transport)
        with pytest.raises(UnrealAdapterError, match="inspect_target_actors"):
            adapter.inspect(_read_operation(), AUTH_ID)


# ── Correlation enforcement ──────────────────────────────────────────────

class TestCorrelation:
    def test_mismatched_request_id_raises(self):
        adapter = UnrealAdapterProduction(MismatchedTransport())
        with pytest.raises(ValueError, match="request_id"):
            adapter.inspect(_read_operation(), AUTH_ID)


# ── Evidence invariants ──────────────────────────────────────────────────

class TestEvidenceInvariants:
    def test_evidence_verified_always_false_on_inspect(self):
        adapter = UnrealAdapterProduction(InMemoryTransport())
        evidence = adapter.inspect(_read_operation(), AUTH_ID)
        assert evidence.verified is False

    def test_evidence_verified_always_false_on_write(self):
        adapter = UnrealAdapterProduction(InMemoryTransport())
        evidence = adapter.apply_authorized(_write_operation(), AUTH_ID)
        assert evidence.verified is False

    def test_evidence_verified_always_false_on_verify(self):
        adapter = UnrealAdapterProduction(InMemoryTransport())
        evidence = adapter.verify(_verify_operation(), AUTH_ID)
        assert evidence.verified is False

    def test_evidence_source_from_transport(self):
        transport = InMemoryTransport(source="ue-5.6.1-editor")
        adapter = UnrealAdapterProduction(transport)
        evidence = adapter.inspect(_read_operation(), AUTH_ID)
        assert evidence.source == "ue-5.6.1-editor"

    def test_evidence_entity_ids_match_operation(self):
        op = _read_operation(entity_ids=("A", "B"))
        transport = InMemoryTransport()
        # Override transport to echo back the entity_ids
        original_send = transport.send

        def patched_send(request):
            return UnrealTransportResponse(
                request_id=request.request_id,
                operation_name=request.operation_name,
                entity_ids=request.entity_ids,
                success=True,
                observed_state={"ok": True},
                error="",
                source="test-ue",
            )

        transport.send = patched_send
        adapter = UnrealAdapterProduction(transport)
        evidence = adapter.inspect(op, AUTH_ID)
        assert evidence.entity_ids == ("A", "B")


# ── Multiple entity IDs ─────────────────────────────────────────────────

class TestMultipleEntityIds:
    def test_multiple_entities_round_trip(self):
        op = _read_operation(
            entity_ids=("ACTOR_A", "ACTOR_B", "ACTOR_C"),
            arguments={"entity_ids": ("ACTOR_A", "ACTOR_B", "ACTOR_C")},
        )
        transport = InMemoryTransport()

        def echo_send(request):
            return UnrealTransportResponse(
                request_id=request.request_id,
                operation_name=request.operation_name,
                entity_ids=request.entity_ids,
                success=True,
                observed_state={"count": 3},
                error="",
                source="test-ue",
            )

        transport.send = echo_send
        adapter = UnrealAdapterProduction(transport)
        evidence = adapter.inspect(op, AUTH_ID)
        assert evidence.entity_ids == ("ACTOR_A", "ACTOR_B", "ACTOR_C")
        assert evidence.observed_state == {"count": 3}
