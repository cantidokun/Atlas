"""Deterministic repository intelligence for Atlas development tooling."""

from planning.repository_intelligence.context import ContextFile, ContextPackage, compile_context
from planning.repository_intelligence.index import (
    GitHistory,
    ImportRecord,
    RepositoryIndex,
    SymbolRecord,
    build_repository_index,
)
from planning.repository_intelligence.m13_router import ContextRoutingAdvice, advise_context_route
from planning.repository_intelligence.relevance import (
    RelevanceExplanation,
    RelevanceQuery,
    RelevanceResult,
    RelevanceWeights,
    rank_repository_files,
)

__all__ = [
    "ContextFile",
    "ContextPackage",
    "ContextRoutingAdvice",
    "GitHistory",
    "ImportRecord",
    "RelevanceExplanation",
    "RelevanceQuery",
    "RelevanceResult",
    "RelevanceWeights",
    "RepositoryIndex",
    "SymbolRecord",
    "advise_context_route",
    "build_repository_index",
    "compile_context",
    "rank_repository_files",
]
