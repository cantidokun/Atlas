"""Immutable receipt binding a Blender request to its normalized result."""

from dataclasses import dataclass
import hashlib
import json
from collections.abc import Mapping
from typing import Any, Optional

from planning.blender_result_contract import BlenderExecutionResult


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _coerce_result(tool: str, result: Any) -> BlenderExecutionResult:
    """Preserve compatibility with legacy result-shaped test doubles.

    Production execution already supplies BlenderExecutionResult. Older tests and
    adapters may still expose the same result attributes without constructing the
    new value object; normalize those objects at the receipt boundary rather than
    weakening the receipt's stored contract.
    """
    if isinstance(result, BlenderExecutionResult):
        return result
    required = ("ok", "state", "details")
    if not all(hasattr(result, key) for key in required):
        raise TypeError("receipt result must be a BlenderExecutionResult")
    return BlenderExecutionResult(
        tool=tool,
        ok=result.ok,
        state=result.state,
        details=dict(result.details),
    )


def _normalize_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(arguments, Mapping):
        raise TypeError("receipt arguments must be an object")
    return dict(arguments)


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
        normalized_arguments = _normalize_arguments(arguments)
        normalized = _coerce_result(tool, result)
        if normalized.tool != tool:
            raise ValueError("receipt tool does not match result tool")
        return cls(tool, _digest(normalized_arguments), _digest({
            "tool": normalized.tool,
            "ok": normalized.ok,
            "state": normalized.state,
            "details": normalized.details,
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
        try:
            normalized_arguments = _normalize_arguments(arguments)
            normalized = _coerce_result(self.tool, result)
        except (TypeError, ValueError):
            return False
        if tool != self.tool or normalized.tool != self.tool:
            return False
        return (
            _digest(normalized_arguments) == self.arguments_digest
            and _digest({
                "tool": normalized.tool,
                "ok": normalized.ok,
                "state": normalized.state,
                "details": normalized.details,
            }) == self.result_digest
        )

    def matches_authorization(self, authorization_id: str) -> bool:
        if self.authorization_digest is None:
            return False
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            return False
        return _digest(authorization_id) == self.authorization_digest
