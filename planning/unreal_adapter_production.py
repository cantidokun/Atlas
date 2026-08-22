"""Production Unreal adapter with pluggable transport.

This adapter replaces the stub ``UnrealAdapterV01`` for real Unreal
communication.  It does **not** modify or import the v01 adapter.

Design invariants
-----------------
- The adapter never sets ``verified=True`` on evidence — Atlas verifies
  independently.
- Authorization IDs are transmitted, never issued, by this layer.
- The transport is pluggable via the ``UnrealTransport`` protocol so that
  tests can inject an in-memory implementation.
- Every response is correlated to its originating request before evidence is
  constructed.
- Semantic VERIFY operations may be fulfilled by a read-only transport
  observation when the process boundary does not expose a distinct VERIFY
  command. Atlas still records the evidence against the original VERIFY
  operation and performs semantic verification independently.
"""

import uuid
from typing import Any, Dict, Mapping, Optional, Protocol

from planning.unreal_agent import UnrealOperation, UnrealOperationKind, UnrealCapability
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_transport_contract import (
    UnrealTransportRequest,
    UnrealTransportResponse,
    validate_response_correlation,
)

# Import the production named pipe transport
try:
    from planning.unreal_transport_named_pipe import create_named_pipe_transport
    NAMED_PIPE_AVAILABLE = True
except ImportError:
    NAMED_PIPE_AVAILABLE = False


class UnrealTransport(Protocol):
    """Process-boundary transport between Atlas and the Unreal Editor."""

    def send(self, request: UnrealTransportRequest) -> UnrealTransportResponse:
        """Send a validated request and return a validated response."""
        ...  # pragma: no cover


class UnrealAdapterError(RuntimeError):
    """Raised when the adapter cannot complete an operation."""


class UnrealAdapterProduction:
    """Execute authorized Unreal operations via a pluggable transport.

    The adapter is stateless — each call is independent.  State tracking
    (plan progress, evidence ledger) belongs to the caller.
    """

    def __init__(self, transport: UnrealTransport, source_tag: str = "atlas-adapter") -> None:
        if not isinstance(source_tag, str) or not source_tag.strip():
            raise ValueError("source_tag must be a non-empty string")
        self._transport = transport
        self._source_tag = source_tag.strip()

    @staticmethod
    def _new_request_id() -> str:
        return f"req-{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _to_evidence(response: UnrealTransportResponse, operation_name: Optional[str] = None) -> UnrealEvidence:
        """Convert correlated transport response to engine-neutral evidence."""
        return UnrealEvidence(
            operation_name=operation_name or response.operation_name,
            entity_ids=response.entity_ids,
            observed_state=response.observed_state,
            source=response.source,
            verified=False,
        )

    def _build_request(
        self,
        operation: UnrealOperation,
        authorization_id: str,
    ) -> UnrealTransportRequest:
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise UnrealAdapterError("authorization_id is required for every transport request")
        return UnrealTransportRequest(
            request_id=self._new_request_id(),
            operation_name=operation.name,
            capability=operation.capability.value,
            kind=operation.kind.value,
            arguments=dict(operation.arguments),
            entity_ids=tuple(operation.entity_ids),
            authorization_id=authorization_id.strip(),
        )

    def _execute(
        self,
        operation: UnrealOperation,
        authorization_id: str,
        *,
        evidence_operation_name: Optional[str] = None,
    ) -> UnrealEvidence:
        request = self._build_request(operation, authorization_id)
        response = self._transport.send(request)
        validate_response_correlation(request, response)
        if not response.success:
            raise UnrealAdapterError(
                f"Unreal operation '{operation.name}' (kind={operation.kind.value}, "
                f"entity_ids={list(operation.entity_ids)}, auth_id={authorization_id}) "
                f"failed: {response.error}"
            )
        return self._to_evidence(response, evidence_operation_name)

    def inspect(
        self,
        operation: UnrealOperation,
        authorization_id: str,
    ) -> UnrealEvidence:
        """Execute a READ operation and return unverified evidence."""
        if operation.kind is not UnrealOperationKind.READ:
            raise UnrealAdapterError("inspect accepts READ operations only")
        return self._execute(operation, authorization_id)

    def apply_authorized(
        self,
        operation: UnrealOperation,
        authorization_id: str,
    ) -> UnrealEvidence:
        """Execute a WRITE operation and return unverified evidence."""
        if operation.kind is not UnrealOperationKind.WRITE:
            raise UnrealAdapterError("apply_authorized accepts WRITE operations only")
        return self._execute(operation, authorization_id)

    def verify(
        self,
        operation: UnrealOperation,
        authorization_id: str,
    ) -> UnrealEvidence:
        """Collect fresh read evidence for a semantic VERIFY operation.

        The current Unreal transport exposes actor inspection as a READ
        operation, not as a separate VERIFY wire command. The adapter maps
        ``verify_target_actor_mapping`` to that read-only observation while
        preserving the original semantic operation name in the evidence.
        Atlas's state verifier remains the authority that decides whether
        the observed state proves the requested mutation.
        """
        if operation.kind is not UnrealOperationKind.VERIFY:
            raise UnrealAdapterError("verify accepts VERIFY operations only")

        if operation.name == "verify_target_actor_mapping":
            transport_operation = UnrealOperation(
                capability=UnrealCapability.INSPECT_ACTOR,
                kind=UnrealOperationKind.READ,
                name="inspect_target_actors",
                arguments={"entity_ids": tuple(operation.entity_ids)},
                entity_ids=tuple(operation.entity_ids),
            )
            return self._execute(
                transport_operation,
                authorization_id,
                evidence_operation_name=operation.name,
            )

        return self._execute(operation, authorization_id)


def create_production_adapter(source_tag: str = "atlas-adapter-production") -> UnrealAdapterProduction:
    """Create a production adapter with Windows named pipe transport.

    Raises:
        RuntimeError: If named pipe transport is not available on this platform.
    """
    if not NAMED_PIPE_AVAILABLE:
        raise RuntimeError(
            "Named pipe transport not available. "
            "This requires Windows and the pywin32 package."
        )

    transport = create_named_pipe_transport()
    return UnrealAdapterProduction(transport, source_tag)
