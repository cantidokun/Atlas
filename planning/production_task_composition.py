"""Reusable composition primitives for Atlas soccer-production tasks.

This module composes already-declarative evidence and action fragments into one
ProductionTaskDefinition. It introduces no executor, scheduler, authorization,
or verification path of its own; compilation still produces one canonical
AtlasTaskDefinition consumed by the existing runtime.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.production_task import ProductionTaskDefinition
from planning.target_state import TargetStateEvaluator


@dataclass(frozen=True)
class ProductionTaskFragment:
    """Named semantic production fragment containing declarative work."""

    name: str
    evidence: Tuple[EvidenceRequest, ...] = ()
    actions: Tuple[ActionSpec, ...] = ()
    deliverables: Tuple[str, ...] = ()
    constraints: Tuple[str, ...] = ()
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("production fragment name must not be empty")
        if any(not isinstance(item, str) or not item.strip() for item in self.deliverables):
            raise ValueError("production fragment deliverables must contain non-empty strings")
        if any(not isinstance(item, str) or not item.strip() for item in self.constraints):
            raise ValueError("production fragment constraints must contain non-empty strings")

    def snapshot(self) -> Dict[str, Any]:
        """Return a durable semantic description without adding execution state."""
        return {
            "name": self.name,
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
            "deliverables": list(self.deliverables),
            "constraints": list(self.constraints),
            "metadata": deepcopy(self.metadata or {}),
        }


def compose_production_task(
    *,
    name: str,
    objective: str,
    fragments: Iterable[ProductionTaskFragment],
    evaluator: TargetStateEvaluator,
    allowed_action_tools: Iterable[str],
    domain: str = "soccer-production",
    deliverables: Iterable[str] = (),
    constraints: Iterable[str] = (),
    allow_writes: bool = True,
    verify_after_action: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
) -> ProductionTaskDefinition:
    """Compose named fragments into one validated higher-level production task.

    Fragment order is preserved. Fragment-local semantic metadata is retained
    in the compiled task metadata while all evidence/actions are flattened into
    the one canonical task contract consumed by the existing runtime.
    """
    fragment_list: List[ProductionTaskFragment] = list(fragments)
    if not fragment_list:
        raise ValueError("at least one production fragment is required")

    seen_names = set()
    evidence: List[EvidenceRequest] = []
    actions: List[ActionSpec] = []
    combined_deliverables: List[str] = list(deliverables)
    combined_constraints: List[str] = list(constraints)
    fragment_specs: List[Dict[str, Any]] = []
    for fragment in fragment_list:
        if fragment.name in seen_names:
            raise ValueError(f"duplicate production fragment name: {fragment.name}")
        seen_names.add(fragment.name)
        evidence.extend(fragment.evidence)
        actions.extend(fragment.actions)
        combined_deliverables.extend(fragment.deliverables)
        combined_constraints.extend(fragment.constraints)
        fragment_specs.append(fragment.snapshot())

    combined_metadata = deepcopy(metadata or {})
    combined_metadata["fragments"] = [fragment.name for fragment in fragment_list]
    combined_metadata["fragment_specs"] = fragment_specs

    return ProductionTaskDefinition(
        name=name,
        objective=objective,
        evidence=tuple(evidence),
        actions=tuple(actions),
        evaluator=evaluator,
        allowed_action_tools=tuple(allowed_action_tools),
        domain=domain,
        deliverables=tuple(combined_deliverables),
        constraints=tuple(combined_constraints),
        allow_writes=allow_writes,
        verify_after_action=verify_after_action,
        metadata=combined_metadata,
    )
