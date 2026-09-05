"""Regression tests for Atlas ↔ Unreal transport serialization.

Coverage targets:
- Deterministic canonical JSON output for requests.
- Round-trip fidelity: request → serialize → deserialize → identical fields.
- Round-trip fidelity: response → serialize (via json) → deserialize → identical fields.
- Fail-closed deserialization on invalid JSON, missing keys, extra keys, wrong types.
- Nested entity_ids tuple/list normalization.
- TransportDeserializationError is raised (not generic exceptions).
"""

import json

import pytest

from planning.unreal_transport_contract import (
    UnrealTransportRequest,
    UnrealTransportResponse,
)
from planning.unreal_transport_serialization import (
    TransportDeserializationError,
    deserialize_request,
    deserialize_response,
    serialize_request,
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


def _valid_response_dict(**overrides):
    defaults = dict(
        request_id="req-001",
        operation_name="inspect_target_actors",
        entity_ids=["FIELD_SURFACE"],
        success=True,
        observed_state={"location": [100, 200, 300]},
        error="",
        source="unreal-editor-5.6",
    )
    defaults.update(overrides)
    return defaults


def _valid_response_json(**overrides):
    return json.dumps(_valid_response_dict(**overrides), sort_keys=True, separators=(",", ":"))


# ── Request serialization ────────────────────────────────────────────────

class TestSerializeRequest:
    def test_produces_valid_json(self):
        req = _valid_request()
        raw = serialize_request(req)
        data = json.loads(raw)
        assert data["request_id"] == "req-001"
        assert data["operation_name"] == "inspect_target_actors"
        assert data["capability"] == "inspect_actor"
        assert data["kind"] == "read"
        assert data["entity_ids"] == ["FIELD_SURFACE"]
        assert data["authorization_id"] == "auth-abc-123"

    def test_deterministic_output(self):
        req = _valid_request()
        assert serialize_request(req) == serialize_request(req)

    def test_entity_ids_serialized_as_array(self):
        req = _valid_request(entity_ids=("A", "B"))
        data = json.loads(serialize_request(req))
        assert isinstance(data["entity_ids"], list)
        assert data["entity_ids"] == ["A", "B"]

    def test_nested_tuple_in_arguments_serialized_as_array(self):
        req = _valid_request(arguments={"entity_ids": ("X", "Y")})
        data = json.loads(serialize_request(req))
        assert isinstance(data["arguments"]["entity_ids"], list)
        assert data["arguments"]["entity_ids"] == ["X", "Y"]

    def test_sorted_keys(self):
        req = _valid_request()
        raw = serialize_request(req)
        data = json.loads(raw)
        assert list(data.keys()) == sorted(data.keys())

    def test_rejects_non_request(self):
        with pytest.raises(TypeError, match="UnrealTransportRequest"):
            serialize_request({"not": "a request"})

    def test_multiple_entity_ids(self):
        req = _valid_request(
            entity_ids=("ACTOR_A", "ACTOR_B"),
            arguments={"entity_ids": ("ACTOR_A", "ACTOR_B")},
        )
        data = json.loads(serialize_request(req))
        assert data["entity_ids"] == ["ACTOR_A", "ACTOR_B"]
        assert data["arguments"]["entity_ids"] == ["ACTOR_A", "ACTOR_B"]


# ── Request round-trip ───────────────────────────────────────────────────

class TestRequestRoundTrip:
    def test_round_trip_preserves_all_fields(self):
        original = _valid_request()
        raw = serialize_request(original)
        restored = deserialize_request(raw)
        assert restored.request_id == original.request_id
        assert restored.operation_name == original.operation_name
        assert restored.capability == original.capability
        assert restored.kind == original.kind
        assert restored.entity_ids == original.entity_ids
        assert restored.authorization_id == original.authorization_id
        assert restored.arguments["entity_ids"] == original.arguments["entity_ids"]

    def test_round_trip_multiple_entities(self):
        original = _valid_request(
            entity_ids=("A", "B", "C"),
            arguments={"entity_ids": ("A", "B", "C")},
        )
        restored = deserialize_request(serialize_request(original))
        assert restored.entity_ids == ("A", "B", "C")
        assert restored.arguments["entity_ids"] == ("A", "B", "C")


# ── Request deserialization fail-closed ──────────────────────────────────

class TestDeserializeRequestFailClosed:
    def test_invalid_json(self):
        with pytest.raises(TransportDeserializationError, match="not valid JSON"):
            deserialize_request("{bad json")

    def test_not_a_string(self):
        with pytest.raises(TransportDeserializationError, match="must be a string"):
            deserialize_request(12345)

    def test_json_array_instead_of_object(self):
        with pytest.raises(TransportDeserializationError, match="JSON object"):
            deserialize_request("[]")

    def test_missing_key(self):
        data = _valid_response_dict()  # wrong shape for request
        with pytest.raises(TransportDeserializationError, match="missing keys"):
            deserialize_request(json.dumps(data))

    def test_extra_key(self):
        req = _valid_request()
        raw = serialize_request(req)
        data = json.loads(raw)
        data["extra_field"] = "surprise"
        with pytest.raises(TransportDeserializationError, match="extra keys"):
            deserialize_request(json.dumps(data))

    def test_entity_ids_not_array(self):
        req = _valid_request()
        raw = serialize_request(req)
        data = json.loads(raw)
        data["entity_ids"] = "FIELD_SURFACE"
        with pytest.raises(TransportDeserializationError, match="entity_ids must be a JSON array"):
            deserialize_request(json.dumps(data))

    def test_arguments_not_object(self):
        req = _valid_request()
        raw = serialize_request(req)
        data = json.loads(raw)
        data["arguments"] = "not-an-object"
        with pytest.raises(TransportDeserializationError, match="arguments must be a JSON object"):
            deserialize_request(json.dumps(data))


# ── Response deserialization valid ───────────────────────────────────────

class TestDeserializeResponseValid:
    def test_success_response(self):
        resp = deserialize_response(_valid_response_json())
        assert resp.request_id == "req-001"
        assert resp.operation_name == "inspect_target_actors"
        assert resp.entity_ids == ("FIELD_SURFACE",)
        assert resp.success is True
        assert resp.observed_state == {"location": [100, 200, 300]}
        assert resp.error == ""
        assert resp.source == "unreal-editor-5.6"

    def test_failure_response(self):
        resp = deserialize_response(
            _valid_response_json(success=False, error="actor not found")
        )
        assert resp.success is False
        assert resp.error == "actor not found"

    def test_no_verified_field(self):
        resp = deserialize_response(_valid_response_json())
        assert not hasattr(resp, "verified")

    def test_multiple_entity_ids(self):
        resp = deserialize_response(
            _valid_response_json(entity_ids=["A", "B"])
        )
        assert resp.entity_ids == ("A", "B")

    def test_frozen(self):
        resp = deserialize_response(_valid_response_json())
        with pytest.raises(AttributeError):
            resp.success = False


# ── Response deserialization fail-closed ─────────────────────────────────

class TestDeserializeResponseFailClosed:
    def test_invalid_json(self):
        with pytest.raises(TransportDeserializationError, match="not valid JSON"):
            deserialize_response("{bad")

    def test_not_a_string(self):
        with pytest.raises(TransportDeserializationError, match="must be a string"):
            deserialize_response(42)

    def test_json_array(self):
        with pytest.raises(TransportDeserializationError, match="JSON object"):
            deserialize_response("[]")

    def test_missing_key(self):
        data = _valid_response_dict()
        del data["source"]
        with pytest.raises(TransportDeserializationError, match="missing keys"):
            deserialize_response(json.dumps(data))

    def test_extra_key(self):
        data = _valid_response_dict()
        data["verified"] = True
        with pytest.raises(TransportDeserializationError, match="extra keys"):
            deserialize_response(json.dumps(data))

    def test_entity_ids_not_array(self):
        data = _valid_response_dict()
        data["entity_ids"] = "FIELD_SURFACE"
        with pytest.raises(TransportDeserializationError, match="entity_ids must be a JSON array"):
            deserialize_response(json.dumps(data))

    def test_observed_state_not_object(self):
        data = _valid_response_dict()
        data["observed_state"] = "flat-string"
        with pytest.raises(TransportDeserializationError, match="observed_state must be a JSON object"):
            deserialize_response(json.dumps(data))

    def test_success_not_boolean(self):
        data = _valid_response_dict()
        data["success"] = 1
        with pytest.raises(TransportDeserializationError, match="success must be a JSON boolean"):
            deserialize_response(json.dumps(data))

    def test_success_string_true_rejected(self):
        data = _valid_response_dict()
        data["success"] = "true"
        with pytest.raises(TransportDeserializationError, match="success must be a JSON boolean"):
            deserialize_response(json.dumps(data))

    def test_empty_request_id_rejected_by_post_init(self):
        """Even if JSON is structurally valid, __post_init__ catches empty strings."""
        data = _valid_response_dict()
        data["request_id"] = ""
        with pytest.raises(ValueError, match="request_id"):
            deserialize_response(json.dumps(data))

    def test_empty_source_rejected_by_post_init(self):
        data = _valid_response_dict()
        data["source"] = "   "
        with pytest.raises(ValueError, match="source"):
            deserialize_response(json.dumps(data))

    def test_empty_entity_id_rejected_by_post_init(self):
        data = _valid_response_dict()
        data["entity_ids"] = [""]
        with pytest.raises(ValueError, match="entity_ids"):
            deserialize_response(json.dumps(data))


# ── Response round-trip ──────────────────────────────────────────────────

class TestResponseRoundTrip:
    def test_serialize_then_deserialize(self):
        """Manually serialize a response dict, deserialize, verify fields."""
        raw = _valid_response_json()
        resp = deserialize_response(raw)
        # Re-serialize to canonical JSON and deserialize again
        reserialized = json.dumps(
            {
                "request_id": resp.request_id,
                "operation_name": resp.operation_name,
                "entity_ids": list(resp.entity_ids),
                "success": resp.success,
                "observed_state": dict(resp.observed_state),
                "error": resp.error,
                "source": resp.source,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        resp2 = deserialize_response(reserialized)
        assert resp2.request_id == resp.request_id
        assert resp2.operation_name == resp.operation_name
        assert resp2.entity_ids == resp.entity_ids
        assert resp2.success == resp.success
        assert resp2.observed_state == resp.observed_state
        assert resp2.error == resp.error
        assert resp2.source == resp.source


# ── Verified field never injected ────────────────────────────────────────

class TestVerifiedNeverPresent:
    def test_extra_verified_key_rejected(self):
        """A response with a 'verified' key must be rejected as an extra key."""
        data = _valid_response_dict()
        data["verified"] = True
        with pytest.raises(TransportDeserializationError, match="extra keys"):
            deserialize_response(json.dumps(data))

    def test_deserialized_response_has_no_verified(self):
        resp = deserialize_response(_valid_response_json())
        assert "verified" not in vars(resp) or not hasattr(resp, "verified")
