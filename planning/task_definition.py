"""Declarative task definition shared by Atlas production-task adapters."""
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional, Tuple

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.target_state import TargetStateEvaluator


@dataclass(frozen=True)
class AtlasTaskDefinition:
    """Task-specific data only; orchestration remains generic."""

    name: str
    evidence: Tuple[EvidenceRequest, ...]
    actions: Tuple[ActionSpec, ...]
    evaluator: TargetStateEvaluator
    allowed_action_tools: FrozenSet[str]
    allow_writes: bool = False
    verify_after_action: bool = True
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("task name must not be empty")
        if not self.evidence:
            raise ValueError("task must define at least one evidence request")
        if not self.actions:
            raise ValueError("task must define at least one action")
        allowed = frozenset(self.allowed_action_tools)
        if not allowed:
            raise ValueError("task must define allowed action tools")
        object.__setattr__(self, "allowed_action_tools", allowed)
        action_tools = {action.tool for action in self.actions}
        unknown = action_tools - allowed
        if unknown:
            raise ValueError(f"actions use unauthorized tools: {sorted(unknown)}")

    def snapshot(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "evidence": [
                {
                    "tool": item.tool,
                    "arguments": deepcopy(item.arguments),
                    "name": item.name,
                }
                for item in self.evidence
            ],
            "actions": [
                {
                    "tool": item.tool,
                    "arguments": deepcopy(item.arguments),
                    "name": item.name,
                }
                for item in self.actions
            ],
            "allowed_action_tools": sorted(self.allowed_action_tools),
            "allow_writes": self.allow_writes,
            "verify_after_action": self.verify_after_action,
            "metadata": deepcopy(self.metadata or {}),
        }
