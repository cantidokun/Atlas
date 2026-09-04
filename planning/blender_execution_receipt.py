"""Immutable receipt binding a Blender request to its normalized result."""

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Optional

from planning.blender_result_contract import BlenderExecutionResult


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BlenderExecutionReceipt:
    tool: str
    arguments_digest: str
    result_digest: str

    @classmethod
    def create(cls, tool: str, arguments: Mapping[str, Any], result: BlenderExecutionResult):
        if not isinstance(tool, str) or not tool.strip():
            raise ValueError("receipt tool must be a non-empty string")
        if not isinstance(arguments, dict):
            raise TypeError("receipt arguments must be an object")
        if not isinstance(result, BlenderExecutionResult):
            raise TypeError("receipt result must be a BlenderExecutionResult")
        if result.tool != tool:
            raise ValueError("receipt tool does not match result tool")
        return cls(tool, _digest(arguments), _digest({
            "tool": result.tool,
            "ok": result.ok,
            "state": result.state,
            "details": result.details,
        }))

    def snapshot(self) -> dict:
        """Return the complete persisted receipt contract without derived data."""
        return {
            "tool": self.tool,
            "arguments_digest": self.arguments_digest,
            "result_digest": self.result_digest,
        }

    def digest(self) -> str:
        """Return the deterministic integrity digest for this receipt."""
        return _digest(self.snapshot())

    def verify_integrity(self, expected_digest: Optional[str] = None) -> None:
        """Fail closed when an expected digest does not match this receipt."""
        if expected_digest is not None:
            if not isinstance(expected_digest, str) or not expected_digest.strip():
                raise ValueError("expected_digest must be a non-empty string")
            if self.digest() != expected_digest:
                raise ValueError("Blender execution receipt integrity check failed")

    @classmethod
    def from_snapshot(cls, snapshot: Any) -> "BlenderExecutionReceipt":
        """Reconstruct a receipt and reject unknown or malformed persisted fields."""
        if not isinstance(snapshot, dict):
            raise ValueError("Blender execution receipt snapshot must be a dictionary")
        required = {"tool", "arguments_digest", "result_digest"}
        if set(snapshot) != required:
            raise ValueError("Blender execution receipt fields are invalid")
        values = {field: snapshot[field] for field in required}
        for field, value in values.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string")
        return cls(
            tool=values["tool"],
            arguments_digest=values["arguments_digest"],
            result_digest=values["result_digest"],
        )

    def matches(self, tool: str, arguments: Mapping[str, Any], result: BlenderExecutionResult) -> bool:
        if not isinstance(result, BlenderExecutionResult):
            return False
        if tool != self.tool or result.tool != self.tool:
            return False
        return (
            _digest(arguments) == self.arguments_digest
            and _digest({
                "tool": result.tool,
                "ok": result.ok,
                "state": result.state,
                "details": result.details,
            }) == self.result_digest
        )
