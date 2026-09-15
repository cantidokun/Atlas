"""Explain repository-context ranking failures without changing selection policy.

Development-only and pure. This module exposes the deterministic relevance score,
rank, and reasons for benchmark paths so ranking misses can be distinguished from
budget/packing misses before any relevance-weight change is attempted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from planning.repository_intelligence.benchmark import ContextBenchmarkCase, ContextBenchmarkResult
from planning.repository_intelligence.index import RepositoryIndex
from planning.repository_intelligence.relevance import RelevanceExplanation, rank_repository_files


@dataclass(frozen=True)
class RankedPathDiagnostic:
    """Ranking facts for one benchmark-relevant path."""

    path: str
    selected: bool
    relevant: bool
    required: bool
    rank: int | None
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CaseRankingDiagnostic:
    """Ranking diagnostics for one benchmark case."""

    case_id: str
    paths: tuple[RankedPathDiagnostic, ...]


def diagnose_rankings(
    index: RepositoryIndex,
    cases: Sequence[ContextBenchmarkCase],
    result: ContextBenchmarkResult,
) -> tuple[CaseRankingDiagnostic, ...]:
    """Explain benchmark-relevant paths using the current deterministic ranking.

    The function deliberately does not alter weights, compile context, or infer
    model behavior. A missing path with a strong rank can therefore be separated
    from a path that was never considered relevant by the ranking layer.
    """
    results_by_case = {item.case_id: item for item in result.cases}
    diagnostics: list[CaseRankingDiagnostic] = []
    for case in cases:
        evaluation = results_by_case.get(case.case_id)
        if evaluation is None:
            raise ValueError(f"missing benchmark result for case: {case.case_id}")

        ranking = rank_repository_files(index, case.query)
        rank_by_path = {item.path: position for position, item in enumerate(ranking.explanations, start=1)}
        explanation_by_path = {item.path: item for item in ranking.explanations}
        selected = set(evaluation.selected_paths)
        relevant = set(case.relevant_paths)
        required = set(case.required_paths)
        paths = sorted(relevant | required)

        diagnostics.append(
            CaseRankingDiagnostic(
                case_id=case.case_id,
                paths=tuple(
                    _diagnose_path(
                        path,
                        selected=path in selected,
                        relevant=path in relevant,
                        required=path in required,
                        rank=rank_by_path.get(path),
                        explanation=explanation_by_path.get(path),
                    )
                    for path in paths
                ),
            )
        )
    return tuple(diagnostics)


def _diagnose_path(
    path: str,
    *,
    selected: bool,
    relevant: bool,
    required: bool,
    rank: int | None,
    explanation: RelevanceExplanation | None,
) -> RankedPathDiagnostic:
    return RankedPathDiagnostic(
        path=path,
        selected=selected,
        relevant=relevant,
        required=required,
        rank=rank,
        score=explanation.score if explanation is not None else 0,
        reasons=explanation.reasons if explanation is not None else (),
    )


def ranking_diagnostic_report(
    diagnostics: Iterable[CaseRankingDiagnostic],
) -> list[dict]:
    """Serialize diagnostics without source contents or runtime state."""
    return [
        {
            "case_id": case.case_id,
            "paths": [
                {
                    "path": item.path,
                    "selected": item.selected,
                    "relevant": item.relevant,
                    "required": item.required,
                    "rank": item.rank,
                    "score": item.score,
                    "reasons": list(item.reasons),
                }
                for item in case.paths
            ],
        }
        for case in diagnostics
    ]
