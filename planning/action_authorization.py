"""Immutable authorization receipts for generic Atlas action plans."""
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict, Iterable, List, Tuple

from planning.action_dependencies import validate_action_dependencies
from planning.action_plan import ActionSpec


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _normalize_inherited_dependencies(names: Iterable[str]) -> Tuple[str, ...]:
    return tuple(sorted({str(name).strip() for name in names if str(name).strip()}))


def _action_payload(action: ActionSpec) -> Dict[str, Any]:
    return {
        "tool": action.tool,
        "arguments": dict(action.arguments),
        "name": action.name,
        "requires_success": action.requires_success,
        "depends_on": list(action.dependency_names()),
    }


def _plan_digest(actions: List[ActionSpec], inherited_dependencies: Iterable[str] = ()) -> str:
    inherited = _normalize_inherited_dependencies(inherited_dependencies)
    action_payloads = [_action_payload(action) for action in actions]
    # Preserve the pre-dependency digest format for ordinary plans so durable
    # authorization receipts created before Stage 14 remain resumable.
    if not inherited:
        payload: Any = action_payloads
    else:
        payload = {
            "actions": action_payloads,
            "inherited_dependencies": list(inherited),
        }
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ActionAuthorization:
    """Immutable proof that a specific action plan was explicitly authorized."""

    plan_digest: str
    authorization_id: str

    @classmethod
    def issue(
        cls,
        actions: List[ActionSpec],
        authorization_id: str,
        *,
        inherited_dependencies: Iterable[str] = (),
    ) -> "ActionAuthorization":
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise ValueError("authorization_id must be a non-empty string.")
        if not isinstance(actions, list) or any(not isinstance(action, ActionSpec) for action in actions):
            raise TypeError("actions must be a list of ActionSpec objects.")
        inherited = _normalize_inherited_dependencies(inherited_dependencies)
        validate_action_dependencies(actions, satisfied_dependencies=inherited)
        return cls(_plan_digest(actions, inherited), authorization_id.strip())

    @classmethod
    def from_snapshot(cls, snapshot: Dict[str, Any]) -> "ActionAuthorization":
        """Restore an authorization receipt without minting a new identity."""
        if not isinstance(snapshot, dict):
            raise TypeError("authorization snapshot must be a dictionary.")
        plan_digest = snapshot.get("plan_digest")
        authorization_id = snapshot.get("authorization_id")
        if not isinstance(plan_digest, str) or not plan_digest:
            raise ValueError("authorization snapshot is missing plan_digest")
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise ValueError("authorization snapshot is missing authorization_id")
        return cls(plan_digest, authorization_id.strip())

    def matches(
        self,
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
        return self.plan_digest == _plan_digest(actions, inherited)

    def snapshot(self) -> Dict[str, str]:
        return {
            "plan_digest": self.plan_digest,
            "authorization_id": self.authorization_id,
        }
