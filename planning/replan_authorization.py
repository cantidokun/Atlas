"""Explicit authorization receipts for deterministic recovery replans."""
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict, List

from action_plan import ActionSpec

_SHA256_HEX_LENGTH = 64


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _action_payload(action: ActionSpec) -> Dict[str, Any]:
    return {
        "tool": action.tool,
        "arguments": dict(action.arguments),
        "name": action.name,
        "requires_success": action.requires_success,
    }


def _validate_digest(name: str, value: str) -> None:
    if not isinstance(value, str) or len(value) != _SHA256_HEX_LENGTH:
        raise ValueError(f"{name} must be a SHA-256 hex digest.")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{name} must be a SHA-256 hex digest.") from exc


@dataclass(frozen=True)
class ReplanAuthorization:
    """Immutable proof that a replacement action list crossed authorization."""

    evidence_digest: str
    actions_digest: str
    authorization_id: str

    def __post_init__(self) -> None:
        _validate_digest("evidence_digest", self.evidence_digest)
        _validate_digest("actions_digest", self.actions_digest)
        if not isinstance(self.authorization_id, str) or not self.authorization_id.strip():
            raise ValueError("authorization_id must be a non-empty string.")

    @classmethod
    def issue(cls, evidence: Any, actions: List[ActionSpec], authorization_id: str) -> "ReplanAuthorization":
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise ValueError("authorization_id must be a non-empty string.")
        if not isinstance(actions, list) or any(not isinstance(action, ActionSpec) for action in actions):
            raise TypeError("actions must be a list of ActionSpec objects.")
        evidence_digest = hashlib.sha256(_canonical(evidence).encode("utf-8")).hexdigest()
        actions_digest = hashlib.sha256(
            _canonical([_action_payload(action) for action in actions]).encode("utf-8")
        ).hexdigest()
        return cls(evidence_digest, actions_digest, authorization_id.strip())

    def matches(self, evidence: Any, actions: List[ActionSpec]) -> bool:
        if not isinstance(actions, list) or any(not isinstance(action, ActionSpec) for action in actions):
            return False
        return (
            self.evidence_digest == hashlib.sha256(_canonical(evidence).encode("utf-8")).hexdigest()
            and self.actions_digest
            == hashlib.sha256(_canonical([_action_payload(action) for action in actions]).encode("utf-8")).hexdigest()
        )

    def snapshot(self) -> Dict[str, str]:
        return {
            "evidence_digest": self.evidence_digest,
            "actions_digest": self.actions_digest,
            "authorization_id": self.authorization_id,
        }
