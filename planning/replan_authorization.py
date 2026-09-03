"""Explicit authorization receipts for deterministic recovery replans."""
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict, List

from action_plan import ActionSpec
from planning.action_dependencies import validate_action_dependencies


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _action_payload(action: ActionSpec) -> Dict[str, Any]:
    return {
        "tool": action.tool,
        "arguments": dict(action.arguments),
        "name": action.name,
        "requires_success": action.requires_success,
        "depends_on": list(action.dependency_names()),
    }


@dataclass(frozen=True)
class ReplanAuthorization:
    """Immutable proof that a replacement action list crossed authorization."""

    evidence_digest: str
    actions_digest: str
    authorization_id: str

    @classmethod
    def issue(cls, evidence: Any, actions: List[ActionSpec], authorization_id: str) -> "ReplanAuthorization":
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise ValueError("authorization_id must be a non-empty string.")
        if not isinstance(actions, list) or any(not isinstance(action, ActionSpec) for action in actions):
            raise TypeError("actions must be a list of ActionSpec objects.")
        validate_action_dependencies(actions)
        evidence_digest = hashlib.sha256(_canonical(evidence).encode("utf-8")).hexdigest()
        actions_digest = hashlib.sha256(
            _canonical([_action_payload(action) for action in actions]).encode("utf-8")
        ).hexdigest()
        return cls(evidence_digest, actions_digest, authorization_id.strip())

    def matches(self, evidence: Any, actions: List[ActionSpec]) -> bool:
        if not isinstance(actions, list) or any(not isinstance(action, ActionSpec) for action in actions):
            return False
        try:
            validate_action_dependencies(actions)
        except (TypeError, ValueError):
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
