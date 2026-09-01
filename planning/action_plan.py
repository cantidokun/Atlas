"""Generic deterministic action-plan primitives for Atlas."""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ActionSpec:
    """One authorized action in an execution plan."""
    tool: str
    arguments: Dict[str, Any]
    name: str = ""
    requires_success: bool = True


@dataclass
class ActionPlan:
    """Track deterministic progress through an ordered, authorized action sequence."""
    actions: List[ActionSpec]
    current_index: int = 0
    completed: List[Dict[str, Any]] = field(default_factory=list)
    failed: Optional[Dict[str, Any]] = None
    authorization: Optional[Any] = None

    @property
    def complete(self) -> bool:
        return self.failed is None and self.current_index >= len(self.actions)

    @property
    def blocked(self) -> bool:
        return self.failed is not None

    @property
    def authorized(self) -> bool:
        return self.authorization is not None and self.authorization.matches(self.actions)

    @property
    def authorization_id(self) -> Optional[str]:
        """Return the human/audit identifier bound to the current receipt."""
        return getattr(self.authorization, "authorization_id", None)

    @property
    def next_action(self) -> Optional[ActionSpec]:
        if self.complete or self.blocked:
            return None
        return self.actions[self.current_index]

    def authorize(self, authorization: Any) -> None:
        """Install an immutable authorization receipt for this exact action list."""
        if self.current_index != 0 or self.completed or self.failed is not None:
            raise RuntimeError("Action plan can only be authorized before execution begins.")
        if not authorization.matches(self.actions):
            raise RuntimeError("Authorization does not match the exact action plan.")
        self.authorization = authorization

    def authorize_with_id(self, authorization_id: str) -> Any:
        """Issue and install a receipt for this exact plan in one explicit operation."""
        from planning.action_authorization import ActionAuthorization

        authorization = ActionAuthorization.issue(self.actions, authorization_id)
        self.authorize(authorization)
        return authorization

    def record_result(self, result: Dict[str, Any], success: bool) -> None:
        """Record one action result and advance only after success."""
        if self.complete:
            raise RuntimeError("Action plan is already complete.")
        if self.blocked:
            raise RuntimeError("Action plan is blocked by a previous failure.")
        if not self.authorized:
            raise RuntimeError("Action plan execution requires valid authorization.")
        action = self.actions[self.current_index]
        entry = {
            "index": self.current_index,
            "name": action.name or action.tool,
            "tool": action.tool,
            "arguments": deepcopy(action.arguments),
            "result": deepcopy(result),
            "success": bool(success),
        }
        self.completed.append(entry)
        if success:
            self.current_index += 1
        elif action.requires_success:
            self.failed = entry

    def snapshot(self) -> Dict[str, Any]:
        """Return an isolated serializable execution state for logging or evidence."""
        next_action = self.next_action
        return {
            "current_index": self.current_index,
            "total_actions": len(self.actions),
            "complete": self.complete,
            "blocked": self.blocked,
            "authorized": self.authorized,
            "authorization": self.authorization.snapshot() if self.authorization is not None else None,
            "next_action": (
                {
                    "name": next_action.name or next_action.tool,
                    "tool": next_action.tool,
                    "arguments": deepcopy(next_action.arguments),
                }
                if next_action is not None
                else None
            ),
            "completed": deepcopy(self.completed),
            "failure": deepcopy(self.failed),
        }
