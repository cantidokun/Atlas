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
from planning.m11_router.model_profile import ModelTier


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


def run_benchmark_task(task: BenchmarkTask, router) -> BenchmarkResult:
    """Run one fixture through the router (returns a measured benchmark result).

    Design note: full corpus execution is deferred to the next M11 milestone;
    this skeleton wires the fixture shape and the router hook.
    """
    decision = router.route_task(
        task.task_id, task.full_dimension_scores, task_classes=[task.task_class]
    )
    metric = {}
    if decision.selection is not None:
        metric = {
            "selected_tier": decision.selection.selected_tier.value,
            "model": decision.selection.selected_model_id,
        }
    result = BenchmarkResult(
        task=task,
        risk=decision.risk,
        outcome="NEEDS_HUMAN_REVIEW" if decision.needs_human_review else "ROUTED",
        measured_metrics=metric,
    )
    return result
