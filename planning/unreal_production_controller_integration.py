"""Narrow controller-to-Unreal production capability adapter."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Protocol

from controller.capability_request import CapabilityRequest


class UnrealProductionExecution(Protocol):
    def __call__(self, request: CapabilityRequest) -> Dict[str, Any]:
        ...


class UnrealProductionControllerIntegration:
    """Validate the controller capability kind before delegating to an executor.

    This adapter owns no authorization and no scheduling. The host supplies
    already-trusted execution state; the underlying Unreal production boundary
    remains responsible for actual engine work and verification.
    """

    def __init__(self, execute: Optional[UnrealProductionExecution] = None):
        self._execute = execute

    def execute(self, request: CapabilityRequest) -> Dict[str, Any]:
        if not isinstance(request, CapabilityRequest):
            raise TypeError("request must be a CapabilityRequest")
        if request.normalized_provider != "unreal":
            raise ValueError("Unreal integration requires provider=unreal")
        if request.normalized_capability != "production":
            raise ValueError("Unreal production integration requires capability=production")
        if not self._execute:
            raise RuntimeError("Unreal production execution adapter is not configured")
        result = self._execute(request)
        if not isinstance(result, dict):
            raise TypeError("Unreal production executor must return an object")
        return result


__all__ = ["UnrealProductionControllerIntegration", "UnrealProductionExecution"]
