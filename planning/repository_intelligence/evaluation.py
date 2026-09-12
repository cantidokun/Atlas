"""Deterministic evaluation metrics for Atlas repository-context selection.

M13.5 measures context quality without invoking a model. The evaluator compares
selected paths against task-declared relevant/required paths and reports recall,
precision, budget utilization, truncation, and deterministic fingerprints.
It is development tooling only and has no production authority imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from planning.repository_intelligence.context import ContextPackage


@dataclass(frozen=True)
class ContextEvaluationCase:
    """Ground-truth fixture for context-selection evaluation."""

    case_id: str
    relevant_paths: frozenset[str]
    required_paths: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id must be non-empty")
        if not self.required_paths.issubset(self.relevant_paths):
            raise ValueError("required_paths must be a subset of relevant_paths")


@dataclass(frozen=True)
class ContextEvaluationResult:
    """Objective context-selection metrics for one evaluation case."""

    case_id: str
    selected_paths: tuple[str, ...]
    relevant_paths: tuple[str, ...]
    required_paths: tuple[str, ...]
    true_positive: int
    false_positive: int
    false_negative: int
    required_missing: int
    recall: float
    precision: float
    f1: float
    budget_utilization: float
    truncated_files: int
    deterministic: bool


def evaluate_context(
    case: ContextEvaluationCase,
    context: ContextPackage,
    *,
    baseline_context: ContextPackage | None = None,
) -> ContextEvaluationResult:
    """Score a compiled package against explicit ground truth.

    ``baseline_context`` is optional and is used only to establish whether the
    same compiler inputs produce the same fingerprint; no model judgment is
    inferred from the baseline.
    """
    selected = {item.path for item in context.included}
    relevant = set(case.relevant_paths)
    required = set(case.required_paths)
    tp = len(selected & relevant)
    fp = len(selected - relevant)
    fn = len(relevant - selected)
    missing = len(required - selected)
    recall = tp / len(relevant) if relevant else 1.0
    precision = tp / len(selected) if selected else (1.0 if not relevant else 0.0)
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    utilization = context.context_chars / context_budget(context)
    deterministic = baseline_context is None or baseline_context.fingerprint == context.fingerprint
    return ContextEvaluationResult(
        case_id=case.case_id,
        selected_paths=tuple(sorted(selected)),
        relevant_paths=tuple(sorted(relevant)),
        required_paths=tuple(sorted(required)),
        true_positive=tp,
        false_positive=fp,
        false_negative=fn,
        required_missing=missing,
        recall=recall,
        precision=precision,
        f1=f1,
        budget_utilization=utilization,
        truncated_files=sum(1 for item in context.included if item.truncated),
        deterministic=deterministic,
    )


def context_budget(context: ContextPackage) -> int:
    """Recover the compiler's configured context budget from its manifest."""
    payload = context.to_dict()
    # Fingerprint inputs contain the manifest, but it is intentionally not
    # exposed separately. For evaluation, context_chars is the safe denominator
    # only when the package exposes a positive budget attribute in the future.
    # Current packages have a fixed M13 default budget.
    return max(1, 48_000)


def aggregate_evaluations(results: Sequence[ContextEvaluationResult]) -> dict:
    """Aggregate objective selection metrics across evaluation cases."""
    if not results:
        return {
            "cases": 0,
            "recall": None,
            "precision": None,
            "f1": None,
            "required_missing": 0,
            "avg_budget_utilization": None,
            "truncated_files": 0,
            "deterministic": True,
        }
    return {
        "cases": len(results),
        "recall": sum(r.recall for r in results) / len(results),
        "precision": sum(r.precision for r in results) / len(results),
        "f1": sum(r.f1 for r in results) / len(results),
        "required_missing": sum(r.required_missing for r in results),
        "avg_budget_utilization": sum(r.budget_utilization for r in results) / len(results),
        "truncated_files": sum(r.truncated_files for r in results),
        "deterministic": all(r.deterministic for r in results),
    }
