"""Fail-closed transport contract for the Atlas ↔ Unreal production boundary.

This module defines the structured request/response shapes that cross the
process boundary between Atlas (Python) and the Unreal Editor (C++).

Design invariants
-----------------
- Both sides validate independently; neither trusts the other.
- ``authorization_id`` is transmitted, never issued, by the transport.
- Responses never carry a ``verified`` flag — Atlas verifies independently.
- All dataclasses are frozen; transport messages are immutable once created.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Tuple


# ---------------------------------------------------------------------------
# Request — Python → Unreal
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UnrealTransportRequest:
    """One authorized operation sent from Atlas to the Unreal process."""

    request_id: str
    operation_name: str
    capability: str
    kind: str
    arguments: Mapping[str, Any]
    entity_ids: Tuple[str, ...]
    authorization_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise ValueError("request_id must be a non-empty string")
        if not isinstance(self.operation_name, str) or not self.operation_name.strip():
            raise ValueError("operation_name must be a non-empty string")
        if not isinstance(self.capability, str) or not self.capability.strip():
            raise ValueError("capability must be a non-empty string")
        if not isinstance(self.kind, str) or not self.kind.strip():
            raise ValueError("kind must be a non-empty string")
        if not isinstance(self.arguments, Mapping):
            raise TypeError("arguments must be a mapping")
        if not isinstance(self.entity_ids, tuple) or not self.entity_ids:
            raise ValueError("entity_ids must be a non-empty tuple of strings")
        for eid in self.entity_ids:
            if not isinstance(eid, str) or not eid.strip():
                raise ValueError("entity_ids must contain only non-empty strings")
        if not isinstance(self.authorization_id, str) or not self.authorization_id.strip():
            raise ValueError("authorization_id must be a non-empty string")


# ---------------------------------------------------------------------------
# Response — Unreal → Python
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UnrealTransportResponse:
    """Structured result returned from the Unreal process to Atlas.

    ``observed_state`` is raw evidence collected by the Unreal side.
    It is **not** verified here — Atlas verification is independent.
    """

    request_id: str
    operation_name: str
    entity_ids: Tuple[str, ...]
    success: bool
    observed_state: Mapping[str, Any]
    error: str
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise ValueError("request_id must be a non-empty string")
        if not isinstance(self.operation_name, str) or not self.operation_name.strip():
            raise ValueError("operation_name must be a non-empty string")
        if not isinstance(self.entity_ids, tuple) or not self.entity_ids:
            raise ValueError("entity_ids must be a non-empty tuple of strings")
        for eid in self.entity_ids:
            if not isinstance(eid, str) or not eid.strip():
                raise ValueError("entity_ids must contain only non-empty strings")
        if not isinstance(self.success, bool):
            raise TypeError("success must be a boolean")
        if not isinstance(self.observed_state, Mapping):
            raise TypeError("observed_state must be a mapping")
        if not isinstance(self.error, str):
            raise TypeError("error must be a string")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a non-empty string")


# ---------------------------------------------------------------------------
# Correlation helper
# ---------------------------------------------------------------------------

def validate_response_correlation(
    request: UnrealTransportRequest,
    response: UnrealTransportResponse,
) -> UnrealTransportResponse:
    """Ensure a response correlates to its originating request.

    Raises ``ValueError`` on any mismatch so that Atlas never processes
    a stale or misrouted response.
    """
    if response.request_id != request.request_id:
        raise ValueError(
            "response request_id does not match the originating request"
        )
    if response.operation_name != request.operation_name:
        raise ValueError(
            "response operation_name does not match the originating request"
        )
    if tuple(response.entity_ids) != tuple(request.entity_ids):
        raise ValueError(
            "response entity_ids do not match the originating request"
        )
    return response
