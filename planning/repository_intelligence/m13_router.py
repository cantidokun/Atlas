"""M13.4 advisory bridge from compiled repository context to frozen M11 routing.

This module is development tooling only. It prepares a model-ready advisory
request using deterministic repository context and asks the frozen M11 router
for a model recommendation. It does not execute production work, authorize
anything, schedule work, persist authority state, or replace Hermes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from planning.m11_router.router import ModelRouter
from planning.m11_router.routing import RouterDecision
from planning.repository_intelligence.context import ContextPackage
from planning.repository_intelligence.context import compile_context
from planning.repository_intelligence.index import RepositoryIndex
from planning.repository_intelligence.relevance import RelevanceQuery, RelevanceWeights


@dataclass(frozen=True)
class ContextRoutingAdvice:
    """Immutable advisory result; authoritative execution remains elsewhere."""

    task_id: str
    decision: RouterDecision
    context: ContextPackage

    def model_payload(self) -> dict:
        """Return the bounded context payload for an injected development model."""
        return {
            "stable_instructions": self.context.stable_instructions,
            "dynamic_state": dict(self.context.dynamic_state),
            "repository_context": [
                {
                    "path": item.path,
                    "score": item.score,
                    "reasons": list(item.reasons),
                    "content": item.content,
                    "truncated": item.truncated,
                }
                for item in self.context.included
            ],
            "context_fingerprint": self.context.fingerprint,
        }


def advise_context_route(
    *,
    task_id: str,
    dimension_scores: Mapping[str, int],
    index: RepositoryIndex,
    query: RelevanceQuery,
    source_by_path: Mapping[str, str],
    router: ModelRouter,
    task_classes: Optional[Sequence[str]] = None,
    stable_instructions: str = "",
    dynamic_state: Optional[Mapping[str, object]] = None,
    max_context_chars: int = 48_000,
    max_file_chars: int = 16_000,
    minimum_score: int = 1,
    weights: RelevanceWeights = RelevanceWeights(),
) -> ContextRoutingAdvice:
    """Compile minimum-sufficient context, then obtain an M11 advisory route.

    Ordering is intentional: context selection is deterministic and independent
    of model output; M11 remains the sole routing authority for development
    model selection. A failed route is represented by the router's existing
    fail-closed decision rather than by a fallback model.
    """
    context = compile_context(
        index,
        query,
        source_by_path,
        stable_instructions=stable_instructions,
        dynamic_state=dynamic_state,
        max_context_chars=max_context_chars,
        max_file_chars=max_file_chars,
        minimum_score=minimum_score,
        weights=weights,
    )
    decision = router.route_task(
        task_id,
        dict(dimension_scores),
        task_classes=task_classes,
    )
    return ContextRoutingAdvice(task_id=task_id, decision=decision, context=context)
