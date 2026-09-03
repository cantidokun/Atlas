"""Explicit authorization receipts for deterministic recovery replans."""
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict, Iterable, List, Tuple

from action_plan import ActionSpec
from planning.action_dependencies import validate_action_dependencies


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _normalize_inherited_dependencies(names: Iterable[str]) -> Tuple[str, ...]:
    normalized = tuple(sorted({str(name).strip() for name in names if str(name).strip()}))
    return normalized


def _action_payload(action: ActionSpec) -> Dict[str, Any]:
    return {
        "tool": action.tool,
        "arguments": dict(action.arguments),
        "name": action.name,
        "requires_success": action.requires_success,
        "depends_on": list(action.dependency_names()),
    }


def _actions_digest(actions: List[ActionSpec], inherited_dependencies: Iterable[str] = ()) -> str:
    payload = {
        "actions": [_action_payload(action) for action in actions],
        "inherited_dependencies": list(_normalize_inherited_dependencies(inherited_dependencies)),
    }
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReplanAuthorization:
    """Immutable proof that a replacement action list crossed authorization.

    The receipt binds both replacement actions and any inherited prerequisites
    proven complete by the blocked continuation. This prevents a replacement
    plan from silently changing which prior work it is allowed to rely upon.
    """

    evidence_digest: str
    actions_digest: str
    authorization_id: str

    @classmethod
    def issue(
        cls,
        evidence: Any,
        actions: List[ActionSpec],
        authorization_id: str,
        *,
        inherited_dependencies: Iterable[str] = (),
    ) -> "ReplanAuthorization":
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise ValueError("authorization_id must be a non-empty string.")
        if not isinstance(actions, list) or any(not isinstance(action, ActionSpec) for action in actions):
            raise TypeError("actions must be a list of ActionSpec objects.")
        inherited = _normalize_inherited_dependencies(inherited_dependencies)
        validate_action_dependencies(actions, satisfied_dependencies=inherited)
        evidence_digest = hashlib.sha256(_canonical(evidence).encode("utf-8")).hexdigest()
        return cls(evidence_digest, _actions_digest(actions, inherited), authorization_id.strip())

    def matches(
        self,
        evidence: Any,
        actions: List[ActionSpec],
        *,
        inherited_dependencies: Iterable[str] = (),
    ) -> bool:
        if not isinstance(actions, list) or any(not isinstance(action, ActionSpec) for action in actions):
            return False
        try:
            inherited = _normalize_inherited_dependencies(inherited_dependencies)
            validate_action_dependencies(actions, satisfied_dependencies=inherited)
        except (TypeError, ValueError):
            return False
        return (
            self.evidence_digest == hashlib.sha256(_canonical(evidence).encode("utf-8")).hexdigest()
            and self.actions_digest == _actions_digest(actions, inherited)
        )

    def snapshot(self) -> Dict[str, str]:
        return {
            "evidence_digest": self.evidence_digest,
            "actions_digest": self.actions_digest,
            "authorization_id": self.authorization_id,
        }
