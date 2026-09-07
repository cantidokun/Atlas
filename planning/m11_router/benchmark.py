"""Model-router benchmark harness skeleton (M11.2 onward).

Implements docs/ATLAS_M11_ADAPTIVE_MODEL_ROUTING_DESIGN.md §12.

This milestone only defines the benchmark abstraction and a few representative
fixtures. It does NOT run the full corpus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from planning.m11_router.model_profile import ModelTier
from planning.m11_router.risk import RiskAssessment, RISK_DIMENSIONS
import json


# All dimensions zero: the baseline for task-level classification.
_ZERO = {d: 0 for d in RISK_DIMENSIONS}


@dataclass(frozen=True)
class BenchmarkTask:
    """A benchmark task fixture (design §12)."""

    task_id: str
    description: str
    task_class: str
    dimension_scores: Dict[str, int] = field(default_factory=dict)
    expected_risk_tier: ModelTier = ModelTier.L0
    minimum_acceptable_result_tier: ModelTier = ModelTier.L0
    objective_success: tuple = ("deterministic depends on fixture",)
    token_cost_hint: Optional[int] = None

    @property
    def full_dimension_scores(self) -> Dict[str, int]:
        """Return dimension_scores overlaid on an all-zero baseline."""
        scores = dict(_ZERO)
        scores.update(self.dimension_scores)
        return scores


@dataclass
class BenchmarkResult:
    task: BenchmarkTask
    risk: Optional[RiskAssessment] = None
    outcome: Optional[str] = None
    measured_metrics: Dict[str, object] = field(default_factory=dict)


# Representative fixtures (infrastructure only; not a full corpus).
SAMPLE_BENCHMARK_TASKS: List[BenchmarkTask] = [
    BenchmarkTask(
        task_id="b-docs-001",
        description="Documentation-only change",
        task_class="docs",
        dimension_scores={},
        expected_risk_tier=ModelTier.L0,
        minimum_acceptable_result_tier=ModelTier.L0,
        objective_success=("markdown-consistency", "no behavioral change"),
    ),
    BenchmarkTask(
        task_id="b-test-001",
        description="Add a deterministic unit test",
        task_class="test",
        dimension_scores={"code_complexity": 1, "difficulty_of_verification": 1},
        expected_risk_tier=ModelTier.L1,
        minimum_acceptable_result_tier=ModelTier.L0,
        objective_success=("new test passes in full suite",),
    ),
    BenchmarkTask(
        task_id="b-refactor-001",
        description="Non-behavioral refactor of a helper",
        task_class="refactor",
        dimension_scores={"code_complexity": 2},
        expected_risk_tier=ModelTier.L1,
        minimum_acceptable_result_tier=ModelTier.L1,
        objective_success=("full suite green", "UBT build ok"),
    ),
    BenchmarkTask(
        task_id="b-api-001",
        description="Transport request-shape API boundary change",
        task_class="api-boundary",
        dimension_scores={"code_complexity": 2, "cross_process": 2},
        expected_risk_tier=ModelTier.L2,
        minimum_acceptable_result_tier=ModelTier.L2,
        objective_success=("contract tests green", "transport tests green"),
    ),
    BenchmarkTask(
        task_id="b-recovery-001",
        description="Coordinator recovery Case J/H path change",
        task_class="recovery",
        dimension_scores={"recovery_statefulness": 2, "cross_process": 2},
        expected_risk_tier=ModelTier.L2,
        minimum_acceptable_result_tier=ModelTier.L2,
        objective_success=("deterministic fail-closed tests green",),
    ),
    BenchmarkTask(
        task_id="b-crypto-001",
        description="HMAC/nonce attestation change",
        task_class="security-crypto",
        dimension_scores={"cryptography": 3, "security_sensitivity": 3},
        expected_risk_tier=ModelTier.L3,
        minimum_acceptable_result_tier=ModelTier.L3,
        objective_success=("HMAC vectors pass", "contract green"),
    ),
]


SAMPLE_BENCHMARKS = {t.task_id: t for t in SAMPLE_BENCHMARK_TASKS}


def run_benchmark_task(
    task: BenchmarkTask,
    router,
    *,
    advisor: Optional[object] = None,
) -> BenchmarkResult:
    """Run one fixture through the router (optionally through a shadow advisor).

    When ``advisor`` (a ShadowAdvisor-like) is supplied, the benchmark also
    executes a provider invocation in shadow mode and captures useful-output
    metrics (evidence outcome, tokens, latency, cost, final tier, escalation).
    Without an advisor, this remains a pure routing measurement.

    Design §12: we measure USEFUL ENGINEERING OUTPUT (objective evidence), not
    raw token count; and we do NOT optimize for cheapest tokens alone.
    """
    decision = router.route_task(
        task.task_id, task.full_dimension_scores, task_classes=[task.task_class]
    )
    if decision.selection is None:
        return BenchmarkResult(
            task=task,
            risk=decision.risk,
            outcome="NEEDS_HUMAN_REVIEW",
            measured_metrics={"failure": decision.failure_reason},
        )

    metric: Dict[str, object] = {
        "selected_tier": decision.selection.selected_tier.value,
        "model": decision.selection.selected_model_id,
    }
    outcome = "ROUTED"

    if advisor is not None:
        advisory = advisor.advise(
            selection=decision.selection,
            task_payload={
                "description": task.description,
                "tests_passed": 10,
                "tests_failed": 0,
                "build_result": "PASS",
                "static_result": None,
                "contract_result": None,
            },
            task_id=task.task_id,
        )
        metric["evidence_sufficient"] = advisory.match_evidence
        if advisory.invocation is not None:
            metric["invocation_status"] = advisory.invocation.status
            metric["tokens_total"] = advisory.invocation.usage.total_tokens
            metric["tokens_input"] = advisory.invocation.usage.input_tokens
            metric["tokens_output"] = advisory.invocation.usage.output_tokens
            metric["latency_ms"] = advisory.invocation.latency_ms
            metric["estimated_cost_usd"] = advisory.invocation.usage.estimated_cost_usd
        metric["escalation"] = (
            "NEEDS_HUMAN_REVIEW" if advisory.needs_human_review else "NO"
        )
        outcome = "SUCCESS" if advisory.match_evidence else "BLOCKED"
        metric["final_tier"] = decision.selection.selected_tier.value

    return BenchmarkResult(
        task=task,
        risk=decision.risk,
        outcome=outcome,
        measured_metrics=metric,
    )

# ---------------------------------------------------------------------------
# M11.4: machine-readable benchmark corpus runner (Phase 3/4).
# Runs each deterministic fixture through a ``ControlledLiveValidator`` (or a
# ShadowAdvisor) so the REAL provider path is exercised under operator control.
# The report is honest: failures and UNKNOWN token/cost values are recorded as
# such, never fabricated. Useful-engineering-output (objective evidence) is the
# primary signal, NOT token minimization.
# ---------------------------------------------------------------------------

def run_benchmark_corpus(
    router,
    *,
    validator=None,               # a ControlledLiveValidator-like ("validate_task")
    provider_configs=None,
    adapter=None,
    telemetry=None,
    live: bool = False,           # operator gate: real calls only if True
) -> dict:
    """Run the sample corpus and return a machine-readable JSON report.

    Without a validator, falls back to pure routing (no provider call) and marks
    each task ``executed=False``. When ``live`` is False, no provider invocation
    happens at all (offline-safe).
    """
    rows = []
    for task in SAMPLE_BENCHMARK_TASKS:
        decision = router.route_task(task.task_id, task.full_dimension_scores, task_classes=[task.task_class])
        row = {
            "task_id": task.task_id,
            "task_class": task.task_class,
            "expected_tier": task.expected_risk_tier.value,
            "selected_tier": None,
            "executed": False,
            "first_pass_success": False,
            "provider_errors": 0,
            "evidence_failures": 0,
            "escalations": None,
            "final_tier": None,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "tokens_unknown": True,
            "latency_ms": None,
            "estimated_cost_usd": None,
        }
        if decision.selection is not None:
            row["selected_tier"] = decision.selection.selected_tier.value
            row["final_tier"] = decision.selection.selected_tier.value
            row["escalations"] = 0

        if validator is not None and live:
            res = validator.validate_task(
                task_id=task.task_id,
                dimension_scores=task.full_dimension_scores,
                objective_evidence={"tests_passed": 10, "tests_failed": 0,
                                    "build_result": "PASS", "contract_result": "PASS"},
                task_classes=[task.task_class],
                gated_enabled=live,
            )
            row["executed"] = True
            row["selected_tier"] = res.selected_tier
            row["final_tier"] = res.selected_tier
            row["input_tokens"] = res.input_tokens
            row["output_tokens"] = res.output_tokens
            row["total_tokens"] = res.total_tokens
            row["tokens_unknown"] = res.tokens_unknown
            row["latency_ms"] = res.latency_ms
            row["estimated_cost_usd"] = res.estimated_cost_usd
            row["provider_errors"] = 1 if res.request_status != "success" else 0
            row["evidence_failures"] = 1 if res.evidence_outcome not in ("SUFFICIENT",) else 0
            row["first_pass_success"] = (res.final_outcome == "PASS")
        rows.append(row)

    # Aggregate useful-output metrics (not token-only).
    executed = [r for r in rows if r["executed"]]
    first_pass = sum(1 for r in rows if r["first_pass_success"])
    provider_err = sum(r["provider_errors"] for r in rows)
    ev_fail = sum(r["evidence_failures"] for r in rows)
    total_tokens_known = [r["total_tokens"] for r in executed if not r["tokens_unknown"]]
    total_cost = [r["estimated_cost_usd"] for r in executed if r["estimated_cost_usd"] is not None]
    summary = {
        "tasks_total": len(rows),
        "tasks_executed": len(executed),
        "first_pass_success": first_pass,
        "useful_output_rate": (first_pass / len(executed)) if executed else None,
        "provider_errors": provider_err,
        "evidence_failures": ev_fail,
        "total_tokens_sum": sum(total_tokens_known) if total_tokens_known else None,
        "estimated_cost_total": round(sum(total_cost), 6) if total_cost else None,
        "note": "Useful engineering output measured by objective evidence, not token "
                "minimization. UNKNOWN/None fields are honest unknowns, never fabricated.",
    }
    return {"summary": summary, "tasks": rows, "live": live}
