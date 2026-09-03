"""Reusable composition primitives for Atlas soccer-production tasks.

This module composes already-declarative evidence and action fragments into one
ProductionTaskDefinition. It introduces no executor, scheduler, authorization,
or verification path of its own; compilation still produces one canonical
AtlasTaskDefinition consumed by the existing runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.production_task import ProductionTaskDefinition
from planning.target_state import TargetStateEvaluator


@dataclass(frozen=True)
class ProductionTaskFragment:
    """Named production fragment containing declarative evidence and actions."""

    name: str
    evidence: Tuple[EvidenceRequest, ...] = ()
    actions: Tuple[ActionSpec, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("production fragment name must not be empty")


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
) -> ProductionTaskDefinition:
    """Compose named fragments into one validated higher-level production task.

    Fragment order is preserved. Action dependencies remain explicit on each
    ActionSpec; the normal production/task contract validates the resulting
    complete action list before execution authorization can occur.
    """
    fragment_list: List[ProductionTaskFragment] = list(fragments)
    if not fragment_list:
        raise ValueError("at least one production fragment is required")

    seen_names = set()
    evidence: List[EvidenceRequest] = []
    actions: List[ActionSpec] = []
    for fragment in fragment_list:
        if fragment.name in seen_names:
            raise ValueError(f"duplicate production fragment name: {fragment.name}")
        seen_names.add(fragment.name)
        evidence.extend(fragment.evidence)
        actions.extend(fragment.actions)

    return ProductionTaskDefinition(
        name=name,
        objective=objective,
        evidence=tuple(evidence),
        actions=tuple(actions),
        evaluator=evaluator,
        allowed_action_tools=tuple(allowed_action_tools),
        domain=domain,
        deliverables=tuple(deliverables),
        constraints=tuple(constraints),
        allow_writes=allow_writes,
        verify_after_action=verify_after_action,
        metadata={"fragments": [fragment.name for fragment in fragment_list]},
    )
