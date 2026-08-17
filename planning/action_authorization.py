"""Immutable authorization receipts for generic Atlas action plans."""
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict, List

from planning.action_plan import ActionSpec


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _action_payload(action: ActionSpec) -> Dict[str, Any]:
    return {
        "tool": action.tool,
        "arguments": dict(action.arguments),
        "name": action.name,
        "requires_success": action.requires_success,
    }


@dataclass(frozen=True)
class ActionAuthorization:
    """Immutable proof that a specific action plan was explicitly authorized."""

    plan_digest: str
    authorization_id: str

    @classmethod
    def issue(cls, actions: List[ActionSpec], authorization_id: str) -> "ActionAuthorization":
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise ValueError("authorization_id must be a non-empty string.")
        if not isinstance(actions, list) or any(not isinstance(action, ActionSpec) for action in actions):
            raise TypeError("actions must be a list of ActionSpec objects.")
        digest = hashlib.sha256(
            _canonical([_action_payload(action) for action in actions]).encode("utf-8")
        ).hexdigest()
        return cls(digest, authorization_id.strip())

    def matches(self, actions: List[ActionSpec]) -> bool:
        if not isinstance(actions, list) or any(not isinstance(action, ActionSpec) for action in actions):
            return False
        digest = hashlib.sha256(
            _canonical([_action_payload(action) for action in actions]).encode("utf-8")
        ).hexdigest()
        return self.plan_digest == digest

    def snapshot(self) -> Dict[str, str]:
        return {
            "plan_digest": self.plan_digest,
            "authorization_id": self.authorization_id,
        }
