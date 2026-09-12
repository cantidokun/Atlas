"""Failure diagnostics for the M13.7 repository-context benchmark.

Development-only and pure: diagnostics consume benchmark results and do not
modify ranking, invoke models, or access production/runtime authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from planning.repository_intelligence.evaluation import ContextEvaluationResult


@dataclass(frozen=True)
class ContextDiagnostic:
    """Explain the measurable failure mode of one benchmark case."""

    case_id: str
    status: str
    missing_required: tuple[str, ...]
    missing_relevant: tuple[str, ...]
    extra_selected: tuple[str, ...]
    truncated_files: tuple[str, ...]
    deterministic: bool


def diagnose_case(result: ContextEvaluationResult) -> ContextDiagnostic:
    """Classify a case without guessing at model behavior."""
    required = tuple(sorted(result.required_missing))
    relevant = tuple(sorted(set(result.relevant_paths) - set(result.selected_paths)))
    extra = tuple(sorted(set(result.selected_paths) - set(result.relevant_paths)))

    if not result.deterministic:
        status = "non_deterministic"
    elif required:
        status = "required_context_missing"
    elif relevant:
        status = "relevant_context_missing"
    elif extra:
        status = "over_selected"
    elif result.truncated_files:
        status = "complete_selection_truncated"
    else:
        status = "pass"

    return ContextDiagnostic(
        case_id=result.case_id,
        status=status,
        missing_required=required,
        missing_relevant=relevant,
        extra_selected=extra,
        truncated_files=tuple(sorted(result.truncated_files)),
        deterministic=result.deterministic,
    )


def diagnose_results(results: Iterable[ContextEvaluationResult]) -> tuple[ContextDiagnostic, ...]:
    """Return deterministic diagnostics ordered by case ID."""
    return tuple(sorted((diagnose_case(item) for item in results), key=lambda item: item.case_id))
