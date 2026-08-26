"""Production completion bridge for the checkpointed autonomous runtime.

The autonomous runtime owns continuation integrity and execution. This bridge
owns only the production completion decision: runtime completion is promoted to
COMPLETED only after an independent authoritative verification callback accepts
its final snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from planning.autonomous_runtime import AutonomousFutureRuntime
from planning.production_operation_lifecycle import ProductionOperationState


@dataclass(frozen=True)
class ProductionRuntimeBridgeResult:
    state: ProductionOperationState
    snapshot: Dict[str, Any]
    reason: str

    @property
    def completed(self) -> bool:
        return self.state is ProductionOperationState.COMPLETED


class ProductionAutonomousRuntimeBridge:
    """Promote autonomous-runtime completion only after authoritative verification."""

    def __init__(
        self,
        runtime: AutonomousFutureRuntime,
        verify_final: Callable[[Dict[str, Any]], bool],
    ) -> None:
        if not isinstance(runtime, AutonomousFutureRuntime):
            raise TypeError("runtime must be an AutonomousFutureRuntime")
        if not callable(verify_final):
            raise TypeError("verify_final must be callable")
        self.runtime = runtime
        self.verify_final = verify_final
        self.state = ProductionOperationState.RUNNING

    def run(
        self,
        execute: Callable[[str, Dict[str, Any]], Dict[str, Any]],
        acknowledgements: Optional[Dict[str, Dict[str, Any]]] = None,
        verifications: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> ProductionRuntimeBridgeResult:
        snapshot = self.runtime.run_until_pause(execute, acknowledgements, verifications)
        if not snapshot.get("complete", False) or snapshot.get("blocked", False):
            self.state = ProductionOperationState.BLOCKED
            return ProductionRuntimeBridgeResult(
                self.state,
                snapshot,
                "autonomous runtime did not reach successful completion",
            )
        try:
            verified = bool(self.verify_final(snapshot))
        except Exception as exc:
            self.state = ProductionOperationState.BLOCKED
            return ProductionRuntimeBridgeResult(
                self.state,
                snapshot,
                f"authoritative verification failed: {exc}",
            )
        if not verified:
            self.state = ProductionOperationState.BLOCKED
            return ProductionRuntimeBridgeResult(
                self.state,
                snapshot,
                "authoritative verification rejected final runtime state",
            )
        self.state = ProductionOperationState.COMPLETED
        return ProductionRuntimeBridgeResult(
            self.state,
            snapshot,
            "authoritative verification accepted final runtime state",
        )
