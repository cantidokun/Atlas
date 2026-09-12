"""Deterministic repository intelligence for Atlas development tooling."""

from planning.repository_intelligence.benchmark import (
    ContextBenchmarkCase,
    ContextBenchmarkResult,
    compile_benchmark_context,
    curated_context_benchmark_cases,
    run_context_benchmark,
    validate_benchmark_corpus,
    validate_benchmark_inputs,
)
from planning.repository_intelligence.context import ContextFile, ContextPackage, compile_context
from planning.repository_intelligence.evaluation import (
    ContextEvaluationCase,
    ContextEvaluationResult,
    aggregate_evaluations,
    evaluate_context,
    repeat_context,
)
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
    "ContextBenchmarkCase",
    "ContextBenchmarkResult",
    "ContextEvaluationCase",
    "ContextEvaluationResult",
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
    "aggregate_evaluations",
    "build_repository_index",
    "compile_benchmark_context",
    "compile_context",
    "curated_context_benchmark_cases",
    "evaluate_context",
    "rank_repository_files",
    "repeat_context",
    "run_context_benchmark",
    "validate_benchmark_corpus",
    "validate_benchmark_inputs",
]
