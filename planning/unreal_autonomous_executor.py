"""Tool executor connecting generic autonomous runtime steps to Unreal safely.

The autonomous runtime accepts a generic ToolExecutor callable:
    (tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]

This module adapts the verified Unreal execution boundary to that API.
Every call crosses UnrealExecutionBoundary, maps to an UnrealOperation,
is executed via UnrealAdapterProduction, and retains the resulting UnrealEvidence.
"""

from typing import Any, Dict, Optional

from planning.unreal_adapter_production import UnrealAdapterError, UnrealExecutor
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_execution_boundary import UnrealExecutionBoundary


class UnrealAutonomousExecutor:
    """Adapt the verified Unreal boundary to the generic ToolExecutor API."""

    def __init__(
        self,
        executor_or_adapter: UnrealExecutor,
        *,
        default_authorization_id: Optional[str] = None,
    ) -> None:
        if isinstance(executor_or_adapter, UnrealExecutionBoundary):
            self._boundary = executor_or_adapter
        else:
            self._boundary = UnrealExecutionBoundary(executor_or_adapter)

        self._default_authorization_id = default_authorization_id
        self._last_evidence: Optional[UnrealEvidence] = None

    @property
    def last_evidence(self) -> Optional[UnrealEvidence]:
        """Return the unverified evidence produced by the last execution."""
        return self._last_evidence

    def __call__(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute one autonomous action through Unreal validation and transport."""
        args = dict(arguments)
        if "authorization_id" not in args and self._default_authorization_id is not None:
            args["authorization_id"] = self._default_authorization_id

        try:
            evidence = self._boundary.execute(tool, args)
            self._last_evidence = evidence
            # Use detached JSON snapshot for observed_state so results are JSON serializable
            snapshot = evidence.snapshot()
            return {
                "ok": True,
                "state": "executed",
                "details": {
                    "operation_name": snapshot["operation_name"],
                    "entity_ids": snapshot["entity_ids"],
                    "observed_state": snapshot["observed_state"],
                    "verified": snapshot["verified"],
                    "source": snapshot["source"],
                },
            }
        except (UnrealAdapterError, ValueError, TypeError) as exc:
            self._last_evidence = None
            return {
                "ok": False,
                "error": str(exc),
                "exception_type": type(exc).__name__,
            }
