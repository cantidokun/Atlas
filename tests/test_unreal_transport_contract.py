"""Regression tests for the Atlas ↔ Unreal transport contract.

Coverage targets:
- Valid construction of request and response.
- Fail-closed rejection of every invalid field.
- Correlation validation between request and response.
- Immutability of transport messages.
- Absence of 'verified' in the response contract.
"""

import pytest

from planning.unreal_transport_contract import (
    UnrealTransportRequest,
    UnrealTransportResponse,
    validate_response_correlation,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _valid_request(**overrides):
    defaults = dict(
        request_id="req-001",
        operation_name="inspect_target_actors",
        capability="inspect_actor",
        kind="read",
        arguments={"entity_ids": ("FIELD_SURFACE",)},
        entity_ids=("FIELD_SURFACE",),
        authorization_id="auth-abc-123",
    )
    defaults.update(overrides)
    return UnrealTransportRequest(**defaults)


def _valid_response(**overrides):
    defaults = dict(
        request_id="req-001",
        operation_name="inspect_target_actors",
        entity_ids=("FIELD_SURFACE",),
        success=True,
        observed_state={"location": [100, 200, 300]},
        error="",
        source="unreal-editor-5.6",
    )
    defaults.update(overrides)
    return UnrealTransportResponse(**defaults)


# ── Request: valid construction ──────────────────────────────────────────

class TestUnrealTransportRequestValid:
    def test_construct_minimal(self):
        req = _valid_request()
        assert req.request_id == "req-001"
        assert req.operation_name == "inspect_target_actors"
        assert req.capability == "inspect_actor"
        assert req.kind == "read"
        assert req.entity_ids == ("FIELD_SURFACE",)
        assert req.authorization_id == "auth-abc-123"

    def test_multiple_entity_ids(self):
        req = _valid_request(entity_ids=("A", "B"), arguments={"entity_ids": ("A", "B")})
        assert req.entity_ids == ("A", "B")

    def test_frozen(self):
        req = _valid_request()
        with pytest.raises(AttributeError):
            req.request_id = "changed"


# ── Request: fail-closed validation ─────────────────────────────────────

class TestUnrealTransportRequestFailClosed:
    def test_empty_request_id(self):
        with pytest.raises(ValueError, match="request_id"):
            _valid_request(request_id="")

    def test_whitespace_request_id(self):
        with pytest.raises(ValueError, match="request_id"):
            _valid_request(request_id="   ")

    def test_empty_operation_name(self):
        with pytest.raises(ValueError, match="operation_name"):
            _valid_request(operation_name="")

    def test_empty_capability(self):
        with pytest.raises(ValueError, match="capability"):
            _valid_request(capability="")

    def test_empty_kind(self):
        with pytest.raises(ValueError, match="kind"):
            _valid_request(kind="")

    def test_arguments_not_mapping(self):
        with pytest.raises(TypeError, match="arguments"):
            _valid_request(arguments="not-a-mapping")

    def test_entity_ids_empty_tuple(self):
        with pytest.raises(ValueError, match="entity_ids"):
            _valid_request(entity_ids=())

    def test_entity_ids_not_tuple(self):
        with pytest.raises(ValueError, match="entity_ids"):
            _valid_request(entity_ids=["FIELD_SURFACE"])

    def test_entity_ids_contains_empty_string(self):
        with pytest.raises(ValueError, match="entity_ids"):
            _valid_request(entity_ids=("FIELD_SURFACE", ""))

    def test_entity_ids_contains_whitespace(self):
        with pytest.raises(ValueError, match="entity_ids"):
            _valid_request(entity_ids=("  ",))

    def test_empty_authorization_id(self):
        with pytest.raises(ValueError, match="authorization_id"):
            _valid_request(authorization_id="")

    def test_whitespace_authorization_id(self):
        with pytest.raises(ValueError, match="authorization_id"):
            _valid_request(authorization_id="   ")


# ── Response: valid construction ─────────────────────────────────────────

class TestUnrealTransportResponseValid:
    def test_construct_success(self):
        resp = _valid_response()
        assert resp.success is True
        assert resp.error == ""
        assert resp.source == "unreal-editor-5.6"

    def test_construct_failure(self):
        resp = _valid_response(success=False, error="actor not found")
        assert resp.success is False
        assert resp.error == "actor not found"

    def test_frozen(self):
        resp = _valid_response()
        with pytest.raises(AttributeError):
            resp.success = False

    def test_no_verified_field(self):
        """The transport response must never carry a 'verified' attribute."""
        resp = _valid_response()
        assert not hasattr(resp, "verified")


# ── Response: fail-closed validation ────────────────────────────────────

class TestUnrealTransportResponseFailClosed:
    def test_empty_request_id(self):
        with pytest.raises(ValueError, match="request_id"):
            _valid_response(request_id="")

    def test_empty_operation_name(self):
        with pytest.raises(ValueError, match="operation_name"):
            _valid_response(operation_name="")

    def test_entity_ids_empty(self):
        with pytest.raises(ValueError, match="entity_ids"):
            _valid_response(entity_ids=())

    def test_entity_ids_not_tuple(self):
        with pytest.raises(ValueError, match="entity_ids"):
            _valid_response(entity_ids=["FIELD_SURFACE"])

    def test_entity_ids_contains_empty(self):
        with pytest.raises(ValueError, match="entity_ids"):
            _valid_response(entity_ids=("",))

    def test_success_not_bool(self):
        with pytest.raises(TypeError, match="success"):
            _valid_response(success=1)

    def test_observed_state_not_mapping(self):
        with pytest.raises(TypeError, match="observed_state"):
            _valid_response(observed_state="not-a-mapping")

    def test_error_not_string(self):
        with pytest.raises(TypeError, match="error"):
            _valid_response(error=None)

    def test_empty_source(self):
        with pytest.raises(ValueError, match="source"):
            _valid_response(source="")

    def test_whitespace_source(self):
        with pytest.raises(ValueError, match="source"):
            _valid_response(source="   ")


# ── Correlation validation ──────────────────────────────────────────────

class TestResponseCorrelation:
    def test_valid_correlation(self):
        req = _valid_request()
        resp = _valid_response()
        result = validate_response_correlation(req, resp)
        assert result is resp

    def test_mismatched_request_id(self):
        req = _valid_request(request_id="req-001")
        resp = _valid_response(request_id="req-999")
        with pytest.raises(ValueError, match="request_id"):
            validate_response_correlation(req, resp)

    def test_mismatched_operation_name(self):
        req = _valid_request(operation_name="inspect_target_actors")
        resp = _valid_response(operation_name="apply_material_variant")
        with pytest.raises(ValueError, match="operation_name"):
            validate_response_correlation(req, resp)

    def test_mismatched_entity_ids(self):
        req = _valid_request(entity_ids=("FIELD_SURFACE",))
        resp = _valid_response(entity_ids=("OTHER_ENTITY",))
        with pytest.raises(ValueError, match="entity_ids"):
            validate_response_correlation(req, resp)

    def test_correlation_preserves_response(self):
        req = _valid_request()
        resp = _valid_response(success=False, error="timeout")
        result = validate_response_correlation(req, resp)
        assert result.success is False
        assert result.error == "timeout"
