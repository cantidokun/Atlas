"""Narrow controller-to-Unreal production capability adapter.

This adapter owns no authorization and no scheduling. The host supplies
already-trusted execution state; the underlying Unreal production boundary
remains responsible for actual engine work and verification.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol

from controller.capability_request import CapabilityRequest


REQUIRED_TRUSTED_CONTEXT_KEYS = {
    "production",
    "authorized_production",
    "intent",
    "sequence_asset_path",
}


class UnrealProductionExecution(Protocol):
    def __call__(self, request: CapabilityRequest) -> Dict[str, Any]:
        ...


class UnrealProductionControllerIntegration:
    """Validate controller capability and trusted execution context."""

    def __init__(self, execute: Optional[UnrealProductionExecution] = None):
        self._execute = execute

    @staticmethod
    def _validate_trusted_context(request: CapabilityRequest) -> None:
        context = request.context
        if context.get("production") is not True:
            raise ValueError(
                "Unreal production request requires trusted production context"
            )

        missing = REQUIRED_TRUSTED_CONTEXT_KEYS.difference(context)
        if missing:
            raise ValueError(
                "Unreal production request is missing trusted context: "
                + ", ".join(sorted(missing))
            )

        if context.get("authorized_production") is None:
            raise ValueError(
                "Unreal production request requires trusted authorization context"
            )

        intent = context.get("intent")
        if not isinstance(intent, str) or not intent.strip():
            raise ValueError("Unreal production request requires trusted intent")

        sequence_asset_path = context.get("sequence_asset_path")
        if not isinstance(sequence_asset_path, str) or not sequence_asset_path.strip():
            raise ValueError(
                "Unreal production request requires trusted sequence_asset_path"
            )

    def execute(self, request: CapabilityRequest) -> Dict[str, Any]:
        if not isinstance(request, CapabilityRequest):
            raise TypeError("request must be a CapabilityRequest")
        if request.normalized_provider != "unreal":
            raise ValueError("Unreal integration requires provider=unreal")
        if request.normalized_capability != "production":
            raise ValueError(
                "Unreal production integration requires capability=production"
            )
        self._validate_trusted_context(request)
        if not self._execute:
            raise RuntimeError("Unreal production execution adapter is not configured")

        result = self._execute(request)
        if not isinstance(result, dict):
            raise TypeError("Unreal production executor must return an object")
        return result


__all__ = [
    "REQUIRED_TRUSTED_CONTEXT_KEYS",
    "UnrealProductionControllerIntegration",
    "UnrealProductionExecution",
]
