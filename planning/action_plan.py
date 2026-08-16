"""Generic deterministic action-plan primitives for Atlas.

This module is intentionally independent from the current goalpost controller.
It provides a small state machine for tasks that require several authorized
actions in a known order, while leaving task interpretation to the agent.

Qwen can propose or explain a plan. Python owns execution state once the plan
has been accepted for execution.
"""

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
    """Track deterministic progress through an ordered action sequence."""
    actions: List[ActionSpec]
    current_index: int = 0
    completed: List[Dict[str, Any]] = field(default_factory=list)
    failed: Optional[Dict[str, Any]] = None

    @property
    def complete(self) -> bool:
        return self.failed is None and self.current_index >= len(self.actions)

    @property
    def blocked(self) -> bool:
        return self.failed is not None

    @property
    def next_action(self) -> Optional[ActionSpec]:
        if self.complete or self.blocked:
            return None
        return self.actions[self.current_index]

    def record_result(self, result: Dict[str, Any], success: bool) -> None:
        """Record one action result and advance only after success."""
        if self.complete:
            raise RuntimeError("Action plan is already complete.")
        if self.blocked:
            raise RuntimeError("Action plan is blocked by a previous failure.")
        action = self.actions[self.current_index]
        entry = {"index": self.current_index, "name": action.name or action.tool, "tool": action.tool, "arguments": action.arguments, "result": result, "success": bool(success)}
        self.completed.append(entry)
        if success:
            self.current_index += 1
        elif action.requires_success:
            self.failed = entry

    def snapshot(self) -> Dict[str, Any]:
        """Return serializable execution state for logging or evidence."""
        next_action = self.next_action
        return {
            "current_index": self.current_index,
            "total_actions": len(self.actions),
            "complete": self.complete,
            "blocked": self.blocked,
            "next_action": ({"name": next_action.name or next_action.tool, "tool": next_action.tool, "arguments": next_action.arguments} if next_action is not None else None),
            "completed": list(self.completed),
            "failure": self.failed,
        }
