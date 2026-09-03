"""Reusable higher-level production-task composition for Atlas.

Production tasks describe a meaningful multi-operation goal while compiling to
one existing :class:`AtlasTaskDefinition`. They add semantic organization and
production intent only; execution, authorization, checkpointing, recovery, and
verification remain owned by the existing generic task runtime.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from action_plan import ActionSpec
from planning.action_dependencies import validate_action_dependencies
from planning.evidence_plan import EvidenceRequest
from planning.task_definition import AtlasTaskDefinition
from planning.target_state import TargetStateEvaluator


@dataclass(frozen=True)
class ProductionTaskDefinition:
    """A reusable semantic production goal backed by one Atlas task contract.

    ``objective``, ``domain``, ``deliverables``, and ``constraints`` describe
    production intent for higher-level planning systems. They never grant an
    execution capability; the compiled :class:`AtlasTaskDefinition` remains the
    sole runtime contract.
    """

    name: str
    objective: str
    evidence: Tuple[EvidenceRequest, ...]
    actions: Tuple[ActionSpec, ...]
    evaluator: TargetStateEvaluator
    allowed_action_tools: Tuple[str, ...]
    domain: str = "soccer-production"
    deliverables: Tuple[str, ...] = ()
    constraints: Tuple[str, ...] = ()
    allow_writes: bool = True
    verify_after_action: bool = True
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("production task name must not be empty")
        if not self.objective.strip():
            raise ValueError("production task objective must not be empty")
        if not self.domain.strip():
            raise ValueError("production task domain must not be empty")
        if not self.evidence:
            raise ValueError("production task must define at least one evidence request")
        if not self.actions:
            raise ValueError("production task must define at least one action")
        if not self.allowed_action_tools:
            raise ValueError("production task must define allowed action tools")
        if any(not isinstance(item, str) or not item.strip() for item in self.deliverables):
            raise ValueError("production task deliverables must contain non-empty strings")
        if any(not isinstance(item, str) or not item.strip() for item in self.constraints):
            raise ValueError("production task constraints must contain non-empty strings")
        action_tools = {action.tool for action in self.actions}
        unauthorized = action_tools - set(self.allowed_action_tools)
        if unauthorized:
            raise ValueError(f"production task actions use unauthorized tools: {sorted(unauthorized)}")
        validate_action_dependencies(list(self.actions))

    def compile(self) -> AtlasTaskDefinition:
        """Compile to the existing task contract without introducing execution semantics."""
        metadata = deepcopy(self.metadata or {})
        metadata.update({
            "production_task": self.name,
            "objective": self.objective,
            "domain": self.domain,
            "deliverables": list(self.deliverables),
            "constraints": list(self.constraints),
        })
        return AtlasTaskDefinition(
            name=self.name,
            evidence=tuple(self.evidence),
            actions=tuple(self.actions),
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
            "domain": self.domain,
            "deliverables": list(self.deliverables),
            "constraints": list(self.constraints),
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
