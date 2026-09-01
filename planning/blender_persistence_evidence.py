"""Immutable evidence binding a Blender mutation to fresh persisted state."""

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from planning.blender_result_contract import BlenderExecutionResult


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BlenderPersistenceEvidence:
    """Evidence produced by an independent inspection after a Blender write."""

    operation_tool: str
    operation_arguments_digest: str
    inspection_tool: str
    expected_state_digest: str
    observed_state_digest: str

    @classmethod
    def create(
        cls,
        operation_tool: str,
        operation_arguments: Mapping[str, Any],
        inspection_tool: str,
        expected_state: Any,
        inspection_result: BlenderExecutionResult,
    ) -> "BlenderPersistenceEvidence":
        if not isinstance(operation_tool, str) or not operation_tool.strip():
            raise ValueError("operation tool must be a non-empty string")
        if not isinstance(operation_arguments, dict):
            raise TypeError("operation arguments must be an object")
        if not isinstance(inspection_tool, str) or not inspection_tool.strip():
            raise ValueError("inspection tool must be a non-empty string")
        if not isinstance(inspection_result, BlenderExecutionResult):
            raise TypeError("inspection result must be a BlenderExecutionResult")
        if inspection_result.tool != inspection_tool:
            raise ValueError("inspection tool does not match inspection result")
        if not inspection_result.ok:
            raise ValueError("persistence evidence requires a successful inspection")

        return cls(
            operation_tool=operation_tool,
            operation_arguments_digest=_digest(operation_arguments),
            inspection_tool=inspection_tool,
            expected_state_digest=_digest(expected_state),
            observed_state_digest=_digest(inspection_result.details),
        )

    def matches(
        self,
        operation_tool: str,
        operation_arguments: Mapping[str, Any],
        expected_state: Any,
        inspection_result: BlenderExecutionResult,
    ) -> bool:
        if not isinstance(inspection_result, BlenderExecutionResult):
            return False
        if inspection_result.tool != self.inspection_tool or not inspection_result.ok:
            return False
        return (
            operation_tool == self.operation_tool
            and _digest(operation_arguments) == self.operation_arguments_digest
            and _digest(expected_state) == self.expected_state_digest
            and _digest(inspection_result.details) == self.observed_state_digest
        )
