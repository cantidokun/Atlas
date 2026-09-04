"""Immutable evidence binding a Blender mutation to fresh persisted state."""

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Optional

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
        observed_state: Any,
        inspection_result: BlenderExecutionResult,
    ) -> "BlenderPersistenceEvidence":
        if not isinstance(operation_tool, str) or not operation_tool.strip():
            raise ValueError("operation tool must be a non-empty string")
        if not isinstance(operation_arguments, dict):
            raise TypeError("operation arguments must be an object")
        if not isinstance(inspection_tool, str) or not inspection_tool.strip():
            raise ValueError("inspection tool must be a non-empty string")
        if not isinstance(inspection_result, BlenderExecutionResult):
            raise TypeError("persistence evidence requires a BlenderExecutionResult")
        if inspection_result.tool != inspection_tool:
            raise ValueError("inspection tool does not match inspection result")
        if not inspection_result.ok:
            raise ValueError("persistence evidence requires a successful inspection")
        if expected_state != observed_state:
            raise ValueError("persistence evidence requires expected and observed state to match")

        return cls(
            operation_tool=operation_tool,
            operation_arguments_digest=_digest(operation_arguments),
            inspection_tool=inspection_tool,
            expected_state_digest=_digest(expected_state),
            observed_state_digest=_digest(observed_state),
        )

    def matches(
        self,
        operation_tool: str,
        operation_arguments: Mapping[str, Any],
        expected_state: Any,
        observed_state: Any,
        inspection_result: BlenderExecutionResult,
    ) -> bool:
        if not isinstance(inspection_result, BlenderExecutionResult):
            return False
        if inspection_result.tool != self.inspection_tool or not inspection_result.ok:
            return False
        if expected_state != observed_state:
            return False
        return (
            operation_tool == self.operation_tool
            and _digest(operation_arguments) == self.operation_arguments_digest
            and _digest(expected_state) == self.expected_state_digest
            and _digest(observed_state) == self.observed_state_digest
        )

    def snapshot(self) -> dict[str, Any]:
        """Return the complete persisted evidence contract without derived data."""
        return {
            "operation_tool": self.operation_tool,
            "operation_arguments_digest": self.operation_arguments_digest,
            "inspection_tool": self.inspection_tool,
            "expected_state_digest": self.expected_state_digest,
            "observed_state_digest": self.observed_state_digest,
        }

    def digest(self) -> str:
        """Return the deterministic integrity digest for this evidence record."""
        return _digest(self.snapshot())

    def verify_integrity(self, expected_digest: Optional[str] = None) -> None:
        """Fail closed when an expected digest does not match this evidence record."""
        if expected_digest is not None:
            if not isinstance(expected_digest, str) or not expected_digest.strip():
                raise ValueError("expected_digest must be a non-empty string")
            if self.digest() != expected_digest:
                raise ValueError("Blender persistence evidence integrity check failed")

    @classmethod
    def from_snapshot(cls, snapshot: Any) -> "BlenderPersistenceEvidence":
        """Reconstruct evidence and reject unknown or malformed persisted fields."""
        if not isinstance(snapshot, dict):
            raise ValueError("Blender persistence evidence snapshot must be a dictionary")
        required = {
            "operation_tool",
            "operation_arguments_digest",
            "inspection_tool",
            "expected_state_digest",
            "observed_state_digest",
        }
        if set(snapshot) != required:
            raise ValueError("Blender persistence evidence fields are invalid")
        values = {
            "operation_tool": snapshot["operation_tool"],
            "operation_arguments_digest": snapshot["operation_arguments_digest"],
            "inspection_tool": snapshot["inspection_tool"],
            "expected_state_digest": snapshot["expected_state_digest"],
            "observed_state_digest": snapshot["observed_state_digest"],
        }
        for field, value in values.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string")
        if values["expected_state_digest"] != values["observed_state_digest"]:
            raise ValueError("Blender persistence evidence state digests must match")
        return cls(**values)


def verify_blender_persistence(
    operation_tool: str,
    operation_arguments: Mapping[str, Any],
    inspection_tool: str,
    expected_state: Any,
    observed_state: Any,
    inspection_result: BlenderExecutionResult,
) -> BlenderPersistenceEvidence:
    """Create and validate persistence evidence for an independently inspected write."""
    evidence = BlenderPersistenceEvidence.create(
        operation_tool,
        operation_arguments,
        inspection_tool,
        expected_state,
        observed_state,
        inspection_result,
    )
    if not evidence.matches(
        operation_tool,
        operation_arguments,
        expected_state,
        observed_state,
        inspection_result,
    ):
        raise RuntimeError("Blender persistence evidence failed closed validation")
    return evidence
