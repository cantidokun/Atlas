"""Declarative task definition shared by Atlas production-task adapters."""
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set, Tuple

from action_plan import ActionSpec
from planning.action_dependencies import validate_action_dependencies
from planning.evidence_plan import EvidenceRequest
from planning.target_state import TargetStateEvaluator


@dataclass(frozen=True)
class AtlasTaskDefinition:
    """Task-specific data only; orchestration remains generic."""

    name: str
    evidence: Tuple[EvidenceRequest, ...]
    actions: Tuple[ActionSpec, ...]
    evaluator: TargetStateEvaluator
    allowed_action_tools: Set[str]
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
        if not self.allowed_action_tools:
            raise ValueError("task must define allowed action tools")
        action_tools = {action.tool for action in self.actions}
        unknown = action_tools - set(self.allowed_action_tools)
        if unknown:
            raise ValueError(f"actions use unauthorized tools: {sorted(unknown)}")
        validate_action_dependencies(list(self.actions))

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
                    "requires_success": item.requires_success,
                    "depends_on": list(item.dependency_names()),
                }
                for item in self.actions
            ],
            "allowed_action_tools": sorted(self.allowed_action_tools),
            "allow_writes": self.allow_writes,
            "verify_after_action": self.verify_after_action,
            "metadata": deepcopy(self.metadata or {}),
        }
