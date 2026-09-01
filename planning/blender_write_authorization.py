"""Explicit authorization gate for Blender scene-writing capabilities."""
from dataclasses import dataclass
from typing import Any, Dict

from planning.action_plan import ActionSpec
from planning.action_authorization import ActionAuthorization
from planning.blender_capability_catalog import require_verified_blender_write


@dataclass(frozen=True)
class BlenderWriteAuthorization:
    """Immutable authorization for one exact, verified Blender write action."""

    tool: str
    authorization_id: str
    action_authorization: ActionAuthorization

    @classmethod
    def issue(cls, action: ActionSpec, authorization_id: str) -> "BlenderWriteAuthorization":
        if not isinstance(action, ActionSpec):
            raise TypeError("action must be an ActionSpec")
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise ValueError("authorization_id must be a non-empty string")
        normalized_authorization_id = authorization_id.strip()
        try:
            require_verified_blender_write(action.tool)
        except ValueError as exc:
            if str(exc).startswith("unsupported Blender capability:"):
                raise ValueError(
                    f"verified Blender write capability required: Unknown Blender capability: {action.tool}"
                ) from exc
            raise
        return cls(
            tool=action.tool,
            authorization_id=normalized_authorization_id,
            action_authorization=ActionAuthorization.issue([action], normalized_authorization_id),
        )

    @classmethod
    def restore(cls, action: ActionSpec, snapshot: Dict[str, Any]) -> "BlenderWriteAuthorization":
        """Restore only an exact authorization snapshot, revalidating its identity."""
        if not isinstance(action, ActionSpec):
            raise TypeError("action must be an ActionSpec")
        if not isinstance(snapshot, dict):
            raise TypeError("snapshot must be a mapping")
        if snapshot.get("tool") != action.tool:
            raise ValueError("authorization snapshot tool does not match action")
        authorization_id = snapshot.get("authorization_id")
        nested = snapshot.get("action_authorization")
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise ValueError("authorization snapshot requires authorization_id")
        if not isinstance(nested, dict):
            raise ValueError("authorization snapshot requires action_authorization")
        plan_digest = nested.get("plan_digest")
        nested_id = nested.get("authorization_id")
        if not isinstance(plan_digest, str) or not plan_digest:
            raise ValueError("authorization snapshot requires plan_digest")
        if nested_id != authorization_id.strip():
            raise ValueError("authorization snapshot authorization_id mismatch")
        restored = cls.issue(action, authorization_id)
        if restored.action_authorization.plan_digest != plan_digest:
            raise ValueError("authorization snapshot plan_digest does not match action")
        return restored

    def matches(self, action: ActionSpec) -> bool:
        return isinstance(action, ActionSpec) and action.tool == self.tool and self.action_authorization.matches([action])

    def snapshot(self) -> Dict[str, Any]:
        return {"tool": self.tool, "authorization_id": self.authorization_id, "action_authorization": self.action_authorization.snapshot()}


def authorize_blender_write(action: ActionSpec, authorization_id: str) -> BlenderWriteAuthorization:
    return BlenderWriteAuthorization.issue(action, authorization_id)
