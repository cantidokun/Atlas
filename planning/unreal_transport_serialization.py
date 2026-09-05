"""Canonical JSON serialization for the Atlas ↔ Unreal transport boundary.

This module is a pure data-transformation layer. It does not contain business
logic, authorization decisions, or evidence verification.

Design invariants
-----------------
- Serialization is deterministic: same request always produces same bytes.
- Deserialization is fail-closed: missing keys, extra keys, or wrong types
  are rejected immediately.
- ``entity_ids`` are always serialized as JSON arrays of strings and
  deserialized back to Python tuples.
"""

import json
from typing import Any, Dict

from planning.unreal_transport_contract import (
    UnrealTransportRequest,
    UnrealTransportResponse,
)


# ---------------------------------------------------------------------------
# Canonical key sets — fail closed on any deviation
# ---------------------------------------------------------------------------

_REQUEST_KEYS = frozenset({
    "request_id",
    "operation_name",
    "capability",
    "kind",
    "arguments",
    "entity_ids",
    "authorization_id",
})

_RESPONSE_KEYS = frozenset({
    "request_id",
    "operation_name",
    "entity_ids",
    "success",
    "observed_state",
    "error",
    "source",
})


# ---------------------------------------------------------------------------
# Request serialization  (Python → JSON → Unreal)
# ---------------------------------------------------------------------------

def serialize_request(request: UnrealTransportRequest) -> str:
    """Serialize a validated transport request to canonical JSON.

    The output is deterministic: keys are sorted and separators are compact.
    This is the exact payload that crosses the process boundary.
    """
    if not isinstance(request, UnrealTransportRequest):
        raise TypeError("expected an UnrealTransportRequest instance")

    payload: Dict[str, Any] = {
        "request_id": request.request_id,
        "operation_name": request.operation_name,
        "capability": request.capability,
        "kind": request.kind,
        "arguments": dict(request.arguments),
        "entity_ids": list(request.entity_ids),
        "authorization_id": request.authorization_id,
    }

    # Normalize nested entity_ids inside arguments to JSON arrays
    args = payload["arguments"]
    for key, value in args.items():
        if isinstance(value, tuple):
            args[key] = list(value)

    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Response deserialization  (Unreal → JSON → Python)
# ---------------------------------------------------------------------------

class TransportDeserializationError(ValueError):
    """Raised when a transport response payload cannot be safely parsed."""


def deserialize_response(raw: str) -> UnrealTransportResponse:
    """Deserialize a JSON payload into a validated transport response.

    Fails closed on:
    - invalid JSON
    - missing or extra top-level keys
    - wrong field types
    - empty identity strings
    - non-boolean ``success``
    - non-array ``entity_ids``

    The resulting ``UnrealTransportResponse`` is further validated by its
    own ``__post_init__``, so this function and the dataclass together
    form a double-validation boundary.
    """
    if not isinstance(raw, str):
        raise TransportDeserializationError("response payload must be a string")

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise TransportDeserializationError(
            f"response payload is not valid JSON: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise TransportDeserializationError(
            "response payload must be a JSON object"
        )

    actual_keys = frozenset(data.keys())
    if actual_keys != _RESPONSE_KEYS:
        missing = _RESPONSE_KEYS - actual_keys
        extra = actual_keys - _RESPONSE_KEYS
        parts = []
        if missing:
            parts.append(f"missing keys: {sorted(missing)}")
        if extra:
            parts.append(f"extra keys: {sorted(extra)}")
        raise TransportDeserializationError(
            f"response does not match the transport contract schema ({'; '.join(parts)})"
        )

    # --- type-level checks before constructing the frozen dataclass ---

    entity_ids_raw = data["entity_ids"]
    if not isinstance(entity_ids_raw, list):
        raise TransportDeserializationError("entity_ids must be a JSON array")

    entity_ids = tuple(entity_ids_raw)

    observed_state_raw = data["observed_state"]
    if not isinstance(observed_state_raw, dict):
        raise TransportDeserializationError(
            "observed_state must be a JSON object"
        )

    success_raw = data["success"]
    if not isinstance(success_raw, bool):
        raise TransportDeserializationError("success must be a JSON boolean")

    # Construct — __post_init__ provides the second validation layer
    return UnrealTransportResponse(
        request_id=data["request_id"],
        operation_name=data["operation_name"],
        entity_ids=entity_ids,
        success=success_raw,
        observed_state=observed_state_raw,
        error=data["error"],
        source=data["source"],
    )


# ---------------------------------------------------------------------------
# Request deserialization  (round-trip testing / diagnostics)
# ---------------------------------------------------------------------------

def deserialize_request(raw: str) -> UnrealTransportRequest:
    """Deserialize a JSON payload into a validated transport request.

    Primarily useful for round-trip verification and diagnostic tooling.
    Production C++ code parses requests independently.
    """
    if not isinstance(raw, str):
        raise TransportDeserializationError("request payload must be a string")

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise TransportDeserializationError(
            f"request payload is not valid JSON: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise TransportDeserializationError(
            "request payload must be a JSON object"
        )

    actual_keys = frozenset(data.keys())
    if actual_keys != _REQUEST_KEYS:
        missing = _REQUEST_KEYS - actual_keys
        extra = actual_keys - _REQUEST_KEYS
        parts = []
        if missing:
            parts.append(f"missing keys: {sorted(missing)}")
        if extra:
            parts.append(f"extra keys: {sorted(extra)}")
        raise TransportDeserializationError(
            f"request does not match the transport contract schema ({'; '.join(parts)})"
        )

    entity_ids_raw = data["entity_ids"]
    if not isinstance(entity_ids_raw, list):
        raise TransportDeserializationError("entity_ids must be a JSON array")

    arguments_raw = data["arguments"]
    if not isinstance(arguments_raw, dict):
        raise TransportDeserializationError("arguments must be a JSON object")

    # Normalize nested entity_ids back to tuples
    arguments = dict(arguments_raw)
    for key, value in arguments.items():
        if isinstance(value, list) and all(isinstance(v, str) for v in value):
            arguments[key] = tuple(value)

    return UnrealTransportRequest(
        request_id=data["request_id"],
        operation_name=data["operation_name"],
        capability=data["capability"],
        kind=data["kind"],
        arguments=arguments,
        entity_ids=tuple(entity_ids_raw),
        authorization_id=data["authorization_id"],
    )
