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
    authorization_digest: Optional[str] = None

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

    @classmethod
    def create_authorized(
        cls,
        tool: str,
        arguments: Mapping[str, Any],
        result: BlenderExecutionResult,
        authorization_id: str,
    ):
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise ValueError("authorization_id must be a non-empty string")
        receipt = cls.create(tool, arguments, result)
        return cls(
            receipt.tool,
            receipt.arguments_digest,
            receipt.result_digest,
            _digest(authorization_id),
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

    def matches_authorization(self, authorization_id: str) -> bool:
        if self.authorization_digest is None:
            return False
        return _digest(authorization_id) == self.authorization_digest
