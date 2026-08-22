"""Tool executor that connects autonomous runtime steps to Blender safely.

The autonomous runtime deliberately accepts a generic callable so it can be
used with simulations and other adapters. This module supplies the production
Blender implementation: every call crosses the Blender execution boundary,
is normalized and verified, and receives an immutable execution receipt.
"""

from typing import Any, Dict, Optional

from planning.blender_execution_boundary import BlenderExecutionBoundary, BlenderExecutor
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_result_contract import BlenderExecutionResult
from planning.blender_tool_adapter import BlenderToolAdapter


class BlenderAutonomousExecutor:
    """Adapt the verified Blender boundary to the autonomous ToolExecutor API."""

    def __init__(self, executor: Optional[BlenderExecutor] = None):
        # A caller may inject a deterministic executor for tests/simulations.
        # Production construction defaults to the explicit concrete capability
        # adapter; authorization and verification remain outside that adapter.
        self._adapter = executor if executor is not None else BlenderToolAdapter()
        self._boundary = BlenderExecutionBoundary(self._adapter)
        self._last_result: Optional[BlenderExecutionResult] = None
        self._last_receipt: Optional[BlenderExecutionReceipt] = None

    @property
    def last_result(self) -> Optional[BlenderExecutionResult]:
        return self._last_result

    @property
    def last_receipt(self) -> Optional[BlenderExecutionReceipt]:
        return self._last_receipt

    def __call__(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute one autonomous action through validation and verification."""
        normalized, receipt = self._boundary.execute_with_receipt(tool, arguments)
        self._last_result = normalized
        self._last_receipt = receipt
        return {
            "ok": normalized.ok,
            "state": normalized.state,
            "details": dict(normalized.details),
        }

    def receipt_matches_last_execution(
        self,
        tool: str,
        arguments: Dict[str, Any],
    ) -> bool:
        """Confirm the retained receipt still binds the supplied request."""
        if self._last_result is None or self._last_receipt is None:
            return False
        return self._last_receipt.matches(tool, arguments, self._last_result)
