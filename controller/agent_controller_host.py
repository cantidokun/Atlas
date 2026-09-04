"""Host-side classifier that safely routes model capability requests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from controller.capability_request import CapabilityRequest, CapabilityRequestError
from controller.trusted_unreal_context import TrustedUnrealContext


REQUEST_PREFIX = "ATLAS_CONTROLLER_REQUEST:"


class AgentControllerHostError(ValueError):
    """Raised when a model response cannot cross the host capability boundary."""


@dataclass(frozen=True)
class ClassifiedControllerRequest:
    request: CapabilityRequest


@dataclass(frozen=True)
class ControllerHostResult:
    classified: ClassifiedControllerRequest
    controller_executed: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class _ExecutionContext:
    def __init__(self) -> None:
        self._contexts: Dict[str, TrustedUnrealContext] = {}

    def set_unreal_production(self, context: TrustedUnrealContext) -> None:
        self._contexts["unreal:production"] = context

    def get_unreal_production(self) -> TrustedUnrealContext:
        context = self._contexts.get("unreal:production")
        if context is None:
            raise AgentControllerHostError("trusted Unreal production context is unavailable")
        return context


class _HostRuntime:
    def __init__(self) -> None:
        self.execution_context = _ExecutionContext()


class AgentControllerHost:
    """Keep model text separate from host-owned execution context."""

    def __init__(self, runtime: Optional[_HostRuntime] = None) -> None:
        self.runtime = runtime or _HostRuntime()
        if not hasattr(self.runtime, "execution_context"):
            raise TypeError("runtime must expose execution_context")

    @classmethod
    def for_unreal_production(
        cls,
        integration: Any,
        trusted_context: TrustedUnrealContext,
    ) -> "AgentControllerHost":
        if not isinstance(trusted_context, TrustedUnrealContext):
            raise TypeError("trusted_context must be TrustedUnrealContext")
        host = cls()
        host._unreal_integration = integration
        host.runtime.execution_context.set_unreal_production(trusted_context)
        return host

    @staticmethod
    def _decode(response: str) -> Dict[str, Any]:
        if not isinstance(response, str) or not response.strip():
            raise AgentControllerHostError("model response must be a non-empty string")
        if not response.startswith(REQUEST_PREFIX):
            raise AgentControllerHostError("model response is not a controller request")
        raw = response[len(REQUEST_PREFIX):].strip()
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AgentControllerHostError("controller request JSON is invalid") from exc
        if not isinstance(decoded, dict):
            raise AgentControllerHostError("controller request must decode to an object")
        allowed = {"capability", "provider", "intent", "context"}
        if set(decoded) - allowed:
            raise AgentControllerHostError("controller request contains unsupported fields")
        return decoded

    def _classify(self, payload: Dict[str, Any]) -> ClassifiedControllerRequest:
        capability = payload.get("capability")
        provider = payload.get("provider")
        intent = payload.get("intent")
        model_context = payload.get("context", {})
        if not isinstance(model_context, dict):
            raise AgentControllerHostError("controller request context must be an object")
        if str(provider).lower() == "unreal" and str(capability).lower() == "production":
            trusted = self.runtime.execution_context.get_unreal_production()
            # Only the harmless marker is retained from the model context. All
            # security-sensitive values come from host-owned trusted state.
            context = trusted.capability_context()
            context["production"] = bool(model_context.get("production", True))
        else:
            context = dict(model_context)
        try:
            request = CapabilityRequest(capability, provider, intent, context)
        except (CapabilityRequestError, TypeError) as exc:
            raise AgentControllerHostError(str(exc)) from exc
        return ClassifiedControllerRequest(request)

    def process_model_response(self, response: str) -> Optional[ControllerHostResult]:
        if not isinstance(response, str) or not response.startswith(REQUEST_PREFIX):
            return None
        try:
            classified = self._classify(self._decode(response))
            if classified.request.normalized_provider == "unreal" and classified.request.normalized_capability == "production":
                integration = getattr(self, "_unreal_integration", None)
                if integration is None:
                    raise AgentControllerHostError("Unreal production integration is not configured")
                result = integration.execute(classified.request)
                return ControllerHostResult(classified, True, result=result)
            raise AgentControllerHostError("unsupported controller capability")
        except Exception as exc:
            return ControllerHostResult(
                classified=ClassifiedControllerRequest(
                    CapabilityRequest("unknown", "unknown", "rejected", {})
                ),
                controller_executed=False,
                error=str(exc),
            )


__all__ = [
    "AgentControllerHost",
    "AgentControllerHostError",
    "ClassifiedControllerRequest",
    "ControllerHostResult",
]
