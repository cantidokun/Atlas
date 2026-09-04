"""Safe Blender executor boundary used by the planning agent."""
from dataclasses import dataclass
from typing import Any, Callable, Dict, Protocol

from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_persistence_evidence import BlenderPersistenceEvidence, verify_blender_persistence
from planning.blender_result_contract import BlenderExecutionResult, normalize_blender_result
from planning.blender_tool_schema import validate_blender_tool_call
from planning.blender_verification import verify_blender_execution


class BlenderExecutor(Protocol):
    def __call__(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]: ...


@dataclass(frozen=True)
class BlenderClosedLoopResult:
    """Complete result of one write followed by independent persistence verification."""

    operation_result: BlenderExecutionResult
    operation_receipt: BlenderExecutionReceipt
    inspection_result: BlenderExecutionResult
    persistence_evidence: BlenderPersistenceEvidence


class BlenderExecutionBoundary:
    """Validate, execute, verify, and optionally receipt-bind Blender calls."""

    def __init__(self, executor: BlenderExecutor):
        self._executor = executor

    def execute(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Backward-compatible execution API returning the raw adapter object."""
        validated = validate_blender_tool_call(tool, arguments)
        result = self._executor(tool, validated)
        if not isinstance(result, dict):
            raise TypeError("Blender executor must return an object")
        return result

    def execute_verified(self, tool: str, arguments: Dict[str, Any]) -> BlenderExecutionResult:
        """Execute and require a successful result for the requested Blender tool."""
        validated = validate_blender_tool_call(tool, arguments)
        result = self._executor(tool, validated)
        normalized = normalize_blender_result(tool, result)
        return verify_blender_execution(normalized, tool)

    def execute_with_receipt(self, tool: str, arguments: Dict[str, Any]):
        """Execute successfully and return the verified result plus an immutable receipt."""
        validated = validate_blender_tool_call(tool, arguments)
        result = self._executor(tool, validated)
        normalized = verify_blender_execution(normalize_blender_result(tool, result), tool)
        receipt = BlenderExecutionReceipt.create(tool, validated, normalized)
        return normalized, receipt

    def execute_with_persistence(
        self,
        operation_tool: str,
        operation_arguments: Dict[str, Any],
        inspection_tool: str,
        inspection_arguments: Dict[str, Any],
        expected_state: Any,
        observed_state: Callable[[BlenderExecutionResult], Any],
    ) -> BlenderClosedLoopResult:
        """Execute one write and require fresh inspection evidence before returning success.

        This method intentionally owns no authorization policy. The caller must establish
        authorization before invoking it; this boundary only performs validated execution,
        independent inspection, and fail-closed persistence verification.
        """
        operation_result, operation_receipt = self.execute_with_receipt(
            operation_tool, operation_arguments
        )
        if not operation_receipt.matches(
            operation_tool, operation_arguments, operation_result
        ):
            raise RuntimeError("Blender execution receipt did not match the request/result")

        inspection_result = self.execute_verified(inspection_tool, inspection_arguments)
        actual_state = observed_state(inspection_result)
        persistence_evidence = verify_blender_persistence(
            operation_tool,
            operation_arguments,
            inspection_tool,
            expected_state,
            actual_state,
            inspection_result,
        )
        return BlenderClosedLoopResult(
            operation_result=operation_result,
            operation_receipt=operation_receipt,
            inspection_result=inspection_result,
            persistence_evidence=persistence_evidence,
        )
