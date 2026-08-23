"""Production Unreal adapter with pluggable transport.

This adapter replaces the stub ``UnrealAdapterV01`` for real Unreal
communication. It does not own authorization or verification.
"""

import uuid
from typing import Any, Mapping, Optional, Protocol

from planning.unreal_agent import UnrealOperation, UnrealOperationKind, UnrealCapability
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_transport_contract import UnrealTransportRequest, UnrealTransportResponse, validate_response_correlation
from planning.unreal_transport_named_pipe import NamedPipeTransportError

try:
    from planning.unreal_transport_named_pipe import create_named_pipe_transport
    NAMED_PIPE_AVAILABLE = True
except ImportError:
    NAMED_PIPE_AVAILABLE = False


class UnrealTransport(Protocol):
    def send(self, request: UnrealTransportRequest) -> UnrealTransportResponse:
        ...


class UnrealAdapterError(RuntimeError):
    """Raised when the adapter cannot complete an operation."""


class UnrealAdapterProduction:
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
        return UnrealEvidence(
            operation_name=operation_name or response.operation_name,
            entity_ids=response.entity_ids,
            observed_state=response.observed_state,
            source=response.source,
            verified=False,
        )

    def _build_request(self, operation: UnrealOperation, authorization_id: str) -> UnrealTransportRequest:
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

    def _execute(self, operation: UnrealOperation, authorization_id: str, *, evidence_operation_name: Optional[str] = None) -> UnrealEvidence:
        request = self._build_request(operation, authorization_id)
        try:
            response = self._transport.send(request)
        except NamedPipeTransportError as exc:
            raise UnrealAdapterError(
                f"Unreal transport failed for operation '{operation.name}' "
                f"(kind={operation.kind.value}, entity_ids={list(operation.entity_ids)}): {exc}"
            ) from exc
        validate_response_correlation(request, response)
        if not response.success:
            raise UnrealAdapterError(
                f"Unreal operation '{operation.name}' (kind={operation.kind.value}, "
                f"entity_ids={list(operation.entity_ids)}, auth_id={authorization_id}) failed: {response.error}"
            )
        return self._to_evidence(response, evidence_operation_name)

    def inspect(self, operation: UnrealOperation, authorization_id: str) -> UnrealEvidence:
        if operation.kind is not UnrealOperationKind.READ:
            raise UnrealAdapterError("inspect accepts READ operations only")
        return self._execute(operation, authorization_id)

    def apply_authorized(self, operation: UnrealOperation, authorization_id: str) -> UnrealEvidence:
        if operation.kind is not UnrealOperationKind.WRITE:
            raise UnrealAdapterError("apply_authorized accepts WRITE operations only")
        return self._execute(operation, authorization_id)

    def verify(self, operation: UnrealOperation, authorization_id: str) -> UnrealEvidence:
        if operation.kind is not UnrealOperationKind.VERIFY:
            raise UnrealAdapterError("verify accepts VERIFY operations only")

        read_mapping = {
            "verify_target_actor_mapping": (UnrealCapability.INSPECT_ACTOR, "inspect_target_actors"),
            "verify_material_variant": (UnrealCapability.MATERIAL, "inspect_material_state"),
            "verify_niagara_variant": (UnrealCapability.NIAGARA, "inspect_niagara_state"),
        }
        if operation.name in read_mapping:
            capability, operation_name = read_mapping[operation.name]
            transport_operation = UnrealOperation(
                capability=capability,
                kind=UnrealOperationKind.READ,
                name=operation_name,
                arguments={"entity_ids": tuple(operation.entity_ids)},
                entity_ids=tuple(operation.entity_ids),
            )
            return self._execute(transport_operation, authorization_id, evidence_operation_name=operation.name)

        return self._execute(operation, authorization_id)


def create_production_adapter(source_tag: str = "atlas-adapter-production") -> UnrealAdapterProduction:
    if not NAMED_PIPE_AVAILABLE:
        raise RuntimeError("Named pipe transport not available. This requires Windows and the pywin32 package.")
    transport = create_named_pipe_transport()
    return UnrealAdapterProduction(transport, source_tag)
