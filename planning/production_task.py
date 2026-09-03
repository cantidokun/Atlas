"""Reusable higher-level production-task composition for Atlas.

Production tasks describe a meaningful multi-operation goal while compiling to
one existing :class:`AtlasTaskDefinition`. They add organization and semantic
metadata only; execution, authorization, checkpointing, recovery, and
verification remain owned by the existing generic task runtime.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.task_definition import AtlasTaskDefinition
from planning.target_state import TargetStateEvaluator


@dataclass(frozen=True)
class ProductionTaskDefinition:
    """A reusable semantic production goal backed by one Atlas task contract."""

    name: str
    objective: str
    evidence: Tuple[EvidenceRequest, ...]
    actions: Tuple[ActionSpec, ...]
    evaluator: TargetStateEvaluator
    allowed_action_tools: Tuple[str, ...]
    allow_writes: bool = True
    verify_after_action: bool = True
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("production task name must not be empty")
        if not self.objective.strip():
            raise ValueError("production task objective must not be empty")
        if not self.evidence:
            raise ValueError("production task must define at least one evidence request")
        if not self.actions:
            raise ValueError("production task must define at least one action")
        if not self.allowed_action_tools:
            raise ValueError("production task must define allowed action tools")

    def compile(self) -> AtlasTaskDefinition:
        """Compile to the existing task contract without introducing execution semantics."""
        metadata = deepcopy(self.metadata or {})
        metadata.update({
            "production_task": self.name,
            "objective": self.objective,
        })
        return AtlasTaskDefinition(
            name=self.name,
            evidence=self.evidence,
            actions=self.actions,
            evaluator=self.evaluator,
            allowed_action_tools=set(self.allowed_action_tools),
            allow_writes=self.allow_writes,
            verify_after_action=self.verify_after_action,
            metadata=metadata,
        )

    def snapshot(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "objective": self.objective,
            "evidence": [
                {
                    "tool": request.tool,
                    "arguments": deepcopy(request.arguments),
                    "name": request.name,
                }
                for request in self.evidence
            ],
            "actions": [
                {
                    "tool": action.tool,
                    "arguments": deepcopy(action.arguments),
                    "name": action.name,
                    "requires_success": action.requires_success,
                    "depends_on": list(action.dependency_names()),
                }
                for action in self.actions
            ],
            "allowed_action_tools": list(self.allowed_action_tools),
            "allow_writes": self.allow_writes,
            "verify_after_action": self.verify_after_action,
            "metadata": deepcopy(self.metadata or {}),
        }
